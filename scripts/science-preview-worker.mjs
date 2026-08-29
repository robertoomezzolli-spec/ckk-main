import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { promisify } from 'node:util';
import {
  deterministicId,
  normalizeStructuralClaim,
  normalizationInput,
  sha256,
  stableStringify,
  structuralHash,
  trueConfluences,
} from '../science/core.mjs';
import {
  AnthropicAdapter,
  executeAgent,
  JUDGE_SCHEMA,
  NORMALIZATION_SCHEMA,
  OpenAIAdapter,
  SCOUT_SCHEMA,
} from '../science/agents.mjs';
import { JUDGE_PROMPT, NORMALIZER_PROMPT, RED_TEAM_PROMPT, SCOUT_PROMPT } from '../science/prompts.mjs';
import { ScienceStore } from '../netlify/functions/_science_store.mjs';

const execFileAsync = promisify(execFile);
const MAX_AGENT_CALLS = 5;
const CIRCUIT_BREAKER_THRESHOLD = 2;

function assertSafeOutbound(payload) {
  const serialized = stableStringify(payload);
  const forbidden = [
    /DATABASE_URL/i, /OPENAI_API_KEY/i, /ANTHROPIC_API_KEY/i, /postgres(?:ql)?:\/\//i,
    /\/Users\//, /agent\/graph_export/i, /hidden_target/i, /generator_output/i,
    /\b[0-9a-f]{64}\b/i,
  ];
  const violation = forbidden.find((pattern) => pattern.test(serialized));
  if (violation) throw new Error(`Outbound DLP rejected payload: ${violation}`);
  return payload;
}

function publicEvidence(candidateState) {
  return {
    candidate: {
      domain: candidateState.candidate.domain,
      name: candidateState.candidate.name,
      formal_statement: candidateState.candidate.formal_statement,
      uncertainties: candidateState.candidate.uncertainties ?? [],
    },
    evidence: candidateState.evidence.map((item, index) => ({
      evidence_ref: `E${index + 1}`,
      source_type: item.source_type,
      source_ref: item.source_ref,
      fact: item.fact,
      quality: item.quality,
    })),
  };
}

function assertSources(sources) {
  if (!Array.isArray(sources) || !sources.length) throw new Error('Scout returned no evidence sources');
  for (const source of sources) {
    const url = new URL(source.source_ref);
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Evidence source must be HTTP(S)');
    if (!source.fact?.trim()) throw new Error('Evidence source is missing a fact');
  }
}

function assertRedTeam(output) {
  if (!['PASS', 'FAIL', 'NEEDS_MORE_SOURCE'].includes(output.verdict)) throw new Error('Invalid red-team verdict');
  for (const field of ['blocking_issues', 'nonblocking_issues', 'source_gaps']) {
    if (!Array.isArray(output[field])) throw new Error(`Red team ${field} must be an array`);
  }
}

function normalizationRecord(candidateId, role, inputHash, output, evidenceIds) {
  const structuralClaim = normalizeStructuralClaim(output.structural_claim);
  const normalizedOutput = {
    structural_claim: structuralClaim,
    supported_by_evidence: output.supported_by_evidence ?? [],
    unmapped_properties: output.unmapped_properties ?? [],
    required_missing_distinctions: output.required_missing_distinctions ?? [],
    confidence: Number(output.confidence),
  };
  if (!Number.isFinite(normalizedOutput.confidence) || normalizedOutput.confidence < 0 || normalizedOutput.confidence > 1) throw new Error('Invalid normalization confidence');
  const outputHash = sha256(normalizedOutput);
  return {
    id: deterministicId('norm', { candidateId, role, inputHash, outputHash }),
    candidate_id: candidateId,
    agent_role: role,
    ...normalizedOutput,
    input_evidence_ids: evidenceIds,
    input_hash: inputHash,
    output_hash: outputHash,
  };
}

async function generate(generationId, levels, operatorVersion) {
  const { stdout } = await execFileAsync('python3', [
    new URL('./science-generate.py', import.meta.url).pathname,
    '--generation-id', generationId,
    '--levels', String(levels),
    '--operator-version', operatorVersion,
  ], { maxBuffer: 32 * 1024 * 1024 });
  return JSON.parse(stdout);
}

export async function runPreviewCycle({
  store,
  openai = new OpenAIAdapter(),
  anthropic = new AnthropicAdapter(),
  topic = 'In physics, identify one standard, source-supported phase variable that is one independent angular parameter and is periodic modulo one full turn (2π). Extract that narrow fact only.',
  levels = 1,
  clock = () => new Date(),
} = {}) {
  if (!store) throw new Error('ScienceStore is required');
  const workerId = deterministicId('worker', { started_at: clock().toISOString(), topic });
  let agentCalls = 0;
  let errorCount = 0;
  const report = { worker_id: workerId, stages: [], preview_only: true, public_eligible: false };
  await store.startWorkerRun({ id: workerId, batch_size: 1, max_agent_calls: MAX_AGENT_CALLS, circuit_breaker_threshold: CIRCUIT_BREAKER_THRESHOLD });

  const call = async (options) => {
    if (agentCalls >= MAX_AGENT_CALLS) throw new Error('Agent-call budget exhausted');
    if (errorCount >= CIRCUIT_BREAKER_THRESHOLD) throw new Error('Agent circuit breaker open');
    agentCalls += 1;
    try { return await executeAgent({ ...options, store, runNonce: workerId }); }
    catch (error) { errorCount += 1; throw error; }
  };

  let candidateId = null;
  try {
    const scoutInput = { domain: 'PHYSICS', quota: 1, topic, exclusion_keys: [], source_requirements: ['PRIMARY_OR_STANDARD', 'HTTP_REFERENCE'] };
    const scout = await call({
      role: 'GPT_SCOUT', candidateId: null, adapter: openai, input: scoutInput,
      prompt: `${SCOUT_PROMPT}\n\n${stableStringify(scoutInput)}`,
      schema: SCOUT_SCHEMA, schemaName: 'ckk_science_scout', webSearch: true,
    });
    assertSources(scout.output.sources);
    const dedupeKey = sha256({ domain: scout.output.domain, name: scout.output.candidate_name, formal: scout.output.formal_statement });
    const candidate = await store.createCandidate({
      domain: scout.output.domain,
      name: scout.output.candidate_name,
      status: 'DISCOVERED',
      created_by_agent: scout.runId,
      dedupe_key: dedupeKey,
      uncertainties: scout.output.uncertainties,
      formal_statement: scout.output.formal_statement,
      budget: { max_agent_calls: MAX_AGENT_CALLS, worker_run_id: workerId },
    });
    candidateId = candidate.id;
    await store.attachAgentRun(scout.runId, candidateId);
    report.stages.push({ stage: 'DISCOVER', status: 'PASS', candidate_id: candidateId, agent_run_id: scout.runId });

    const retrievedAt = clock().toISOString();
    await store.addEvidence(candidateId, scout.output.sources.map((source) => ({
      source_type: source.source_type,
      source_ref: source.source_ref,
      fact: source.fact,
      quality: source.quality,
      retrieved_at: retrievedAt,
      raw: { observed_properties: scout.output.observed_properties },
    })));
    await store.updateCandidate(candidateId, 'SOURCED');
    let candidateState = await store.candidate(candidateId);
    report.stages.push({ stage: 'SOURCE', status: 'PASS', evidence_count: candidateState.evidence.length });

    const redInput = assertSafeOutbound(publicEvidence(candidateState));
    const red = await call({
      role: 'CLAUDE_RED_TEAM', candidateId, adapter: anthropic, input: redInput,
      system: RED_TEAM_PROMPT,
      prompt: `${RED_TEAM_PROMPT}\n\nReturn exactly {"blocking_issues":[],"nonblocking_issues":[],"source_gaps":[],"verdict":"PASS|FAIL|NEEDS_MORE_SOURCE"}.\n\n${stableStringify(redInput)}`,
      evidenceIds: candidateState.evidence.map((item) => item.id),
    });
    assertRedTeam(red.output);
    if (red.output.verdict !== 'PASS') {
      await store.updateCandidate(candidateId, 'FAILED');
      await store.addFailure({ candidate_id: candidateId, domain: candidate.domain, code: red.output.verdict === 'FAIL' ? 'FORBIDDEN' : 'INSUFFICIENT_EVIDENCE', details: red.output });
      throw new Error(`Red team blocked candidate: ${red.output.verdict}`);
    }
    await store.updateCandidate(candidateId, 'CRITIQUED');
    report.stages.push({ stage: 'CRITIQUE', status: 'PASS', agent_run_id: red.runId });

    candidateState = await store.candidate(candidateId);
    const publicState = publicEvidence(candidateState);
    const isolatedInput = assertSafeOutbound({
      ...publicState,
      allowed_structural_fields: normalizationInput(candidateState.candidate, []).allowed_structural_fields,
      forbidden_inputs: ['other_normalization', 'hidden target', 'generator output', 'catalog match'],
    });
    const evidenceIds = candidateState.evidence.map((item) => item.id);
    await store.updateCandidate(candidateId, 'NORMALIZING');
    const [gptResult, claudeResult] = await Promise.all([
      call({
        role: 'GPT_NORMALIZER', candidateId, adapter: openai, input: isolatedInput,
        prompt: `${NORMALIZER_PROMPT}\n\n${stableStringify(isolatedInput)}`,
        schema: NORMALIZATION_SCHEMA, schemaName: 'ckk_science_normalization', evidenceIds,
      }),
      call({
        role: 'CLAUDE_NORMALIZER', candidateId, adapter: anthropic, input: isolatedInput,
        system: NORMALIZER_PROMPT,
        prompt: `${NORMALIZER_PROMPT}\nReturn JSON matching this field contract: structural_claim(kind,dim,order,sym,sq,anti,mult,bc,dual,occ), supported_by_evidence, unmapped_properties, required_missing_distinctions, confidence.\n\n${stableStringify(isolatedInput)}`,
        evidenceIds,
      }),
    ]);
    const gptNormalization = normalizationRecord(candidateId, 'GPT_NORMALIZER', gptResult.inputHash, gptResult.output, evidenceIds);
    const claudeNormalization = normalizationRecord(candidateId, 'CLAUDE_NORMALIZER', claudeResult.inputHash, claudeResult.output, evidenceIds);
    await store.addNormalization(gptNormalization);
    await store.addNormalization(claudeNormalization);
    report.stages.push({
      stage: 'NORMALIZE', status: stableStringify(gptNormalization.structural_claim) === stableStringify(claudeNormalization.structural_claim) ? 'AGREE' : 'DISAGREE',
      agent_run_ids: [gptResult.runId, claudeResult.runId], isolation: 'INDEPENDENT_INPUTS_NO_CROSS_VISIBILITY',
    });

    const judgeInput = assertSafeOutbound({
      evidence: publicState.evidence,
      gpt_normalization: { proposal_ref: 'GPT_PROPOSAL', structural_claim: gptNormalization.structural_claim, supported_by_evidence: gptNormalization.supported_by_evidence, unmapped_properties: gptNormalization.unmapped_properties, required_missing_distinctions: gptNormalization.required_missing_distinctions, confidence: gptNormalization.confidence },
      claude_normalization: { proposal_ref: 'CLAUDE_PROPOSAL', structural_claim: claudeNormalization.structural_claim, supported_by_evidence: claudeNormalization.supported_by_evidence, unmapped_properties: claudeNormalization.unmapped_properties, required_missing_distinctions: claudeNormalization.required_missing_distinctions, confidence: claudeNormalization.confidence },
      red_team: red.output,
      allowed_proposal_refs: ['GPT_PROPOSAL', 'CLAUDE_PROPOSAL'],
    });
    const judge = await call({
      role: 'JUDGE', candidateId, adapter: openai, input: judgeInput,
      prompt: `${JUDGE_PROMPT}\nIf and only if accepting, selected_normalization_id must be GPT_PROPOSAL or CLAUDE_PROPOSAL. These are aliases for the two supplied proposals.\n\n${stableStringify(judgeInput)}`,
      schema: JUDGE_SCHEMA, schemaName: 'ckk_science_judge', evidenceIds,
    });
    const proposalMap = { GPT_PROPOSAL: gptNormalization.id, CLAUDE_PROPOSAL: claudeNormalization.id };
    const judgeProposal = {
      ...judge.output,
      selected_normalization_id: judge.output.selected_normalization_id == null ? null : proposalMap[judge.output.selected_normalization_id],
    };
    if (judge.output.selected_normalization_id != null && !judgeProposal.selected_normalization_id) throw new Error('Judge selected an unknown proposal alias');
    const adjudication = await store.adjudicate(candidateId, judgeProposal, `OPENAI:${judge.model}`);
    report.stages.push({ stage: 'ADJUDICATE', status: adjudication.verdict, agent_run_id: judge.runId });
    if (adjudication.verdict !== 'ACCEPT_NORMALIZATION') throw new Error(`Candidate not accepted: ${adjudication.verdict}`);

    candidateState = await store.candidate(candidateId);
    const selected = candidateState.normalizations.find((item) => item.id === adjudication.selected_normalization_id);
    const frozenPayload = {
      structural_claim: normalizeStructuralClaim(selected.structural_claim),
      input_evidence_ids: selected.input_evidence_ids,
      adjudication_id: adjudication.id,
      hidden_from_generator: true,
    };
    const canonId = `preview-physics-canon-v1-${workerId.slice(-8)}`;
    const target = await store.freezeTarget({
      canon_id: canonId,
      canon_version: 1,
      canon_hash: sha256({ canonId, status: 'PREVIEW_ONLY', denominator: 1 }),
      canon_manifest: { role: 'AUTONOMOUS_PREVIEW_ONLY', source_candidate_id: candidateId, immutable: true },
      coverage_denominator: 1,
      candidate_id: candidateId,
      domain: candidateState.candidate.domain,
      name: candidateState.candidate.name,
      frozen_payload: frozenPayload,
    });
    report.stages.push({ stage: 'FREEZE', status: 'PASS', target_id: target.id, payload_hash: target.payload_hash });

    const [grammarSource, seedFixture] = await Promise.all([
      readFile(new URL('../ckk_snapshot/ckk/gen/grammar.py', import.meta.url), 'utf8'),
      readFile(new URL('../crossdomain/physics/seed.fixture.json', import.meta.url), 'utf8'),
    ]);
    const grammarHash = sha256(grammarSource);
    const seedSetHash = sha256(seedFixture);
    const generationId = `sci-v1-preview-${sha256({ workerId, grammarHash, seedSetHash, levels }).slice(0, 16)}`;
    const generated = await generate(generationId, levels, `ckk-grammar-${grammarHash.slice(0, 12)}`);
    const confluences = trueConfluences(generated.derivation_events);
    await store.persistGeneration({
      id: generationId,
      grammar_version: 'scientific-v1-current-core',
      grammar_hash: grammarHash,
      seed_set_hash: seedSetHash,
      maxdim: generated.experiment.maxdim,
      expansion_levels: levels,
      true_confluence_count: confluences.length,
      scope: {
        candidate_id: candidateId,
        target_id: target.id,
        hidden_target_not_supplied_to_generator: true,
        full_crossdomain_regression_eligible: false,
        full_crossdomain_regression_reason: 'GOLDEN_CANONS_INCOMPLETE_AND_DEEPER_CORE_LEAKS_REMAIN',
      },
    }, generated);
    await store.updateCandidate(candidateId, 'GENERATED');
    report.stages.push({ stage: 'GENERATE', status: 'PASS', generation_id: generationId, structures: generated.structures.length, derivation_events: generated.derivation_events.length, true_confluences: confluences.length });

    const targetHash = structuralHash(frozenPayload.structural_claim);
    const matched = generated.structures.find((item) => item.structural_hash === targetHash);
    if (!matched) {
      await store.addFailure({ candidate_id: candidateId, generation_id: generationId, domain: candidateState.candidate.domain, code: 'OUT_OF_SCOPE', details: { target_hash: targetHash } });
      await store.updateCandidate(candidateId, 'FAILED');
      throw new Error('Frozen target was not generated in the controlled scope');
    }
    const interpretation = await store.addInterpretation({
      id: deterministicId('interp', { generationId, structure: matched.id, target: target.id }),
      generation_id: generationId,
      structure_id: matched.id,
      domain: candidateState.candidate.domain,
      target_id: target.id,
      status: 'REDISCOVERED',
      match_rule: 'BLIND_EXACT_STRUCTURAL_HASH',
      confidence: Math.min(Number(selected.confidence), 1),
      evidence_ids: evidenceIds,
    });
    await store.updateCandidate(candidateId, 'MATCHED');
    report.stages.push({ stage: 'MATCH', status: 'REDISCOVERED', structure_id: matched.id, interpretation_id: interpretation.id, semantic_equivalence: 'NOT_EVALUATED' });

    const validation = await store.validateGeneration(generationId);
    if (!validation.clean) throw new Error(`Generation validation failed: ${validation.errors.join('; ')}`);
    await store.updateCandidate(candidateId, 'VALIDATED');
    report.stages.push({ stage: 'VALIDATE', status: 'PASS', validation });
    const seal = await store.sealGeneration(generationId, { publicEligible: false, candidateId });
    report.stages.push({ stage: 'SEAL', status: 'PASS', seal: seal.seal, public_eligible: false });
    report.result = 'SEALED_PREVIEW_NOT_PUBLIC_ELIGIBLE';
    report.candidate_id = candidateId;
    report.generation_id = generationId;
    await store.updateWorkerRun(workerId, { status: 'SUCCEEDED', agent_calls: agentCalls, error_count: errorCount, report });
    return report;
  } catch (error) {
    report.result = 'FAILED';
    report.error = String(error.message ?? error);
    report.candidate_id = candidateId;
    await store.updateWorkerRun(workerId, { status: errorCount >= CIRCUIT_BREAKER_THRESHOLD ? 'CIRCUIT_OPEN' : 'FAILED', agent_calls: agentCalls, error_count: errorCount, report });
    throw Object.assign(error, { report });
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const databaseUrl = process.env.SCIENCE_DATABASE_URL;
  if (!databaseUrl) throw new Error('SCIENCE_DATABASE_URL missing; production DATABASE_URL is deliberately ignored');
  const report = await runPreviewCycle({ store: ScienceStore.connect(databaseUrl) });
  console.log(JSON.stringify(report, null, 2));
}
