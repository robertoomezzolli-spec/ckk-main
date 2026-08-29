import { neon } from '@neondatabase/serverless';
import {
  adjudicateNormalizations,
  crossDomainMatches,
  deterministicId,
  sha256,
  stableStringify,
} from '../../science/core.mjs';
import { validateGenerationPayload } from '../../science/validation.mjs';

const json = (value) => JSON.stringify(value ?? null);

export class ScienceStore {
  constructor(sql) {
    this.sql = sql;
  }

  static connect(databaseUrl = process.env.DATABASE_URL) {
    if (!databaseUrl) throw new Error('DATABASE_URL missing');
    return new ScienceStore(neon(databaseUrl));
  }

  async overview() {
    const [generationStatus, candidateStatus, failureStatus, agentStatus, publicState] = await this.sql.transaction([
      this.sql`SELECT status,count(*)::int AS count FROM science_generations GROUP BY status ORDER BY status`,
      this.sql`SELECT status,count(*)::int AS count FROM science_candidates GROUP BY status ORDER BY status`,
      this.sql`SELECT code,count(*)::int AS count FROM science_failures WHERE status <> 'RESOLVED' GROUP BY code ORDER BY code`,
      this.sql`SELECT role,status,count(*)::int AS count FROM science_agent_runs GROUP BY role,status ORDER BY role,status`,
      this.sql`SELECT active_generation_id,updated_at FROM science_public_state WHERE singleton=true`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return {
      schema: 'ckk.science-overview.v1',
      separation: { structure_derivation_interpretation: true },
      self_duality: 'NOT_EVALUATED',
      generation_status: generationStatus,
      candidate_status: candidateStatus,
      failure_status: failureStatus,
      agent_status: agentStatus,
      public_state: publicState[0] ?? { active_generation_id: null },
      historical_run34: {
        generation_id: 'v6-noselfdual-563f50e328c5', run_id: 34,
        nodes: 276, edges: 945, historical_graph_confluences: 196,
        role: 'SEALED_HISTORICAL_PRESENTATION_SNAPSHOT',
      },
    };
  }

  async listGenerations() {
    return this.sql`SELECT g.*,s.validator_version,s.test_report_hash,s.sealed_at,s.public_eligible
      FROM science_generations g LEFT JOIN science_seals s ON s.generation_id=g.id
      ORDER BY g.created_at DESC`;
  }

  async generation(id) {
    const [generations, structures, events, interpretations, seals, failures] = await this.sql.transaction([
      this.sql`SELECT * FROM science_generations WHERE id=${id}`,
      this.sql`SELECT * FROM science_structures WHERE generation_id=${id} ORDER BY kind,dim,id`,
      this.sql`SELECT * FROM science_derivation_events WHERE generation_id=${id} ORDER BY level,operator,id`,
      this.sql`SELECT * FROM science_interpretations WHERE generation_id=${id} ORDER BY domain,status,id`,
      this.sql`SELECT * FROM science_seals WHERE generation_id=${id}`,
      this.sql`SELECT * FROM science_failures WHERE generation_id=${id} ORDER BY created_at,id`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    if (!generations[0]) return null;
    return { generation: generations[0], structures, derivation_events: events, interpretations, seal: seals[0] ?? null, failures };
  }

  async structure(id, generationId = null) {
    const structures = generationId
      ? await this.sql`SELECT * FROM science_structures WHERE generation_id=${generationId} AND id=${id}`
      : await this.sql`SELECT s.* FROM science_structures s JOIN science_generations g ON g.id=s.generation_id
          WHERE s.id=${id} ORDER BY g.created_at DESC LIMIT 1`;
    if (!structures[0]) return null;
    const structure = structures[0];
    const [incoming, outgoing, interpretations, traces] = await this.sql.transaction([
      this.sql`SELECT * FROM science_derivation_events WHERE generation_id=${structure.generation_id} AND output=${structure.id} ORDER BY level,id`,
      this.sql`SELECT * FROM science_derivation_events WHERE generation_id=${structure.generation_id} AND inputs ? ${structure.id} ORDER BY level,id`,
      this.sql`SELECT * FROM science_interpretations WHERE generation_id=${structure.generation_id} AND structure_id=${structure.id} ORDER BY domain,id`,
      this.sql`SELECT r.* FROM science_agent_runs r JOIN science_candidates c ON c.id=r.candidate_id
        JOIN science_canon_targets t ON t.candidate_id=c.id JOIN science_interpretations i ON i.target_id=t.id
        WHERE i.generation_id=${structure.generation_id} AND i.structure_id=${structure.id} ORDER BY r.started_at`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return { structure, derivation_events: { incoming, outgoing }, interpretations, agent_trace: traces };
  }

  async listCandidates() {
    return this.sql`SELECT c.*,
      (SELECT count(*)::int FROM science_evidence e WHERE e.candidate_id=c.id) evidence_count,
      (SELECT count(*)::int FROM science_normalizations n WHERE n.candidate_id=c.id) normalization_count
      FROM science_candidates c ORDER BY c.created_at DESC`;
  }

  async candidate(id) {
    const [candidate, evidence, normalizations, adjudications, traces, targets] = await this.sql.transaction([
      this.sql`SELECT * FROM science_candidates WHERE id=${id}`,
      this.sql`SELECT * FROM science_evidence WHERE candidate_id=${id} ORDER BY created_at,id`,
      this.sql`SELECT * FROM science_normalizations WHERE candidate_id=${id} ORDER BY agent_role`,
      this.sql`SELECT * FROM science_adjudications WHERE candidate_id=${id}`,
      this.sql`SELECT * FROM science_agent_runs WHERE candidate_id=${id} ORDER BY started_at,id`,
      this.sql`SELECT * FROM science_canon_targets WHERE candidate_id=${id}`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return candidate[0] ? {
      candidate: candidate[0], evidence, normalizations,
      adjudication: adjudications[0] ?? null, agent_trace: traces, target: targets[0] ?? null,
    } : null;
  }

  async disputes() {
    const candidates = await this.sql`SELECT * FROM science_candidates WHERE status='DISPUTED' ORDER BY updated_at DESC`;
    const result = [];
    for (const candidate of candidates) result.push(await this.candidate(candidate.id));
    return result;
  }

  async failures() {
    return this.sql`SELECT * FROM science_failures ORDER BY status,created_at DESC,id`;
  }

  async grammarPressure() {
    const [groups, proposals] = await this.sql.transaction([
      this.sql`SELECT missing_distinction,array_agg(DISTINCT domain ORDER BY domain) domains,
        count(*)::int failure_count,array_agg(id ORDER BY id) failure_ids
        FROM science_failures WHERE status <> 'RESOLVED' AND missing_distinction IS NOT NULL
        GROUP BY missing_distinction ORDER BY count(*) DESC,missing_distinction`,
      this.sql`SELECT * FROM science_grammar_proposals ORDER BY created_at DESC,id`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return { groups, proposals, automatic_activation: 'FORBIDDEN', required_status: 'HUMAN_REVIEW_REQUIRED' };
  }

  async crossDomain() {
    const [structures, interpretations] = await this.sql.transaction([
      this.sql`SELECT s.* FROM science_structures s JOIN science_generations g ON g.id=s.generation_id WHERE g.status='SEALED'`,
      this.sql`SELECT i.* FROM science_interpretations i JOIN science_generations g ON g.id=i.generation_id WHERE g.status='SEALED' AND i.sealed=true`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return crossDomainMatches(interpretations, structures);
  }

  async createCandidate(input) {
    const id = input.id ?? deterministicId('cand', input.dedupe_key);
    const rows = await this.sql`INSERT INTO science_candidates(
      id,domain,name,status,created_by_agent,dedupe_key,uncertainties,formal_statement,budget
    ) VALUES(
      ${id},${input.domain},${input.name},${input.status ?? 'DISCOVERED'},${input.created_by_agent},${input.dedupe_key},
      ${json(input.uncertainties ?? [])}::jsonb,${input.formal_statement ?? null},${json(input.budget ?? {})}::jsonb
    ) ON CONFLICT(dedupe_key) DO UPDATE SET updated_at=science_candidates.updated_at RETURNING *`;
    return rows[0];
  }

  async updateCandidate(id, status, fields = {}) {
    const rows = await this.sql`UPDATE science_candidates SET status=${status},
      formal_statement=COALESCE(${fields.formal_statement ?? null},formal_statement),
      uncertainties=COALESCE(${fields.uncertainties ? json(fields.uncertainties) : null}::jsonb,uncertainties)
      WHERE id=${id} RETURNING *`;
    return rows[0] ?? null;
  }

  async addEvidence(candidateId, evidence) {
    const queries = evidence.map((item) => {
      const contentHash = item.content_hash ?? sha256({ source_ref: item.source_ref, fact: item.fact });
      const id = item.id ?? deterministicId('ev', { candidateId, contentHash });
      return this.sql`INSERT INTO science_evidence(
        id,candidate_id,source_type,source_ref,fact,retrieved_at,quality,content_hash,raw
      ) VALUES(${id},${candidateId},${item.source_type},${item.source_ref},${item.fact},${item.retrieved_at},${item.quality},${contentHash},${json(item.raw ?? {})}::jsonb)
      ON CONFLICT(candidate_id,content_hash) DO NOTHING RETURNING *`;
    });
    const results = queries.length ? await this.sql.transaction(queries) : [];
    return results.flat();
  }

  async startAgentRun(input) {
    const rows = await this.sql`INSERT INTO science_agent_runs(
      id,candidate_id,role,provider,model,prompt_version,isolation_key,input_hash,status,input_evidence_ids
    ) VALUES(${input.id},${input.candidate_id ?? null},${input.role},${input.provider},${input.model},${input.prompt_version},
      ${input.isolation_key},${input.input_hash},'RUNNING',${json(input.input_evidence_ids ?? [])}::jsonb) RETURNING *`;
    return rows[0];
  }

  async finishAgentRun(id, status, output, usage = {}, error = null) {
    const outputHash = output == null ? null : sha256(output);
    const rows = await this.sql`UPDATE science_agent_runs SET status=${status},output=${output == null ? null : json(output)}::jsonb,
      output_hash=${outputHash},usage=${json(usage)}::jsonb,error=${error},finished_at=now() WHERE id=${id} RETURNING *`;
    return rows[0] ?? null;
  }

  async attachAgentRun(id, candidateId) {
    const rows = await this.sql`UPDATE science_agent_runs SET candidate_id=${candidateId} WHERE id=${id} AND candidate_id IS NULL RETURNING *`;
    return rows[0] ?? null;
  }

  async startWorkerRun(input) {
    const rows = await this.sql`INSERT INTO science_worker_runs(
      id,status,batch_size,max_agent_calls,circuit_breaker_threshold
    ) VALUES(${input.id},'RUNNING',${input.batch_size},${input.max_agent_calls},${input.circuit_breaker_threshold}) RETURNING *`;
    return rows[0];
  }

  async updateWorkerRun(id, fields) {
    const rows = await this.sql`UPDATE science_worker_runs SET status=${fields.status},agent_calls=${fields.agent_calls},
      error_count=${fields.error_count},report=${json(fields.report ?? {})}::jsonb,
      finished_at=CASE WHEN ${fields.status}='RUNNING' THEN NULL ELSE now() END WHERE id=${id} RETURNING *`;
    return rows[0] ?? null;
  }

  async addFailure(input) {
    const id = input.id ?? deterministicId('failure', input);
    const rows = await this.sql`INSERT INTO science_failures(
      id,candidate_id,generation_id,domain,code,missing_distinction,details,status
    ) VALUES(${id},${input.candidate_id ?? null},${input.generation_id ?? null},${input.domain},${input.code},
      ${input.missing_distinction ?? null},${json(input.details ?? {})}::jsonb,${input.status ?? 'OPEN'})
      ON CONFLICT(id) DO NOTHING RETURNING *`;
    return rows[0];
  }

  async addNormalization(input) {
    const rows = await this.sql`INSERT INTO science_normalizations(
      id,candidate_id,agent_role,structural_claim,supported_by_evidence,input_evidence_ids,
      unmapped_properties,required_missing_distinctions,confidence,input_hash,output_hash
    ) VALUES(${input.id},${input.candidate_id},${input.agent_role},${json(input.structural_claim)}::jsonb,
      ${json(input.supported_by_evidence ?? [])}::jsonb,${json(input.input_evidence_ids)}::jsonb,
      ${json(input.unmapped_properties ?? [])}::jsonb,${json(input.required_missing_distinctions ?? [])}::jsonb,
      ${input.confidence},${input.input_hash},${input.output_hash}) RETURNING *`;
    return rows[0];
  }

  async adjudicate(candidateId, proposed, judgeVersion) {
    const normalizations = await this.sql`SELECT * FROM science_normalizations WHERE candidate_id=${candidateId} ORDER BY agent_role`;
    const gpt = normalizations.find((item) => item.agent_role === 'GPT_NORMALIZER');
    const claude = normalizations.find((item) => item.agent_role === 'CLAUDE_NORMALIZER');
    if (!gpt || !claude) throw new Error('Both independent normalizations are required');
    const result = adjudicateNormalizations(gpt, claude, proposed);
    const id = deterministicId('adj', { candidateId, normalizations: normalizations.map((item) => item.id), result });
    const status = result.verdict === 'ACCEPT_NORMALIZATION' ? 'ADJUDICATED' : result.verdict === 'AMBIGUOUS' ? 'DISPUTED' : 'REJECTED';
    const [adjudication] = await this.sql.transaction([
      this.sql`INSERT INTO science_adjudications(
        id,candidate_id,verdict,normalization_ids,selected_normalization_id,reason,blocking_items,judge_version
      ) VALUES(${id},${candidateId},${result.verdict},${json(normalizations.map((item) => item.id))}::jsonb,
        ${result.selected_normalization_id},${result.reason},${json(result.blocking_items)}::jsonb,${judgeVersion}) RETURNING *`,
      this.sql`UPDATE science_candidates SET status=${status} WHERE id=${candidateId} RETURNING *`,
    ]);
    return { ...adjudication[0], candidate_status: status };
  }

  async freezeTarget(input) {
    const payloadHash = sha256(input.frozen_payload);
    const targetId = input.id ?? deterministicId('target', payloadHash);
    const queries = [
      this.sql`INSERT INTO science_canons(id,domain,version,status,coverage_denominator,manifest,payload_hash,frozen_at)
        VALUES(${input.canon_id},${input.domain},${input.canon_version ?? 1},'FROZEN',${input.coverage_denominator ?? 1},
        ${json(input.canon_manifest ?? {})}::jsonb,${input.canon_hash},now()) ON CONFLICT(id) DO NOTHING`,
      this.sql`INSERT INTO science_canon_targets(id,canon_id,candidate_id,domain,name,hidden,frozen_payload,payload_hash)
        VALUES(${targetId},${input.canon_id},${input.candidate_id},${input.domain},${input.name},true,
        ${json(input.frozen_payload)}::jsonb,${payloadHash}) RETURNING *`,
      this.sql`UPDATE science_candidates SET status='FROZEN' WHERE id=${input.candidate_id} RETURNING *`,
    ];
    const result = await this.sql.transaction(queries);
    return result[1][0];
  }

  async persistGeneration(generation, payload) {
    const confluenceCount = generation.true_confluence_count;
    const queries = [
      this.sql`SELECT pg_advisory_xact_lock(hashtext('ckk-science-generation-writer'))`,
      this.sql`INSERT INTO science_generations(
        id,grammar_version,grammar_hash,seed_set_hash,maxdim,expansion_levels,status,parent_generation_id,scope,
        node_count,derivation_event_count,true_confluence_count,preview
      ) VALUES(${generation.id},${generation.grammar_version},${generation.grammar_hash},${generation.seed_set_hash},
        ${generation.maxdim},${generation.expansion_levels},'DRAFT',${generation.parent_generation_id ?? null},
        ${json(generation.scope ?? {})}::jsonb,${payload.structures.length},${payload.derivation_events.length},${confluenceCount},true)`,
      ...payload.structures.map((item) => this.sql`INSERT INTO science_structures(
        generation_id,id,kind,dim,recurrence_order,sym,sq,anti,mult,bc,dual,occ,lifecycle,structural_sig,structural_hash
      ) VALUES(${generation.id},${item.id},${item.kind},${item.dim},${item.recurrence_order},${item.sym},${item.sq},${item.anti},
        ${item.mult},${item.bc},${item.dual},${item.occ},${item.lifecycle},${json(item.structural_sig)}::jsonb,${item.structural_hash})`),
      ...payload.derivation_events.map((item) => this.sql`INSERT INTO science_derivation_events(
        generation_id,id,operator,operator_version,inputs,output,parameters,level,input_structural_hashes,output_structural_hash,event_hash
      ) VALUES(${generation.id},${item.id},${item.operator},${item.operator_version},${json(item.inputs)}::jsonb,${item.output},
        ${json(item.parameters)}::jsonb,${item.level},${json(item.input_structural_hashes)}::jsonb,${item.output_structural_hash},${item.event_hash})`),
      this.sql`UPDATE science_generations SET status='GENERATED',generated_at=now() WHERE id=${generation.id} RETURNING *`,
    ];
    const result = await this.sql.transaction(queries, { isolationLevel: 'Serializable' });
    return result.at(-1)[0];
  }

  async addInterpretation(input) {
    const rows = await this.sql`INSERT INTO science_interpretations(
      id,generation_id,structure_id,domain,target_id,status,match_rule,confidence,evidence_ids,sealed
    ) VALUES(${input.id},${input.generation_id},${input.structure_id},${input.domain},${input.target_id},${input.status},
      ${input.match_rule},${input.confidence},${json(input.evidence_ids ?? [])}::jsonb,false) RETURNING *`;
    return rows[0];
  }

  async validateGeneration(id) {
    const snapshot = await this.generation(id);
    if (!snapshot) throw new Error('Generation not found');
    if (snapshot.generation.status !== 'GENERATED') throw new Error(`Generation must be GENERATED, got ${snapshot.generation.status}`);
    const report = validateGenerationPayload(snapshot.generation, snapshot.structures, snapshot.derivation_events);
    if (!report.clean) {
      const failureId = deterministicId('failure', { id, report });
      await this.sql.transaction([
        this.sql`UPDATE science_generations SET validation_report=${json(report)}::jsonb,status='REJECTED' WHERE id=${id}`,
        this.sql`INSERT INTO science_failures(id,generation_id,domain,code,missing_distinction,details)
          VALUES(${failureId},${id},'PHYSICS','VALIDATION_FAILED','GENERATION_INTEGRITY',${json(report)}::jsonb)`,
      ]);
      return report;
    }
    await this.sql.transaction([
      this.sql`UPDATE science_generations SET status='AUDITED',validation_report=${json(report)}::jsonb WHERE id=${id}`,
      this.sql`UPDATE science_generations SET status='VALIDATED',validated_at=now() WHERE id=${id}`,
    ], { isolationLevel: 'Serializable' });
    return report;
  }

  async sealGeneration(id, { publicEligible = false, candidateId = null } = {}) {
    const rows = await this.sql`SELECT * FROM science_generations WHERE id=${id}`;
    const generation = rows[0];
    if (!generation || generation.status !== 'VALIDATED' || !generation.validation_report?.clean) {
      throw new Error('Only a clean VALIDATED generation may be sealed');
    }
    const reportHash = sha256(generation.validation_report);
    const sealPayload = {
      generation_id: id,
      grammar_hash: generation.grammar_hash,
      seed_set_hash: generation.seed_set_hash,
      validation_report_hash: reportHash,
      public_eligible: publicEligible,
    };
    const queries = [
      this.sql`SELECT pg_advisory_xact_lock(hashtext('ckk-science-generation-writer'))`,
      this.sql`UPDATE science_generations SET status='SEALED' WHERE id=${id} RETURNING *`,
      this.sql`INSERT INTO science_seals(generation_id,validator_version,test_report_hash,public_eligible,seal_payload)
        VALUES(${id},${generation.validation_report.validator_version},${reportHash},${publicEligible},${json(sealPayload)}::jsonb) RETURNING *`,
      this.sql`UPDATE science_interpretations SET sealed=true WHERE generation_id=${id} RETURNING id`,
    ];
    if (candidateId) queries.push(this.sql`UPDATE science_candidates SET status='SEALED' WHERE id=${candidateId} RETURNING *`);
    const result = await this.sql.transaction(queries, { isolationLevel: 'Serializable' });
    return { generation: result[1][0], seal: result[2][0] };
  }

  async publicActiveGeneration() {
    const rows = await this.sql`SELECT g.*,s.validator_version,s.test_report_hash,s.sealed_at,s.public_eligible
      FROM science_public_state p JOIN science_generations g ON g.id=p.active_generation_id
      JOIN science_seals s ON s.generation_id=g.id
      WHERE p.singleton=true AND g.status='SEALED' AND s.public_eligible=true`;
    return rows[0] ?? null;
  }

  async publicUniverse() {
    const active = await this.publicActiveGeneration();
    if (!active) return null;
    return this.generation(active.id);
  }

  async publicStructure(id) {
    const active = await this.publicActiveGeneration();
    if (!active) return null;
    return this.structure(id, active.id);
  }

  async publicCrossDomain(hash) {
    const active = await this.publicActiveGeneration();
    if (!active) return null;
    const [structures, interpretations] = await this.sql.transaction([
      this.sql`SELECT * FROM science_structures WHERE generation_id=${active.id} AND structural_hash=${hash}`,
      this.sql`SELECT i.* FROM science_interpretations i JOIN science_structures s
        ON s.generation_id=i.generation_id AND s.id=i.structure_id
        WHERE i.generation_id=${active.id} AND s.structural_hash=${hash} AND i.sealed=true`,
    ], { isolationLevel: 'RepeatableRead', readOnly: true });
    return { generation_id: active.id, structural_hash: hash, structures, interpretations, verdict: 'STRUCTURAL_MATCH', same_mechanism: 'NOT_EVALUATED' };
  }
}

export function scienceStore(databaseUrl) {
  return ScienceStore.connect(databaseUrl);
}

export function payloadHash(payload) {
  return sha256(stableStringify(payload));
}
