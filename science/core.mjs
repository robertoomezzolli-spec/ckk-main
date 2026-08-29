import crypto from 'node:crypto';

export const DOMAINS = Object.freeze(['PHYSICS', 'CHEMISTRY', 'BIOLOGY', 'COMPUTATION', 'MATHEMATICS']);
export const JUDGE_VERDICTS = Object.freeze([
  'ACCEPT_NORMALIZATION', 'REJECT', 'AMBIGUOUS', 'NEEDS_SOURCE', 'NEEDS_SCHEMA',
]);
export const FAILURE_CODES = Object.freeze([
  'MISSING_PRIMITIVE', 'MISSING_OPERATOR', 'SIGNATURE_COLLISION', 'AMBIGUOUS',
  'OUT_OF_SCOPE', 'INSUFFICIENT_EVIDENCE', 'FORBIDDEN', 'VALIDATION_FAILED',
]);
export const STRUCTURAL_FIELDS = Object.freeze([
  'kind', 'dim', 'order', 'sym', 'sq', 'anti', 'mult', 'bc', 'dual', 'occ',
]);
export const SELF_DUALITY = Object.freeze({
  assessment: 'NOT_EVALUATED',
  equivalence_relation: null,
});

export function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, stableValue(value[key])]));
  }
  return value;
}

export function stableStringify(value) {
  return JSON.stringify(stableValue(value));
}

export function sha256(value) {
  return crypto.createHash('sha256').update(typeof value === 'string' ? value : stableStringify(value)).digest('hex');
}

export function deterministicId(prefix, payload, length = 24) {
  return `${prefix}_${sha256(payload).slice(0, length)}`;
}

export function normalizeStructuralClaim(claim) {
  if (!claim || typeof claim !== 'object' || Array.isArray(claim)) throw new Error('structural_claim must be an object');
  const unexpected = Object.keys(claim).filter((key) => !STRUCTURAL_FIELDS.includes(key));
  if (unexpected.length) throw new Error(`Unsupported structural fields: ${unexpected.join(', ')}`);
  if (typeof claim.kind !== 'string' || !claim.kind.trim()) throw new Error('structural_claim.kind is required');
  const normalized = {
    kind: claim.kind.trim().toUpperCase(),
    dim: Number(claim.dim ?? 0),
    order: Number(claim.order ?? 0),
    sym: claim.sym ?? null,
    sq: claim.sq ?? null,
    anti: claim.anti ?? null,
    mult: Number(claim.mult ?? 1),
    bc: claim.bc ?? null,
    dual: Number(claim.dual ?? 0),
    occ: claim.occ ?? null,
  };
  if (!Number.isInteger(normalized.dim) || normalized.dim < 0) throw new Error('dim must be a non-negative integer');
  if (!Number.isInteger(normalized.order) || normalized.order < 0) throw new Error('order must be a non-negative integer');
  if (!Number.isInteger(normalized.mult) || normalized.mult < 1) throw new Error('mult must be a positive integer');
  if (![0, 1].includes(normalized.dual)) throw new Error('dual must be 0 or 1; self-duality is not a structural state');
  return normalized;
}

export function structuralSignature(record) {
  return normalizeStructuralClaim({
    kind: record.kind,
    dim: record.dim,
    order: record.order ?? record.recurrence_order,
    sym: record.sym ?? record.symmetry,
    sq: record.sq,
    anti: record.anti,
    mult: record.mult ?? record.multiplicity,
    bc: record.bc ?? record.boundary_condition,
    dual: record.dual,
    occ: record.occ ?? record.occupancy,
  });
}

export function structuralHash(record) {
  return sha256(structuralSignature(record));
}

export function eventIdentity(event) {
  const inputs = event.operator === 'op_product' ? [...event.inputs].sort() : [...event.inputs];
  const inputHashes = event.operator === 'op_product'
    ? [...event.input_structural_hashes].sort()
    : [...event.input_structural_hashes];
  return {
    operator: event.operator,
    operator_version: event.operator_version,
    inputs,
    output: event.output,
    parameters: event.parameters ?? {},
    level: Number(event.level),
    input_structural_hashes: inputHashes,
    output_structural_hash: event.output_structural_hash,
  };
}

export function eventHash(event) {
  return sha256(eventIdentity(event));
}

export function trueConfluences(events) {
  const byOutput = new Map();
  for (const event of events) {
    if (!byOutput.has(event.output)) byOutput.set(event.output, new Set());
    byOutput.get(event.output).add(event.event_hash ?? eventHash(event));
  }
  return [...byOutput.entries()]
    .filter(([, identities]) => identities.size >= 2)
    .map(([output, identities]) => ({ output, derivation_event_count: identities.size }))
    .sort((a, b) => a.output.localeCompare(b.output));
}

export function normalizationInput(candidate, evidence) {
  return stableValue({
    candidate: {
      id: candidate.id,
      domain: candidate.domain,
      name: candidate.name,
      formal_statement: candidate.formal_statement,
      uncertainties: candidate.uncertainties ?? [],
    },
    evidence: evidence.map((item) => ({
      id: item.id,
      source_type: item.source_type,
      source_ref: item.source_ref,
      fact: item.fact,
      quality: item.quality,
      content_hash: item.content_hash,
    })),
    allowed_structural_fields: STRUCTURAL_FIELDS,
    forbidden_inputs: ['other_normalization', 'hidden_target', 'generator_output', 'catalog_match'],
  });
}

export function adjudicateNormalizations(gpt, claude, proposedJudge) {
  const allowedIds = new Set([gpt.id, claude.id]);
  const sameClaim = stableStringify(normalizeStructuralClaim(gpt.structural_claim))
    === stableStringify(normalizeStructuralClaim(claude.structural_claim));
  if (!sameClaim) {
    return {
      verdict: 'AMBIGUOUS',
      reason: 'Independent normalizers disagree; the candidate is disputed.',
      blocking_items: ['NORMALIZATION_DISAGREEMENT'],
      selected_normalization_id: null,
    };
  }
  if (!proposedJudge || !JUDGE_VERDICTS.includes(proposedJudge.verdict)) throw new Error('Judge returned an unsupported verdict');
  const selected = proposedJudge.selected_normalization_id ?? null;
  if (selected && !allowedIds.has(selected)) throw new Error('Judge attempted to invent a third normalization');
  if (proposedJudge.verdict === 'ACCEPT_NORMALIZATION' && !selected) throw new Error('Accepted adjudication must select one supplied normalization');
  return {
    verdict: proposedJudge.verdict,
    reason: proposedJudge.reason,
    blocking_items: proposedJudge.blocking_items ?? [],
    selected_normalization_id: proposedJudge.verdict === 'ACCEPT_NORMALIZATION' ? selected : null,
  };
}

export function crossDomainMatches(interpretations, structures) {
  const structureByKey = new Map(structures.map((item) => [`${item.generation_id}:${item.id}`, item]));
  const byHash = new Map();
  for (const interpretation of interpretations) {
    const structure = structureByKey.get(`${interpretation.generation_id}:${interpretation.structure_id}`);
    if (!structure) continue;
    if (!byHash.has(structure.structural_hash)) byHash.set(structure.structural_hash, []);
    byHash.get(structure.structural_hash).push({ ...interpretation, structural_hash: structure.structural_hash });
  }
  return [...byHash.entries()].flatMap(([hash, occurrences]) => {
    const domains = [...new Set(occurrences.map((item) => item.domain))].sort();
    return domains.length >= 2 ? [{ structural_hash: hash, domains, occurrences, verdict: 'STRUCTURAL_MATCH', same_mechanism: 'NOT_EVALUATED' }] : [];
  });
}

