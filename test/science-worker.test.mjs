import assert from 'node:assert/strict';
import { test } from 'node:test';
import { adjudicateNormalizations, deterministicId, sha256 } from '../science/core.mjs';
import { validateGenerationPayload } from '../science/validation.mjs';
import { runPreviewCycle } from '../scripts/science-preview-worker.mjs';

class SequenceAdapter {
  constructor(provider, model, outputs) { this.provider = provider; this.model = model; this.outputs = [...outputs]; }
  async complete() { return { output: this.outputs.shift(), usage: { input_tokens: 1, output_tokens: 1 }, model: this.model }; }
}

class MemoryStore {
  constructor() { this.candidates = new Map(); this.evidence = new Map(); this.normalizations = new Map(); this.agentRuns = []; this.generations = new Map(); this.interpretations = []; }
  async startWorkerRun(input) { this.worker = { ...input, status: 'RUNNING' }; }
  async updateWorkerRun(_id, fields) { Object.assign(this.worker, fields); }
  async startAgentRun(input) { this.agentRuns.push({ ...input, status: 'RUNNING' }); }
  async finishAgentRun(id, status, output) { Object.assign(this.agentRuns.find((item) => item.id === id), { status, output }); }
  async attachAgentRun(id, candidateId) { this.agentRuns.find((item) => item.id === id).candidate_id = candidateId; }
  async createCandidate(input) { const item = { id: deterministicId('cand', input.dedupe_key), ...input }; this.candidates.set(item.id, item); return item; }
  async updateCandidate(id, status) { this.candidates.get(id).status = status; return this.candidates.get(id); }
  async addEvidence(candidateId, rows) { const items = rows.map((item, index) => ({ id: `e${index + 1}`, candidate_id: candidateId, content_hash: sha256(item), ...item })); this.evidence.set(candidateId, items); return items; }
  async candidate(id) { return { candidate: this.candidates.get(id), evidence: this.evidence.get(id) ?? [], normalizations: this.normalizations.get(id) ?? [], adjudication: this.adjudication ?? null, agent_trace: this.agentRuns.filter((item) => item.candidate_id === id) }; }
  async addFailure(input) { this.failure = input; }
  async addNormalization(input) { const list = this.normalizations.get(input.candidate_id) ?? []; list.push(input); this.normalizations.set(input.candidate_id, list); return input; }
  async adjudicate(candidateId, proposed, judgeVersion) {
    const [gpt, claude] = this.normalizations.get(candidateId);
    const result = adjudicateNormalizations(gpt, claude, proposed);
    this.adjudication = { id: 'adj', candidate_id: candidateId, judge_version: judgeVersion, ...result };
    this.candidates.get(candidateId).status = result.verdict === 'ACCEPT_NORMALIZATION' ? 'ADJUDICATED' : 'DISPUTED';
    return this.adjudication;
  }
  async freezeTarget(input) { this.target = { id: deterministicId('target', input.frozen_payload), payload_hash: sha256(input.frozen_payload), ...input }; this.candidates.get(input.candidate_id).status = 'FROZEN'; return this.target; }
  async persistGeneration(generation, payload) { this.generations.set(generation.id, { generation: { ...generation, node_count: payload.structures.length, derivation_event_count: payload.derivation_events.length, status: 'GENERATED' }, payload }); }
  async addInterpretation(input) { this.interpretations.push(input); return input; }
  async validateGeneration(id) { const item = this.generations.get(id); const report = validateGenerationPayload(item.generation, item.payload.structures, item.payload.derivation_events); item.generation.validation_report = report; item.generation.status = report.clean ? 'VALIDATED' : 'REJECTED'; return report; }
  async sealGeneration(id, options) { const item = this.generations.get(id); assert.equal(item.generation.status, 'VALIDATED'); item.generation.status = 'SEALED'; this.seal = { generation_id: id, public_eligible: options.publicEligible }; return { generation: item.generation, seal: this.seal }; }
}

test('contract-replay pipeline reaches private seal with five isolated agent calls', async () => {
  const scout = {
    candidate_name: 'Periodic phase fixture', domain: 'PHYSICS',
    sources: [{ source_ref: 'https://example.test/public-standard', source_type: 'standard', fact: 'A phase angle is periodic modulo 2π.', quality: 'STANDARD' }],
    formal_statement: 'θ is one angular parameter with θ ≡ θ + 2π.', observed_properties: ['one periodic parameter'], uncertainties: [],
  };
  const normalization = {
    structural_claim: { kind: 'CYCLE', dim: 1, order: 0, sym: null, sq: null, anti: null, mult: 1, bc: null, dual: 0, occ: null },
    supported_by_evidence: ['E1'], unmapped_properties: [], required_missing_distinctions: [], confidence: 0.9,
  };
  const openai = new SequenceAdapter('OPENAI_TEST_DOUBLE', 'gpt-test', [
    scout,
    normalization,
    { verdict: 'ACCEPT_NORMALIZATION', reason: 'The supplied proposals agree.', blocking_items: [], selected_normalization_id: 'GPT_PROPOSAL' },
  ]);
  const anthropic = new SequenceAdapter('ANTHROPIC_TEST_DOUBLE', 'claude-test', [
    { blocking_issues: [], nonblocking_issues: [], source_gaps: [], verdict: 'PASS' },
    normalization,
  ]);
  const store = new MemoryStore();
  const report = await runPreviewCycle({ store, openai, anthropic, clock: () => new Date('2026-08-27T18:00:00Z') });
  assert.equal(report.result, 'SEALED_PREVIEW_NOT_PUBLIC_ELIGIBLE');
  assert.equal(report.stages.map((item) => item.stage).join('>'), 'DISCOVER>SOURCE>CRITIQUE>NORMALIZE>ADJUDICATE>FREEZE>GENERATE>MATCH>VALIDATE>SEAL');
  assert.equal(store.agentRuns.length, 5);
  assert.equal(store.agentRuns.every((item) => item.status === 'SUCCEEDED'), true);
  assert.equal(store.seal.public_eligible, false);
  assert.equal(store.interpretations[0].status, 'REDISCOVERED');
  assert.equal(store.generations.get(report.generation_id).generation.scope.hidden_target_not_supplied_to_generator, true);
});

