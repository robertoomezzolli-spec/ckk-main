import {
  deterministicId,
  EVENT_IDENTITY_VERSION,
  eventHash,
  SELF_DUALITY,
  stableStringify,
  structuralHash,
  structuralSignature,
  trueConfluences,
} from './core.mjs';
import { isCanonicalSeed, replayDerivation, REPLAY_GRAMMAR_SHA256 } from './replay.mjs';

export const VALIDATOR_VERSION = 'science-validator-v2.0.0';

export function validateGenerationPayload(generation, structures, events) {
  const errors = [];
  const ids = new Set();
  const hashes = new Set();
  const signatures = new Set();
  const byId = new Map();
  const bySignature = new Map();
  if (generation.grammar_hash != null && generation.grammar_hash !== REPLAY_GRAMMAR_SHA256) {
    errors.push('generation grammar hash has no supported replay verifier');
  }

  for (const structure of structures) {
    let signature;
    try { signature = structuralSignature(structure); }
    catch (error) { errors.push(`structure ${structure?.id}: ${error.message}`); continue; }
    const hash = structuralHash(structure);
    const signatureText = stableStringify(signature);
    if (structure.generation_id !== generation.id) errors.push(`structure ${structure.id}: wrong generation`);
    if (ids.has(structure.id)) errors.push(`duplicate structure id ${structure.id}`);
    if (hashes.has(hash)) errors.push(`duplicate structural hash ${hash}`);
    if (signatures.has(signatureText)) errors.push(`duplicate structural signature ${signatureText}`);
    if (structure.structural_hash !== hash) errors.push(`structure ${structure.id}: structural hash mismatch`);
    if (structure.id !== deterministicId('str', hash)) errors.push(`structure ${structure.id}: nondeterministic id`);
    if (stableStringify(structure.structural_sig) !== signatureText) errors.push(`structure ${structure.id}: stored signature mismatch`);
    if (!['ADMITTED', 'GENERABLE'].includes(structure.lifecycle)) errors.push(`structure ${structure.id}: invalid lifecycle`);
    if (structure.lifecycle === 'ADMITTED' && !isCanonicalSeed(signature)) errors.push(`structure ${structure.id}: seed is not admitted by the pinned grammar`);
    if (Number(structure.dual) === 2) errors.push(`structure ${structure.id}: asserted self-duality is forbidden`);
    ids.add(structure.id); hashes.add(hash); signatures.add(signatureText); byId.set(structure.id, structure);
    bySignature.set(structure.id, signature);
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
  let invalidDerivationSteps = 0;
  const identityEvents = [];
  const replayedEvents = [];

  for (const event of events) {
    if (event.generation_id !== generation.id) errors.push(`event ${event.id}: wrong generation`);
    let computedHash;
    try { computedHash = eventHash(event); }
    catch (error) { errors.push(`event ${event?.id}: ${error.message}`); invalidDerivationSteps += 1; continue; }
    identityEvents.push(event);
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
    // Verify each hash belongs to the input at the same position before any
    // commutative normalization. Swapping hashes alone must not pass.
    if (stableStringify(expectedHashes) !== stableStringify(storedHashes)) errors.push(`event ${event.id}: input hash mismatch`);
    if (event.inputs.includes(event.output)) selfTransitions += 1;
    if (event.operator === 'op_fiber' && new Set(presentInputs.map((item) => Number(item.recurrence_order))).size > 1) crossOrderFiberViolations += 1;
    if (event.operator === 'op_product' && new Set(presentInputs.map((item) => Number(item.dual))).size > 1) mixedDualProductViolations += 1;
    if (event.operator === 'op_fiber' && new Set(presentInputs.map((item) => Number(item.dual))).size > 1) mixedDualFiberViolations += 1;
    const level = Number(event.level);
    if (!Number.isSafeInteger(level) || level < 1
      || (generation.expansion_levels != null && level > Number(generation.expansion_levels))) {
      errors.push(`event ${event.id}: invalid observation level`);
      invalidDerivationSteps += 1;
      continue;
    }
    if (presentInputs.length !== inputs.length) continue;
    try {
      const result = replayDerivation(event, event.inputs.map((id) => bySignature.get(id)));
      if (stableStringify(result) !== stableStringify(bySignature.get(event.output))) {
        throw new Error('replayed output signature mismatch');
      }
      replayedEvents.push(event);
    } catch (error) {
      invalidDerivationSteps += 1;
      errors.push(`event ${event.id}: ${error.message}`);
    }
  }

  // A locally valid dual cycle alone is not a derivation from a seed. Require
  // every input of every replayed hyperedge to be available at an earlier
  // observation level. Alternative derivations may return to an older state.
  const reachable = new Map([...bySignature].filter(([id, sig]) =>
    byId.get(id).lifecycle === 'ADMITTED' && isCanonicalSeed(sig)).map(([id]) => [id, 0]));
  for (const event of [...replayedEvents].sort((a, b) => Number(a.level) - Number(b.level))) {
    if (!event.inputs.every((id) => reachable.has(id) && reachable.get(id) < Number(event.level))) {
      errors.push(`event ${event.id}: inputs are not derived before this observation level`);
      continue;
    }
    if (!reachable.has(event.output)) reachable.set(event.output, Number(event.level));
  }
  const unreachable = structures.filter((s) => s.lifecycle === 'GENERABLE' && !reachable.has(s.id));
  if (unreachable.length) errors.push(`${unreachable.length} generated structures lack a seed-rooted replay`);

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

  const confluences = trueConfluences(identityEvents);
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
      invalid_derivation_steps: invalidDerivationSteps,
      replayed_derivation_events: replayedEvents.length,
      unreachable_generated_structures: unreachable.length,
      unverified_selfduality_claims: structures.filter((item) => Number(item.dual) === 2).length,
    },
    methodology: {
      structure_derivation_interpretation_separate: true,
      event_identity_version: EVENT_IDENTITY_VERSION,
      confluence_definition: '>=2 distinct canonical operator applications produce one structure; observation level excluded',
      replay_grammar_sha256: REPLAY_GRAMMAR_SHA256,
      every_binary_input_required: true,
      binary_input_arity_is_confluence: false,
      self_duality: SELF_DUALITY,
      maxdim: { value: generation.maxdim, role: 'EXPERIMENT_PARAMETER' },
    },
    true_confluences: confluences,
  };
}
