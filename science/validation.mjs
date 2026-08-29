import {
  deterministicId,
  eventHash,
  SELF_DUALITY,
  stableStringify,
  structuralHash,
  structuralSignature,
  trueConfluences,
} from './core.mjs';

export const VALIDATOR_VERSION = 'science-validator-v1.0.0';

export function validateGenerationPayload(generation, structures, events) {
  const errors = [];
  const ids = new Set();
  const hashes = new Set();
  const signatures = new Set();
  const byId = new Map();

  for (const structure of structures) {
    const signature = structuralSignature(structure);
    const hash = structuralHash(structure);
    const signatureText = stableStringify(signature);
    if (structure.generation_id !== generation.id) errors.push(`structure ${structure.id}: wrong generation`);
    if (ids.has(structure.id)) errors.push(`duplicate structure id ${structure.id}`);
    if (hashes.has(hash)) errors.push(`duplicate structural hash ${hash}`);
    if (signatures.has(signatureText)) errors.push(`duplicate structural signature ${signatureText}`);
    if (structure.structural_hash !== hash) errors.push(`structure ${structure.id}: structural hash mismatch`);
    if (structure.id !== deterministicId('str', hash)) errors.push(`structure ${structure.id}: nondeterministic id`);
    if (Number(structure.dual) === 2) errors.push(`structure ${structure.id}: asserted self-duality is forbidden`);
    ids.add(structure.id); hashes.add(hash); signatures.add(signatureText); byId.set(structure.id, structure);
  }

  const eventIds = new Set();
  const eventHashes = new Set();
  const generatedOutputs = new Set();
  let crossOrderFiberViolations = 0;
  let mixedDualProductViolations = 0;
  let mixedDualFiberViolations = 0;
  let selfTransitions = 0;
  let danglingInputs = 0;
  let danglingOutputs = 0;

  for (const event of events) {
    if (event.generation_id !== generation.id) errors.push(`event ${event.id}: wrong generation`);
    const computedHash = eventHash(event);
    if (event.event_hash !== computedHash) errors.push(`event ${event.id}: event hash mismatch`);
    if (event.id !== deterministicId('dev', computedHash)) errors.push(`event ${event.id}: nondeterministic id`);
    if (eventIds.has(event.id)) errors.push(`duplicate derivation id ${event.id}`);
    if (eventHashes.has(computedHash)) errors.push(`duplicate derivation identity ${computedHash}`);
    eventIds.add(event.id); eventHashes.add(computedHash);

    const output = byId.get(event.output);
    if (!output) { danglingOutputs += 1; continue; }
    generatedOutputs.add(event.output);
    if (event.output_structural_hash !== output.structural_hash) errors.push(`event ${event.id}: output hash mismatch`);
    const inputs = event.inputs.map((id) => byId.get(id));
    danglingInputs += inputs.filter((item) => !item).length;
    const presentInputs = inputs.filter(Boolean);
    const expectedHashes = presentInputs.map((item) => item.structural_hash);
    const storedHashes = event.input_structural_hashes;
    const comparableExpected = event.operator === 'op_product' ? [...expectedHashes].sort() : expectedHashes;
    const comparableStored = event.operator === 'op_product' ? [...storedHashes].sort() : storedHashes;
    if (stableStringify(comparableExpected) !== stableStringify(comparableStored)) errors.push(`event ${event.id}: input hash mismatch`);
    if (event.inputs.includes(event.output)) selfTransitions += 1;
    if (event.operator === 'op_fiber' && new Set(presentInputs.map((item) => Number(item.recurrence_order))).size > 1) crossOrderFiberViolations += 1;
    if (event.operator === 'op_product' && new Set(presentInputs.map((item) => Number(item.dual))).size > 1) mixedDualProductViolations += 1;
    if (event.operator === 'op_fiber' && new Set(presentInputs.map((item) => Number(item.dual))).size > 1) mixedDualFiberViolations += 1;
  }

  for (const structure of structures) {
    if (structure.lifecycle === 'ADMITTED' && generatedOutputs.has(structure.id)) errors.push(`admitted seed ${structure.id} has a derivation event`);
    if (structure.lifecycle === 'GENERABLE' && !generatedOutputs.has(structure.id)) errors.push(`generated structure ${structure.id} is not traceable`);
  }
  if (danglingInputs) errors.push(`${danglingInputs} dangling derivation inputs`);
  if (danglingOutputs) errors.push(`${danglingOutputs} dangling derivation outputs`);
  if (selfTransitions) errors.push(`${selfTransitions} idempotent self transitions`);
  if (crossOrderFiberViolations) errors.push(`${crossOrderFiberViolations} cross-order fiber events`);
  if (mixedDualProductViolations) errors.push(`${mixedDualProductViolations} mixed-dual product events`);
  if (mixedDualFiberViolations) errors.push(`${mixedDualFiberViolations} mixed-dual fiber events`);

  const confluences = trueConfluences(events);
  const counts = {
    structures: structures.length,
    admitted: structures.filter((item) => item.lifecycle === 'ADMITTED').length,
    generable: structures.filter((item) => item.lifecycle === 'GENERABLE').length,
    derivation_events: events.length,
    true_derivational_confluences: confluences.length,
  };
  if (Number(generation.node_count) !== counts.structures) errors.push('stored node_count mismatch');
  if (Number(generation.derivation_event_count) !== counts.derivation_events) errors.push('stored derivation_event_count mismatch');
  if (Number(generation.true_confluence_count) !== counts.true_derivational_confluences) errors.push('stored true_confluence_count mismatch');

  return {
    validator_version: VALIDATOR_VERSION,
    clean: errors.length === 0,
    errors,
    counts,
    integrity: {
      duplicate_structure_ids: structures.length - ids.size,
      duplicate_structural_hashes: structures.length - hashes.size,
      dangling_derivation_inputs: danglingInputs,
      dangling_derivation_outputs: danglingOutputs,
      idempotent_self_transitions: selfTransitions,
      cross_order_fiber_violations: crossOrderFiberViolations,
      mixed_dual_product_violations: mixedDualProductViolations,
      mixed_dual_fiber_violations: mixedDualFiberViolations,
      unverified_selfduality_claims: structures.filter((item) => Number(item.dual) === 2).length,
    },
    methodology: {
      structure_derivation_interpretation_separate: true,
      confluence_definition: '>=2 distinct DerivationEvent.event_hash values produce one structure',
      binary_input_arity_is_confluence: false,
      self_duality: SELF_DUALITY,
      maxdim: { value: generation.maxdim, role: 'EXPERIMENT_PARAMETER' },
    },
    true_confluences: confluences,
  };
}
