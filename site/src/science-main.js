import './science.css';

const view = document.querySelector('#science-view');
const title = document.querySelector('#view-title');
const connection = document.querySelector('#connection-label');
const inspector = document.querySelector('#inspector');
const inspectorContent = document.querySelector('#inspector-content');
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
const route = location.pathname.replace(/^\/science\/?/, '').split('/')[0] || 'overview';
const titles = { overview: 'Scientific Overview', queue: 'Autonomous Candidate Queue', disputes: 'Normalization Disputes', failures: 'First-Class Failures', 'grammar-pressure': 'Grammar Pressure', generations: 'Immutable Generations', 'cross-domain': 'Cross-Domain Classes' };
const endpoints = { overview: 'overview', queue: 'candidates', disputes: 'disputes', failures: 'failures', 'grammar-pressure': 'grammar-pressure', generations: 'generations', 'cross-domain': 'cross-domain' };
let apiMode = 'LIVE_PREVIEW_BRANCH';

document.querySelectorAll('[data-route]').forEach((item) => item.classList.toggle('active', item.dataset.route === route));
title.textContent = titles[route] ?? 'Scientific Control Plane';

async function fetchJson(path) {
  const response = await fetch(`/api/science/${path}`, { headers: { accept: 'application/json' } });
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

async function loadData() {
  try {
    const payload = await fetchJson(endpoints[route] ?? 'overview');
    connection.textContent = 'PREVIEW DB LIVE';
    return payload;
  } catch (error) {
    const response = await fetch('/data/science-preview.json');
    if (!response.ok) throw error;
    const all = await response.json();
    apiMode = 'SEALED_PREVIEW_EXPORT';
    connection.textContent = 'SEALED PREVIEW EXPORT';
    return all[route];
  }
}

function pill(status) {
  const label = status ?? 'UNKNOWN';
  return `<span class="status ${escapeHtml(label)}">${escapeHtml(label.replaceAll('_', ' '))}</span>`;
}

function countRows(rows = []) {
  return rows.reduce((object, item) => ({ ...object, [item.status ?? item.code ?? item.role]: Number(item.count) }), {});
}

function renderOverview(data) {
  const generations = countRows(data.generation_status);
  const candidates = countRows(data.candidate_status);
  const failures = data.failure_status?.reduce((sum, item) => sum + Number(item.count), 0) ?? 0;
  return `
    <div class="hero-grid">
      <article class="hero-card"><span>SCIENTIFIC GENERATIONS</span><strong>${Object.values(generations).reduce((a, b) => a + b, 0)}</strong><small>${generations.SEALED ?? 0} SEALED · ${generations.VALIDATED ?? 0} VALIDATED</small></article>
      <article class="hero-card"><span>CANDIDATE PIPELINE</span><strong>${Object.values(candidates).reduce((a, b) => a + b, 0)}</strong><small>${candidates.SEALED ?? 0} COMPLETE · ${candidates.DISPUTED ?? 0} DISPUTED</small></article>
      <article class="hero-card alert"><span>OPEN FAILURES</span><strong>${failures}</strong><small>FAILURE IS SCIENTIFIC DATA</small></article>
      <article class="hero-card"><span>PUBLIC SCIENTIFIC</span><strong>${data.public_state?.active_generation_id ? '1' : '0'}</strong><small>${data.public_state?.active_generation_id ? 'SEALED + ELIGIBLE' : 'NO ELIGIBLE GENERATION'}</small></article>
    </div>
    <section class="panel pipeline-panel"><div class="section-head"><div><span class="eyebrow">AUTONOMOUS PIPELINE</span><h2>Evidence before generation</h2></div>${pill('FAIL_CLOSED')}</div>
      <div class="pipeline" data-testid="pipeline">
        ${['DISCOVER','SOURCE','CRITIQUE','NORMALIZE GPT','NORMALIZE CLAUDE','ADJUDICATE','FREEZE','GENERATE','MATCH','VALIDATE','SEAL'].map((step, index) => `<div><i>${String(index + 1).padStart(2, '0')}</i><b>${step}</b><small>${index < 7 ? 'LLM OUTSIDE CORE' : index === 7 ? 'NO LLM' : 'DETERMINISTIC'}</small></div>`).join('')}
      </div>
    </section>
    <div class="split-grid">
      <section class="panel"><div class="section-head"><div><span class="eyebrow">HISTORICAL MUSEUM</span><h2>Run 34 · untouched</h2></div>${pill('SEALED')}</div>
        <div class="metric-list"><span>Generation<b>${escapeHtml(data.historical_run34.generation_id)}</b></span><span>Structures<b>${data.historical_run34.nodes}</b></span><span>Edges<b>${data.historical_run34.edges}</b></span><span>Historical graph convergences<b>${data.historical_run34.historical_graph_confluences}</b></span><span>Self-duality<b>NOT EVALUATED</b></span></div>
      </section>
      <section class="panel"><div class="section-head"><div><span class="eyebrow">TRUTH BOUNDARY</span><h2>What agents cannot do</h2></div></div>
        <ul class="constraint-list"><li>Cannot mutate grammar</li><li>Cannot see hidden targets during normalization</li><li>Cannot publish to the Universe</li><li>Cannot invent a third adjudication</li><li>Cannot promote a grammar proposal</li></ul>
      </section>
    </div>`;
}

function renderQueue(data) {
  const rows = data.candidates ?? [];
  return `<section class="panel"><div class="section-head"><div><span class="eyebrow">${rows.length} RECORDS</span><h2>Candidate lifecycle</h2></div>${pill('DEDUPE_ACTIVE')}</div>
    ${rows.length ? `<div class="data-table"><div class="table-head"><span>Candidate</span><span>Domain</span><span>Evidence</span><span>Normalizers</span><span>Status</span></div>${rows.map((item) => `<button class="table-row" data-candidate="${escapeHtml(item.id)}"><span><b>${escapeHtml(item.name)}</b><small>${escapeHtml(item.id)}</small></span><span>${escapeHtml(item.domain)}</span><span>${item.evidence_count}</span><span>${item.normalization_count}/2</span><span>${pill(item.status)}</span></button>`).join('')}</div>` : empty('No candidates have entered the preview queue.')}</section>`;
}

function renderDisputes(data) {
  const rows = data.disputes ?? [];
  return `<section class="panel"><div class="section-head"><div><span class="eyebrow">INDEPENDENT NORMALIZATION</span><h2>GPT ↔ Claude disagreements</h2></div>${pill(rows.length ? 'DISPUTED' : 'NO_OPEN_DISPUTE')}</div>
  ${rows.length ? rows.map((item) => `<article class="dispute"><h3>${escapeHtml(item.candidate.name)}</h3><div class="comparison">${item.normalizations.map((normalization) => `<div><span>${escapeHtml(normalization.agent_role)}</span><pre>${escapeHtml(JSON.stringify(normalization.structural_claim, null, 2))}</pre></div>`).join('')}</div><p>Judge outcome: ${escapeHtml(item.adjudication?.verdict ?? 'PENDING')}</p></article>`).join('') : empty('Independent normalizers agree in the current preview cycle. This view stays empty rather than manufacturing a dispute.')}</section>`;
}

function renderFailures(data) {
  const rows = data.failures ?? [];
  return `<section class="panel"><div class="section-head"><div><span class="eyebrow">FAILURE IS FIRST-CLASS DATA</span><h2>Open structural limitations</h2></div>${pill(rows.length ? 'ATTENTION' : 'CLEAR')}</div>
    ${rows.length ? `<div class="failure-grid">${rows.map((item) => `<article><header>${pill(item.code)}<small>${escapeHtml(item.domain)}</small></header><h3>${escapeHtml(item.missing_distinction ?? 'UNCLASSIFIED')}</h3><p>${escapeHtml(item.details?.summary ?? item.details?.reason ?? 'See raw failure details.')}</p><details><summary>Raw evidence</summary><pre>${escapeHtml(JSON.stringify(item.details, null, 2))}</pre></details></article>`).join('')}</div>` : empty('No failures are stored. Absence is not proof of coverage.')}</section>`;
}

function renderGrammarPressure(data) {
  const groups = data.groups ?? [];
  return `<div class="split-grid pressure-layout"><section class="panel"><div class="section-head"><div><span class="eyebrow">AGGREGATED FAILURES</span><h2>Missing distinctions</h2></div>${pill('HUMAN_REVIEW_ONLY')}</div>
    ${groups.length ? groups.map((item) => `<article class="pressure"><strong>${item.failure_count}</strong><div><h3>${escapeHtml(item.missing_distinction)}</h3><p>${escapeHtml(item.domains.join(' · '))}</p></div></article>`).join('') : empty('No repeated missing distinction is established yet.')}</section>
    <section class="panel"><div class="section-head"><div><span class="eyebrow">PROPOSALS</span><h2>Never auto-activated</h2></div></div>${(data.proposals ?? []).length ? data.proposals.map((item) => `<article class="proposal"><h3>${escapeHtml(item.id)}</h3>${pill(item.status)}<p>${escapeHtml(item.missing_distinction)}</p></article>`).join('') : empty('No GrammarProposal has crossed the evidence threshold.')}</section></div>`;
}

function renderGenerations(data) {
  const rows = data.generations ?? [];
  return `<section class="panel"><div class="section-head"><div><span class="eyebrow">IMMUTABLE SNAPSHOTS</span><h2>Generation registry</h2></div>${pill('HASH_VERIFIED')}</div>
  ${rows.length ? `<div class="generation-grid">${rows.map((item) => `<button class="generation-card" data-generation="${escapeHtml(item.id)}"><header>${pill(item.status)}<small>${item.preview ? 'PREVIEW' : 'PRODUCTION'}</small></header><h3>${escapeHtml(item.id)}</h3><div><span>Structures<b>${item.node_count}</b></span><span>Events<b>${item.derivation_event_count}</b></span><span>True confluences<b>${item.true_confluence_count}</b></span></div><footer>MAXDIM ${item.maxdim} · LEVELS ${item.expansion_levels} · PUBLIC ${item.public_eligible ? 'YES' : 'NO'}</footer></button>`).join('')}</div>` : empty('No Scientific generation exists. Run 34 remains in the historical plane.')}</section>`;
}

function renderCrossDomain(data) {
  const rows = data.matches ?? [];
  return `<section class="panel"><div class="section-head"><div><span class="eyebrow">SHARED STRUCTURAL HASHES</span><h2>Cross-domain classes</h2></div>${pill('STRUCTURAL_MATCH_ONLY')}</div>
  ${rows.length ? rows.map((item) => `<article class="bridge"><code>${escapeHtml(item.structural_hash)}</code><h3>${escapeHtml(item.domains.join(' ↔ '))}</h3><p>Same mechanism: NOT EVALUATED</p></article>`).join('') : empty('No sealed Scientific structural hash currently occurs in two independently evidenced domains. No bridge is fabricated.')}</section>`;
}

function empty(message) { return `<div class="empty"><i>∅</i><h3>HONEST EMPTY STATE</h3><p>${escapeHtml(message)}</p></div>`; }

async function openGeneration(id) {
  const payload = await fetchJson(`generations/${id}`).catch(async () => {
    const all = await (await fetch('/data/science-preview.json')).json();
    return all.generation_details?.[id];
  });
  inspectorContent.innerHTML = `<span class="eyebrow">GENERATION INSPECTOR</span><h2>${escapeHtml(payload.generation.id)}</h2>
    <div class="inspector-facts"><span>Status<b>${escapeHtml(payload.generation.status)}</b></span><span>Grammar hash<b>${escapeHtml(payload.generation.grammar_hash)}</b></span><span>Seed hash<b>${escapeHtml(payload.generation.seed_set_hash)}</b></span><span>Self-duality<b>NOT EVALUATED</b></span></div>
    <h3>VALIDATION</h3><pre>${escapeHtml(JSON.stringify(payload.generation.validation_report, null, 2))}</pre>
    <h3>STRUCTURES · ${payload.structures.length}</h3><div class="structure-list">${payload.structures.map((item) => `<button data-structure="${escapeHtml(item.id)}" data-generation-id="${escapeHtml(id)}"><b>${escapeHtml(item.kind)} d${item.dim}</b><code>${escapeHtml(item.structural_hash.slice(0, 18))}…</code></button>`).join('')}</div>
    <h3>DERIVATION EVENTS · ${payload.derivation_events.length}</h3><pre>${escapeHtml(JSON.stringify(payload.derivation_events, null, 2))}</pre>`;
  inspector.scrollTop = 0;
  inspector.showModal();
  inspectorContent.querySelectorAll('[data-structure]').forEach((button) => button.onclick = () => openStructure(button.dataset.structure, button.dataset.generationId));
}

async function openStructure(id, generationId) {
  const payload = await fetchJson(`structures/${id}?generation=${encodeURIComponent(generationId)}`).catch(async () => {
    const all = await (await fetch('/data/science-preview.json')).json();
    return all.structure_details?.[`${generationId}:${id}`];
  });
  inspectorContent.innerHTML = `<span class="eyebrow">STRUCTURE INSPECTOR</span><h2>${escapeHtml(payload.structure.kind)} · d${payload.structure.dim}</h2>
    <div class="layer-stack"><article><span>STRUCTURE</span><pre>${escapeHtml(JSON.stringify(payload.structure.structural_sig, null, 2))}</pre></article><article><span>DERIVATION EVENTS</span><pre>${escapeHtml(JSON.stringify(payload.derivation_events, null, 2))}</pre></article><article><span>INTERPRETATIONS</span><pre>${escapeHtml(JSON.stringify(payload.interpretations, null, 2))}</pre></article></div>
    <h3>EVIDENCE + AGENT TRACE</h3><pre>${escapeHtml(JSON.stringify(payload.agent_trace, null, 2))}</pre>`;
  inspector.scrollTop = 0;
}

function bind() {
  view.querySelectorAll('[data-generation]').forEach((button) => button.onclick = () => openGeneration(button.dataset.generation));
}

document.querySelector('.dialog-close').onclick = () => inspector.close();
inspector.addEventListener('click', (event) => { if (event.target === inspector) inspector.close(); });

try {
  const data = await loadData();
  const renderers = { overview: renderOverview, queue: renderQueue, disputes: renderDisputes, failures: renderFailures, 'grammar-pressure': renderGrammarPressure, generations: renderGenerations, 'cross-domain': renderCrossDomain };
  view.innerHTML = (renderers[route] ?? renderOverview)(data);
  bind();
  window.__CKK_SCIENCE_READY__ = true;
  window.__CKK_SCIENCE_STATE__ = { route, apiMode, payload: data };
} catch (error) {
  connection.textContent = 'DATA UNAVAILABLE';
  view.innerHTML = `<div class="fatal"><span>FAIL CLOSED</span><h2>Scientific data could not be loaded.</h2><p>${escapeHtml(error.message)}</p><p>No fallback claims were generated.</p></div>`;
  window.__CKK_SCIENCE_READY__ = true;
  window.__CKK_SCIENCE_STATE__ = { route, apiMode: 'ERROR', error: error.message };
}
