import { normalizeStructuralClaim, stableStringify } from './core.mjs';

// Independent structural verifier for this exact Python grammar. This module
// never generates candidates or modifies the physics-blind kernel. A changed
// grammar must receive a reviewed verifier and a new source hash.
export const REPLAY_GRAMMAR_SHA256 = 'afd52bc69b014d418826c400d2eb5e159ca41fb3e60fee68f8da90dcf18e89da';
export const REPLAY_OPERATOR_VERSION = `ckk-grammar-${REPLAY_GRAMMAR_SHA256.slice(0, 12)}`;
const st = (kind, fields = {}) => normalizeStructuralClaim({ kind, ...fields });
const carries = (s) => ({ dim: s.dim, order: s.order, sym: s.sym,
  mult: s.mult, bc: s.bc, dual: s.dual, occ: s.occ });
const is = (s, ...kinds) => kinds.includes(s.kind);
const compatible = (a, b) => a.sym === b.sym && a.bc === b.bc
  && a.order === b.order && a.dual === b.dual;

export const CANONICAL_SEEDS = Object.freeze([
  ...[0, 2, 3, 4].map((order) => st('RECURRENCE', { order })),
  ...[false, true].flatMap((anti) => [1, -1].map((sq) => st('SYMMETRY', { sq, anti }))),
  st('CARRIER', { occ: 1 }), st('CARRIER', { occ: -1 }),
].map(Object.freeze));
const seedKeys = new Set(CANONICAL_SEEDS.map(stableStringify));
export const isCanonicalSeed = (signature) => seedKeys.has(stableStringify(signature));

const unary = {
  op_close: (s) => s.kind === 'RECURRENCE' ? st('CYCLE', { dim: 1, order: s.order }) : null,
  op_winding: (s) => is(s, 'CYCLE', 'PRODUCT', 'BUNDLE') ? st('INTEGER', carries(s)) : null,
  op_boundary: (s) => is(s, 'PRODUCT', 'BUNDLE')
    ? st('BOUNDARY', { ...carries(s), dim: Math.max(s.dim - 1, 0) }) : null,
  op_weight: (s) => is(s, 'CYCLE', 'PRODUCT', 'BUNDLE') ? st('WEIGHT', carries(s)) : null,
  op_filter: (s) => s.kind === 'WEIGHT' ? st('FILTER', carries(s)) : null,
  op_dual: (s) => is(s, 'CYCLE', 'PRODUCT', 'BUNDLE', 'INTEGER', 'WEIGHT') && [0, 1].includes(s.dual)
    ? st(s.kind, { ...carries(s), dual: 1 - s.dual }) : null,
  // The Python operator intentionally also admits the finite CARRIER seed.
  op_fill: (s) => s.occ !== null && s.occ >= 0 && [1, 2].includes(s.mult)
    ? st('INTEGER', { ...carries(s), mult: s.occ * s.mult }) : null,
};
const binary = {
  op_product: (a, b) => is(a, 'CYCLE', 'PRODUCT') && is(b, 'CYCLE', 'PRODUCT') && compatible(a, b)
    ? st('PRODUCT', { ...carries(a), dim: a.dim + b.dim, mult: Math.max(a.mult, b.mult),
      occ: a.occ === b.occ ? a.occ : null }) : null,
  op_fiber: (base, fib) => fib.kind === 'CYCLE' && is(base, 'CYCLE', 'PRODUCT', 'BOUNDARY')
    && compatible(base, fib) ? st('BUNDLE', { ...carries(base),
      mult: Math.max(base.mult, fib.mult), occ: fib.occ }) : null,
  op_degenerate: (s, sym) => {
    if (sym.kind !== 'SYMMETRY' || !sym.anti || !is(s, 'CYCLE', 'PRODUCT', 'BUNDLE', 'WEIGHT')
      || s.mult !== 1 || !isCanonicalSeed(sym)) return null;
    // Python takes the canonical seed's label. Reconstruct it from the pinned
    // seed table; arbitrary labels from interpretation records are never used.
    return st(s.kind, { ...carries(s), sym: sym.sq === -1 ? 'S-a' : 'S+a',
      mult: sym.sq === -1 ? 2 : 1 });
  },
  op_exclude: (s, carrier) => carrier.kind === 'CARRIER'
    && is(s, 'CYCLE', 'PRODUCT', 'BUNDLE', 'INTEGER', 'WEIGHT') && s.occ === null
    ? st(s.kind, { ...carries(s), occ: carrier.occ }) : null,
};

export const REPLAY_OPERATORS = Object.freeze([...Object.keys(unary), ...Object.keys(binary)]);

export function replayDerivation(event, inputs) {
  const fn = Object.hasOwn(unary, event.operator) ? unary[event.operator]
    : Object.hasOwn(binary, event.operator) ? binary[event.operator] : null;
  if (!fn) throw new Error(`unregistered operator ${event.operator}`);
  if (event.operator_version !== REPLAY_OPERATOR_VERSION) throw new Error('unsupported operator version');
  const arity = Object.hasOwn(unary, event.operator) ? 1 : 2;
  if (inputs.length !== arity) throw new Error(`operator requires ${arity} inputs`);
  if (stableStringify(event.parameters) !== stableStringify({ arity })) {
    throw new Error('unsupported operator parameters or arity');
  }
  const result = fn(...inputs);
  if (!result) throw new Error('operator preconditions do not hold');
  return result;
}
