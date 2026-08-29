export const STATUS_INFO = Object.freeze({
  KNOWN: 'Matches a structure intentionally present in the reference catalog.',
  REDISCOVERED: 'Generated without the target label and subsequently matched to a held-out or catalog structure.',
  VARIANT: 'Close structural relative of a catalog entry, differing in one or more generated properties.',
  UNMATCHED: 'Valid grammar output for which no catalog match is currently assigned.',
});

const PROFILES = Object.freeze({
  'CYCLE:1': { description: 'A closed one-dimensional phase or recurrence structure. The physical names shown here are catalog annotations applied after generation.', formula: 'φ ∼ φ + 2π' },
  'BOUNDARY:1': { description: 'A generated one-dimensional boundary structure matched to a boundary realization in the reference catalog.', formula: '∂X' },
  'BUNDLE:1': { description: 'A one-dimensional base/fiber structure whose catalog realizations include phase transport and order-parameter bundles.', formula: 'hol(C) = exp(i ∮ᴄ A)' },
  'INTEGER:1': { description: 'Closed phase with an integer winding number. The same mathematical closure structure occurs in several known physical systems.', formula: '1/(2π) ∮ᴄ dφ = n,    n ∈ ℤ' },
  'WEIGHT:1': { description: 'A generated phase structure equipped with a weight, matched in the catalog to interference-intensity realizations.', formula: 'I = |Σⱼ Aⱼ eⁱᶠʲ|²' },
  'FILTER:1': { description: 'A weighted structure followed by a filter operation, with catalog matches to transmission or envelope effects.', formula: 'Iₒᵤₜ = |T|² Iᵢₙ' },
  'PRODUCT:2': { description: 'A generated two-dimensional product structure, catalog-matched to two independent periodic directions.', formula: 'T² = S¹ × S¹' },
  'BUNDLE:2': { description: 'A two-dimensional bundle signature. Berry or monopole language belongs to the catalog annotation, not to the generator.', formula: 'A = i⟨u|du⟩,    F = dA' },
  'INTEGER:2': { description: 'A two-dimensional structure carrying an integer closure index, matched to first-characteristic-number realizations.', formula: 'C₁ = 1/(2π) ∫M₂ F ∈ ℤ' },
  'BUNDLE:3': { description: 'A generated three-dimensional bundle signature subsequently matched to a catalogued topological response structure.', formula: 'C⃗ = (C₁ˣʸ, C₁ʸᶻ, C₁ᶻˣ)' },
  'INTEGER:3': { description: 'A generated three-dimensional integer signature matched to a quantized catalog invariant.', formula: 'k ∈ ℤ' },
  'PRODUCT:4': { description: 'A four-dimensional product structure generated without the target label and subsequently matched to the second-Chern catalog entry.', formula: 'C₂ = 1/(8π²) ∫M₄ Tr(F ∧ F) ∈ ℤ' },
  'INTEGER:4': { description: 'A four-dimensional integer signature matched after generation to a catalogued second-characteristic-number sector.', formula: 'Q = 1/(8π²) ∫M₄ Tr(F ∧ F) ∈ ℤ' },
});

const REALIZATION_NAMES = Object.freeze({
  'Bohr-Sommerfeld': 'Bohr–Sommerfeld', Flussquantisierung: 'Flux quantization',
  'Superfluid-Zirkulation': 'Superfluid circulation', 'Teilchen im Ring': 'Particle on a ring',
  Doppelspalt: 'Double slit', '4D-QHE / zweite Chernzahl': '4D quantum Hall / second Chern number',
  'euklidische Zeit am Horizont': 'Euclidean time at the horizon', 'U(1)-Phase': 'U(1) phase',
  'Aharonov-Bohm-Buendel': 'Aharonov–Bohm bundle', 'Ordnungsparameter am Ring': 'Order parameter on a ring',
});

const OPERATION_NAMES = Object.freeze({
  op_close: 'Closure', op_winding: 'Winding / closure count', op_product: 'Product',
  op_fiber: 'Fiber composition', op_boundary: 'Boundary', op_weight: 'Weighting',
  op_filter: 'Filtering', op_dual: 'Dual transformation', op_degenerate: 'Degeneracy',
  op_exclude: 'Exclusion', op_fill: 'Filling',
});

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const raw = (node) => node?.signature?.snapshot_node || {};
function factor(node) { const value = raw(node).factor; if (value === '2pi') return '2π'; if (value === 'pi') return 'π'; return value && value !== '—' ? String(value) : '—'; }
const present = (value) => value == null || value === 'None' ? 'none' : String(value);
function realizations(node) { return (raw(node).phys || []).filter((item) => !String(item).startsWith('Variante von:')).map((item) => REALIZATION_NAMES[item] || item); }
function sameCore(a, b) { return a.kind === b.kind && Number(a.dim) === Number(b.dim) && Number(a.recurrence_order || 0) === Number(b.recurrence_order || 0) && present(a.symmetry) === present(b.symmetry) && Number(a.multiplicity || 1) === Number(b.multiplicity || 1) && present(a.boundary_condition) === present(b.boundary_condition) && present(a.occupancy) === present(b.occupancy) && factor(a) === factor(b); }

function dualPartner(node, graph) {
  if (Number(node.dual || 0) !== 1) return null;
  const candidates = graph.nodes.filter((candidate) => Number(candidate.dual || 0) === 0 && sameCore(node, candidate));
  const incoming = new Set(graph.edges.filter((edge) => edge.target_id === node.id).map((edge) => edge.source_id));
  return candidates.sort((a, b) => Number(incoming.has(b.id)) - Number(incoming.has(a.id)) || Math.abs(Number(a.depth) - Number(node.depth) + 1) - Math.abs(Number(b.depth) - Number(node.depth) + 1) || String(a.id).localeCompare(String(b.id)))[0] || null;
}

function compatibleOperation(source, target) {
  if (source.kind === 'RECURRENCE' && target.kind === 'CYCLE') return 'op_close';
  if (['CYCLE', 'PRODUCT', 'BUNDLE'].includes(source.kind) && target.kind === 'INTEGER') return 'op_winding';
  if (['PRODUCT', 'BUNDLE'].includes(source.kind) && target.kind === 'BOUNDARY') return 'op_boundary';
  if (['CYCLE', 'PRODUCT', 'BUNDLE'].includes(source.kind) && target.kind === 'WEIGHT') return 'op_weight';
  if (source.kind === 'WEIGHT' && target.kind === 'FILTER') return 'op_filter';
  if (source.kind === target.kind && Number(source.dual || 0) === 0 && Number(target.dual || 0) === 1) return 'op_dual';
  if (['CYCLE', 'PRODUCT'].includes(source.kind) && target.kind === 'PRODUCT') return 'op_product';
  if (['CYCLE', 'PRODUCT', 'BOUNDARY'].includes(source.kind) && target.kind === 'BUNDLE') return 'op_fiber';
  return null;
}

function derivations(node, graph) {
  return graph.edges.filter((edge) => edge.target_id === node.id).map((edge) => {
    const source = graph.nodes.find((candidate) => candidate.id === edge.source_id); if (!source) return null;
    const explicit = String(edge.operator || '').startsWith('op_'); const operation = explicit ? edge.operator : compatibleOperation(source, node);
    const score = (Number(source.depth) < Number(node.depth) ? 4 : 0) + (operation ? 2 : 0) + (Number(source.dual || 0) <= Number(node.dual || 0) ? 1 : 0);
    return { edge, source, operation, explicit, score };
  }).filter(Boolean).sort((a, b) => b.score - a.score || Number(a.source.depth) - Number(b.source.depth) || String(a.source.id).localeCompare(String(b.source.id))).slice(0, 4);
}

function statusTitle(node) { if (node.verdict === 'UNMATCHED') return 'UNMATCHED STRUCTURE'; if (node.verdict === 'VARIANT' && !node.label) return 'STRUCTURAL VARIANT'; return node.label || `${node.kind} structure`; }
function structuralFormula(node) { const properties = [factor(node) !== '—' ? factor(node) : null, `m=${Number(node.multiplicity || 1)}`, Number(node.dual || 0) === 1 ? 'dual=transformed' : 'dual=original'].filter(Boolean).join(', '); return `X = ${node.kind}[d=${node.dim}](${properties})`; }

export function buildPhysicsCardModel(node, graph) {
  const status = node.verdict || 'UNMATCHED';
  const profile = ['KNOWN', 'REDISCOVERED'].includes(status) ? PROFILES[`${node.kind}:${Number(node.dim)}`] || null : null;
  const cluster = (graph.duality_clusters || []).find((item) => item.target_node_id === node.id) || null;
  return { node, status, title: statusTitle(node), subtitle: status === 'UNMATCHED' ? 'Generated structure with no catalog match' : `${status} · d${node.dim} · depth ${node.depth}`, description: profile?.description || (status === 'UNMATCHED' ? 'CKK generated this structure from the grammar, but the current reference catalog contains no assigned physical match with this signature.' : STATUS_INFO[status] || 'Generated structural state.'), formula: profile?.formula || structuralFormula(node), formulaSource: profile ? 'PHYSICS ANNOTATION' : 'GENERATED STRUCTURE', formulaCaveat: profile ? 'This formula describes the catalog interpretation. It did not determine the generated topology.' : 'Structural notation only; no physical identification is implied.', realizations: realizations(node), derivations: derivations(node, graph), partner: dualPartner(node, graph), cluster, factor: factor(node), selfDuality: graph.methodology?.self_duality || { assessment: 'NOT_EVALUATED', equivalence_relation: null } };
}

function renderDerivation(item, target) {
  const transition = `${item.source.kind} → ${target.kind}`; const operationName = item.operation ? OPERATION_NAMES[item.operation] || item.operation : 'Recorded structural transition';
  const provenance = item.explicit ? `The export records ${item.operation} as the generating operation.` : item.operation ? `The structural change is compatible with ${item.operation}; the sealed legacy edge does not retain its original operator label.` : 'The sealed legacy snapshot records this relation, but no original operator label is available.';
  return `<button class="derivation path-link" data-path-source="${esc(item.source.id)}" data-path-target="${esc(target.id)}"><span class="derivation-flow">${esc(transition)}</span><strong>${esc(operationName)}${item.explicit ? '' : ' · compatible'}</strong><small>${esc(provenance)}</small></button>`;
}

function renderDuality(model) {
  const transformed = Number(model.node.dual || 0) === 1; const partner = model.partner;
  return `<section class="card-section duality-section"><div class="section-label">DUALITY</div><h4>${transformed ? 'Dual transformed' : 'Original dual state'}</h4><div class="equation">${transformed ? 'X★ = D(X)' : 'X'}</div><p>${transformed ? 'This node is the dual-transformed counterpart of another structure. This does not mean that X is self-dual.' : 'No dual transformation is asserted for this node.'}</p>${transformed ? `<div class="fact-grid"><span>Dual partner</span><span>${partner ? `<button class="text-link node-link" data-node-id="${esc(partner.id)}">${esc(partner.label || `${partner.kind} d${partner.dim}`)} →</button>` : 'not uniquely resolved'}</span><span>Transformation</span><span>op_dual-compatible</span><span>Involution rule</span><span>D(D(X)) = X</span></div>` : ''}<div class="self-duality-box"><strong>Self-duality</strong><div class="equation small">D(X) ≡? X</div><span class="verdict-chip neutral">${esc(model.selfDuality.assessment || 'NOT_EVALUATED')}</span><p>No equivalence criterion has been defined. No self-duality claim is made.</p></div></section>`;
}

export function renderPhysicsCard(node, graph) {
  const model = buildPhysicsCardModel(node, graph);
  const technical = { id: node.id, kind: node.kind, dimension: Number(node.dim), operator_depth: Number(node.depth), recurrence_order: Number(node.recurrence_order || 0), factor: model.factor, symmetry: present(node.symmetry), multiplicity: Number(node.multiplicity || 1), boundary_condition: present(node.boundary_condition), occupancy: present(node.occupancy), dual_state: Number(node.dual || 0) === 1 ? 'transformed' : 'original', lifecycle: node.lifecycle, verdict: model.status, paths: Number(node.paths || 1) };
  const isGenerated = node.lifecycle === 'GENERABLE'; const catalogMatch = ['KNOWN', 'REDISCOVERED'].includes(model.status) ? 'MATCHED' : model.status === 'VARIANT' ? 'RELATED' : 'NONE';
  const pathNote = model.cluster ? `${model.cluster.branches.length} independently seed-rooted branches converge on this signature.` : Number(node.paths || 1) > 1 ? `${node.paths} recorded routes reach this signature. Path multiplicity alone does not prove independent seed families.` : 'One recorded route reaches this signature.';
  return `<article class="physics-card status-${esc(model.status.toLowerCase())}"><header class="card-header"><div class="section-label">${model.status === 'UNMATCHED' ? 'GENERATED STRUCTURE' : 'PHYSICS CARD'}</div><h3>${esc(model.title)}</h3><div class="card-subtitle"><span class="verdict-chip ${esc(model.status.toLowerCase())}">${esc(model.status)}</span> ${esc(model.subtitle)}</div><p class="meaning">${esc(model.description)}</p></header><section class="formula-section ${model.formulaSource === 'PHYSICS ANNOTATION' ? 'annotation' : 'generated'}"><div class="section-label">${esc(model.formulaSource)}</div><div class="equation large">${esc(model.formula)}</div><small>${esc(model.formulaCaveat)}</small>${model.realizations.length ? `<div class="realizations"><strong>Known realizations</strong><p>${model.realizations.map(esc).join(' · ')}</p></div>` : ''}</section><section class="card-section"><div class="section-label">WHY IS THIS NODE HERE?</div>${model.derivations.length ? model.derivations.map((item) => renderDerivation(item, node)).join('') : '<p>No retained incoming transition is present; this may be an admitted seed or an orphaned legacy record.</p>'}<div class="fact-grid compact"><span>Generated independently of catalog labels</span><strong>${isGenerated ? 'YES' : 'SEED / ADMITTED'}</strong><span>Catalog match</span><strong>${catalogMatch}</strong><span>Recorded paths</span><strong>${Number(node.paths || 1)}</strong></div><p class="why-interesting"><strong>Why this is interesting</strong><br>${esc(pathNote)}</p></section>${renderDuality(model)}<section class="card-section status-section"><div class="section-label">STATUS</div><h4>${esc(model.status)}</h4><p>${esc(STATUS_INFO[model.status] || 'No status definition available.')}</p></section><details class="technical-signature"><summary>Technical signature</summary><div class="equation small">${esc(structuralFormula(node))}</div><pre>${esc(JSON.stringify(technical, null, 2))}</pre></details><button class="reset-card" data-reset-graph>Reset graph focus</button></article>`;
}

export function renderStatusGlossary() { return `<details class="status-glossary"><summary>Status key</summary>${Object.entries(STATUS_INFO).map(([status, explanation]) => `<div><span class="verdict-chip ${status.toLowerCase()}">${status}</span><p>${esc(explanation)}</p></div>`).join('')}</details>`; }
