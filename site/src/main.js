import './style.css';
import './classic-fan.css';
import { Universe } from './universe.js';
import { ClassicFan } from './classic-fan.js';
import { loadSelectedSealedSnapshot } from './snapshot-source.js';
import { resolveSeedExploration } from './seed-explorer.js';
import {
  buildCrossDomainBridges,
  buildGraphIndex,
  DOMAINS,
  GOLDEN,
  nodeCardModel,
  TOUR,
  truthCounts,
  validateSnapshot,
} from './model.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);

let data;
let index;
let universe;
let classicFan;
let activeView = 'universe';
let adminPreferenceKey = null;
let lastSeedResult = null;
let tourIndex = 0;
let labelFrame = 0;

function showToast(message) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.classList.add('show');
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 2200);
}

function selectedNodeIds() {
  return data.nodes.map((node) => String(node.id));
}

function setApplicationView(view, { persist = true, updateUrl = true } = {}) {
  activeView = view === 'classic' ? 'classic' : 'universe';
  document.body.classList.toggle('view-classic', activeView === 'classic');
  $('#classic-fan').hidden = activeView !== 'classic';
  universe?.setActive(activeView === 'universe');
  const link = $('#admin-view-link');
  if (link) {
    const target = activeView === 'classic' ? 'universe' : 'classic';
    link.textContent = activeView === 'classic' ? 'UNIVERSE 3D' : 'CLASSIC FAN';
    link.href = `?view=${target}`;
  }
  if (persist) localStorage.setItem(adminPreferenceKey ? `ckk:view-mode:${adminPreferenceKey}` : 'ckk:view-mode:browser', activeView);
  if (updateUrl) {
    const url = new URL(window.location.href);
    if (activeView === 'classic') url.searchParams.set('view', 'classic'); else url.searchParams.delete('view');
    history.replaceState(null, '', url);
  }
}

function renderSeedResult(result) {
  const panel = $('#seed-result');
  panel.hidden = false;
  panel.innerHTML = `
    <button class="seed-close" data-seed-close aria-label="Close seed exploration">×</button>
    <h3>READ-ONLY SEED EXPLORER</h3>
    <h2>${escapeHtml(result.display || result.original)}</h2>
    <p>${escapeHtml(result.explanation)}</p>
    ${result.verdict === 'NO_STRUCTURAL_PATH' ? '<div class="no-structural-path">NO STRUCTURAL PATH</div>' : '<div class="evidence-box"><b>EXPLICIT STRUCTURAL PATH</b><small>Backed by stored node attachment(s) in this SEALED generation.</small></div>'}
    <section><h3>MATCHED STRUCTURES</h3>${result.matchedNodes.length
      ? result.matchedNodes.map((node) => `<button class="seed-match-row" data-seed-node="${escapeHtml(node.id)}">${escapeHtml(node.label || `${node.kind} d${node.dim}`)} · NODE ${escapeHtml(node.id)}</button>`).join('')
      : '<p>No generated node is explicitly attached.</p>'}</section>
    <section><h3>DERIVATION / PROVENANCE</h3>${result.provenance.length
      ? result.provenance.slice(0, 20).map((edge) => `<p><code>${escapeHtml(edge.source_id)} → ${escapeHtml(edge.target_id)}</code> · ${escapeHtml(edge.operator || edge.id || 'stored relation')}</p>`).join('')
      : '<p>No applicable stored derivation is available for this expression.</p>'}</section>
    ${result.unsupportedSteps.length ? `<section><h3>UNSUPPORTED STEPS</h3>${result.unsupportedSteps.map((step) => `<p>${escapeHtml(step)} <b>— NO STRUCTURAL PATH</b></p>`).join('')}</section>` : ''}
    <p><small>This exploration is presentation-only. It creates no candidate, canon record, grammar rule, generation, or Scientific state.</small></p>`;
  $('[data-seed-close]', panel).onclick = () => {
    panel.hidden = true; universe?.clearExplore(); classicFan?.clearExplore(); lastSeedResult = null;
  };
  $$('[data-seed-node]', panel).forEach((button) => {
    button.onclick = () => {
      if (activeView === 'classic') classicFan.select(button.dataset.seedNode);
      else { universe?.focusNode(button.dataset.seedNode); nodeCard(index.nodes.get(button.dataset.seedNode)); }
    };
  });
}

function playSeedCinematic(result) {
  const cinematic = $('#seed-cinematic');
  $('strong', cinematic).textContent = result.display || result.original;
  cinematic.hidden = true;
  void cinematic.offsetWidth;
  cinematic.hidden = false;
  window.setTimeout(() => { cinematic.hidden = true; }, 2200);
  const ids = result.matchedNodes.map((node) => String(node.id));
  universe?.exploreNodes(ids);
  classicFan?.exploreNodes(ids);
}

async function enableAdminTools() {
  try {
    const response = await fetch('/.netlify/functions/admin-session', { cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) return;
    const session = await response.json();
    if (!session.admin || !session.preference_key) return;
    adminPreferenceKey = session.preference_key;
    $('#admin-tools').hidden = false;
    const requested = new URL(window.location.href).searchParams.get('view');
    const stored = localStorage.getItem(`ckk:view-mode:${adminPreferenceKey}`);
    if (requested === 'classic' || stored === 'classic') setApplicationView('classic', { persist: false, updateUrl: false });
    $('#seed-explorer').onsubmit = (event) => {
      event.preventDefault();
      lastSeedResult = resolveSeedExploration($('#seed-expression').value, data, index);
      renderSeedResult(lastSeedResult);
      playSeedCinematic(lastSeedResult);
    };
  } catch (error) {
    console.warn('Admin controls unavailable.', error);
  }
}

function domainCard(key) {
  const panel = $('#domain-panel');
  $('#node-card').hidden = true;
  $('#tour-card').hidden = true;
  panel.hidden = false;
  if (key === 'cross-domain') {
    const bridges = buildCrossDomainBridges(data.nodes.map((node) => ({ domain: 'physics', node })));
    panel.innerHTML = `
      <button class="card-close" data-close>×</button>
      <span class="eyebrow">CROSS-DOMAIN CONNECTIONS</span>
      <h2>${bridges.length} certified bridges</h2>
      <p>A bridge requires the same neutral structural signature in at least two domains with executable, provenance-bearing occurrences.</p>
      <div class="no-bridge">NO GENERATED STRUCTURE SATISFIES THIS REQUIREMENT.<br>Chemistry, Biology, and Computation do not currently have executable fixtures. No semantic equivalence is inferred.</div>
      <div class="status-grid"><span>Match semantics</span><b>STRUCTURAL MATCH ONLY</b><span>Same mechanism</span><b>NOT EVALUATED</b><span>Missing data shown</span><b>YES</b></div>`;
  } else {
    const domain = DOMAINS[key];
    const partial = !domain.executable;
    panel.innerHTML = `
      <button class="card-close" data-close>×</button>
      <span class="eyebrow">${escapeHtml(domain.status)} · DOMAIN GALAXY</span>
      <h2>${escapeHtml(domain.name)}</h2>
      <p>${escapeHtml(domain.note)}</p>
      ${partial ? `<div class="missing-state"><b>MISSING EXECUTABLE DATA</b><small>${escapeHtml(domain.missing)}</small></div>` : ''}
      <div class="status-grid">
        <span>Generated structures</span><b>${domain.structures}</b>
        <span>Executable fixture</span><b>${domain.executable ? 'YES' : 'NO'}</b>
        <span>Archive status</span><b>${escapeHtml(domain.status)}</b>
        <span>Provenance</span><b>${escapeHtml(domain.provenance || GOLDEN.generationId)}</b>
      </div>
      ${partial ? '<p>No stars or catalog matches are synthesized for this galaxy. The nebula is a missing-data marker, not a scientific result.</p>' : '<p>The visible clusters use stored structural kinds. The graph itself is not changed by this view.</p>'}`;
  }
  $('[data-close]', panel).onclick = () => { panel.hidden = true; };
}

function incomingRows(model) {
  if (!model.incoming.length) return '<div class="derivation-row"><span>ADMITTED SEED</span><b>no incoming relation</b></div>';
  return model.incoming.slice(0, 8).map((edge) => `
    <button class="derivation-row" data-node-link="${escapeHtml(edge.source_id)}">
      <span>${escapeHtml(edge.source_id)} → ${escapeHtml(model.id)}</span>
      <b>${escapeHtml(edge.operator)}</b>
    </button>`).join('') + (model.incoming.length > 8 ? `<p>+ ${model.incoming.length - 8} more stored incoming relations</p>` : '');
}

function nodeCard(node) {
  const model = nodeCardModel(node, index);
  const card = $('#node-card');
  $('#domain-panel').hidden = true;
  $('#tour-card').hidden = true;
  card.hidden = false;
  const catalogBlock = model.isCatalog ? `
    <div class="evidence-box annotation"><b>CATALOG ANNOTATION</b><small>${escapeHtml(node.label || 'Catalog relative')} · ${escapeHtml(model.status)}</small></div>` : `
    <div class="evidence-box annotation"><b>CATALOG MATCH</b><small>NONE ASSIGNED</small></div>`;
  const rediscovered = model.status === 'REDISCOVERED' ? `
    <section class="card-section">
      <h3>WHY RUN 34 CALLS THIS REDISCOVERED</h3>
      <p>The sealed snapshot records a generated structural signature followed by a catalog match. Independent hold-out provenance is not fully recoverable from this projection, so the historical classification is displayed with that limitation.</p>
    </section>` : '';
  const unmatched = model.status === 'UNMATCHED' ? `
    <section class="card-section interest">
      <h3>WHY THIS MAY BE INTERESTING</h3>
      <p>${node.paths} recorded paths reach this signature; ${model.rootDiversity} root classes are reachable in the projected graph. These are prioritization metrics, not evidence of new physics.</p>
    </section>` : '';
  card.innerHTML = `
    <div class="node-head">
      <button class="card-close" data-close>×</button>
      <span class="status-chip ${escapeHtml(model.status)}">${escapeHtml(model.status)}</span>
      <h2>${escapeHtml(model.name)}</h2>
      <div class="subtitle">${escapeHtml(node.kind)} · STRUCTURAL d${node.dim} · OPERATOR DEPTH ${node.depth}</div>
    </div>
    <section class="card-section">
      <h3>WHAT IS THIS?</h3>
      <p>${escapeHtml(model.meaning)}</p>
      <div class="formula">${escapeHtml(model.catalogFormula || model.structuralFormula)}</div>
      ${model.catalogFormula ? '<p>This formula belongs to the catalog interpretation. It is not part of the generated node identity.</p>' : ''}
    </section>
    <section class="card-section">
      <h3>GENERATED STRUCTURE ≠ INTERPRETATION</h3>
      <div class="generated-vs-annotation">
        <div class="evidence-box"><b>GENERATED</b><small>${escapeHtml(node.kind)} d${node.dim}; lifecycle ${escapeHtml(node.lifecycle)}</small></div>
        ${catalogBlock}
      </div>
    </section>
    <section class="card-section">
      <h3>WHY IT EXISTS HERE · STORED RELATIONS</h3>
      <div class="derivation-list">${incomingRows(model)}</div>
      <p>Operator provenance: <b>${escapeHtml(model.provenance)}</b>. <code>snapshot_v6:*</code> identifiers are reported verbatim and are not reconstructed as named operators.</p>
    </section>
    <section class="card-section">
      <h3>STRUCTURE METRICS</h3>
      <div class="metric-grid">
        <div class="metric"><b>${node.paths}</b><small>RECORDED PATHS</small></div>
        <div class="metric"><b>${model.rootDiversity}</b><small>ROOT DIVERSITY</small></div>
        <div class="metric"><b>${model.incoming.length}</b><small>IN-DEGREE</small></div>
      </div>
      <p>Legacy convergence: <b>${model.legacyConvergence ? 'YES' : 'NO'}</b>. True derivational confluence: <b>${model.trueConfluence}</b>.</p>
    </section>
    ${model.physicsRealizations.length ? `<section class="card-section"><h3>DOMAIN REALIZATIONS · CATALOG</h3><div class="tag-list">${model.physicsRealizations.map((item) => `<span class="tag">${escapeHtml(item)}</span>`).join('')}</div></section>` : ''}
    ${rediscovered}${unmatched}
    <section class="card-section">
      <h3>DUALITY STATUS</h3>
      <p>Structural dual branch: <b>${Number(node.dual) === 1 ? 'TRANSFORMED BRANCH' : 'ORIGINAL BRANCH'}</b>. Physical duality: <b>NOT EVALUATED</b>. D(X) ≡ X: <b>NOT EVALUATED</b>.</p>
    </section>
    <section class="card-section advanced-only">
      <h3>TECHNICAL RECORD</h3>
      <p>Roots: ${escapeHtml(model.roots.join(', ') || 'none')}. Stored edge provenance is a conservative Run 34 projection.</p>
      <details><summary>TECHNICAL SIGNATURE + RAW RECORD</summary><pre>${escapeHtml(JSON.stringify({ structural_signature: model.structuralFormula, node: model.raw }, null, 2))}</pre></details>
    </section>`;
  $('[data-close]', card).onclick = () => { card.hidden = true; universe.selectedId = null; universe.setFilters([...universe.filters]); };
  $$('[data-node-link]', card).forEach((button) => {
    button.onclick = () => {
      const parent = index.nodes.get(button.dataset.nodeLink);
      if (parent) { universe.focusNode(parent.id); nodeCard(parent); }
    };
  });
}

function questionsCard() {
  const panel = $('#domain-panel');
  $('#node-card').hidden = true; $('#tour-card').hidden = true; panel.hidden = false;
  panel.innerHTML = `
    <button class="card-close" data-close>×</button>
    <span class="eyebrow">OPEN QUESTIONS · FAIL-CLOSED</span>
    <h2>What remains unresolved?</h2>
    <div class="missing-state"><b>CROSS-ORDER FIBER INFORMATION</b><small>The current audited Python core records 1,836 cross-order fiber events. Regression status: FAIL.</small></div>
    <div class="missing-state"><b>MIXED-DUAL PRODUCT INFORMATION</b><small>The current audited Python core records 336 mixed-dual products promoted through max(dual). Regression status: FAIL.</small></div>
    <div class="missing-state"><b>CROSS-DOMAIN FIXTURES</b><small>Chemistry, Biology, and Computation have partial methodology records but no executable golden fixtures.</small></div>
    <div class="status-grid"><span>Self-duality</span><b>NOT EVALUATED</b><span>Physical duality</span><b>NOT EVALUATED</b><span>MAXDIM=4</span><b>EXPERIMENT PARAMETER</b><span>New generation</span><b>NOT CREATED</b></div>`;
  $('[data-close]', panel).onclick = () => { panel.hidden = true; };
}

function renderTour() {
  const step = TOUR[tourIndex];
  const card = $('#tour-card');
  $('#domain-panel').hidden = true; $('#node-card').hidden = true; card.hidden = false;
  card.innerHTML = `
    <button class="card-close" data-close>×</button>
    <span class="tour-step">STEP ${tourIndex + 1} / ${TOUR.length}</span>
    <h2>${escapeHtml(step.title)}</h2>
    <div class="tour-progress"><i style="width:${((tourIndex + 1) / TOUR.length) * 100}%"></i></div>
    <p>${escapeHtml(step.body)}</p>
    <div class="tour-nav"><button data-prev ${tourIndex === 0 ? 'disabled' : ''}>PREVIOUS</button><button data-inspect>OPEN STRUCTURE</button><button data-next>${tourIndex === TOUR.length - 1 ? 'FINISH' : 'NEXT'}</button></div>`;
  universe.focusNode(step.nodeId);
  $('[data-close]', card).onclick = () => { card.hidden = true; };
  $('[data-prev]', card).onclick = () => { tourIndex = Math.max(0, tourIndex - 1); renderTour(); };
  $('[data-inspect]', card).onclick = () => nodeCard(index.nodes.get(step.nodeId));
  $('[data-next]', card).onclick = () => {
    if (tourIndex === TOUR.length - 1) { card.hidden = true; universe.reset(); return; }
    tourIndex += 1; renderTour();
  };
}

function updateGalaxyLabels() {
  if (!universe || labelFrame++ % 3) return;
  const positions = universe.labelPositions();
  Object.entries(positions).forEach(([key, point]) => {
    const label = $(`[data-galaxy-label="${key}"]`);
    if (!label) return;
    label.style.left = `${point.x}px`; label.style.top = `${point.y}px`;
    label.style.opacity = point.visible ? '1' : '0';
  });
}

function renderLabels() {
  $('#galaxy-labels').innerHTML = Object.entries(DOMAINS).map(([key, domain]) => `
    <div class="galaxy-label ${domain.executable ? 'physics' : 'partial'}" data-galaxy-label="${key}">
      <b>${escapeHtml(domain.name)}</b><small>${domain.executable ? `${domain.structures} STRUCTURES` : 'MISSING EXECUTABLE DATA'}</small>
    </div>`).join('');
}

function fallbackView(error) {
  $('#universe').hidden = true;
  const fallback = $('#fallback'); fallback.hidden = false;
  $('#fallback-domains').innerHTML = Object.values(DOMAINS).map((domain) => `<div class="fallback-domain"><b>${escapeHtml(domain.name)}</b><p>${escapeHtml(domain.note)}</p><small>${domain.structures} generated structures · ${escapeHtml(domain.status)}</small></div>`).join('');
  showToast(`3D fallback: ${error.message}`);
}

function bindUI() {
  $('#admin-view-link').onclick = (event) => {
    event.preventDefault();
    setApplicationView(activeView === 'classic' ? 'universe' : 'classic');
  };
  $$('.domain-button').forEach((button) => {
    button.onclick = () => {
      $$('.domain-button').forEach((item) => item.classList.toggle('active', item === button));
      domainCard(button.dataset.domain);
      universe?.focusDomain(button.dataset.domain);
    };
  });
  $$('.filters input[type="checkbox"]').forEach((input) => {
    input.onchange = () => universe?.setFilters($$('.filters input:checked').map((item) => item.value));
  });
  $('[data-action="toggle-filters"]').onclick = () => $('.filters').classList.toggle('collapsed');
  $('[data-action="advanced"]').onclick = (event) => {
    const active = document.body.classList.toggle('advanced');
    event.currentTarget.setAttribute('aria-pressed', String(active));
    showToast(active ? 'Advanced data enabled' : 'Advanced data disabled');
  };
  $('[data-action="tour"]').onclick = () => { tourIndex = 0; renderTour(); };
  $('[data-action="home"]').onclick = () => { universe?.reset(); classicFan?.clearExplore(); $('#domain-panel').hidden = true; $('#node-card').hidden = true; $('#tour-card').hidden = true; $('#seed-result').hidden = true; };
  $('[data-action="reset-camera"]').onclick = () => universe?.reset();
  $$('[data-view]').forEach((button) => {
    button.onclick = () => {
      $$('[data-view]').forEach((item) => item.classList.toggle('active', item === button));
      if (button.dataset.view === 'questions') questionsCard();
      else if (button.dataset.view === 'bridges') domainCard('cross-domain');
      else { $('#domain-panel').hidden = true; universe?.reset(); }
    };
  });
  $$('[data-enter]').forEach((button) => {
    button.onclick = () => {
      $('#landing').classList.add('hidden');
      if (button.dataset.enter === 'tour') { tourIndex = 0; renderTour(); }
      if (button.dataset.enter === 'questions') questionsCard();
      if (button.dataset.enter === 'bridges') domainCard('cross-domain');
    };
  });
}

async function start() {
  try {
    data = await loadSelectedSealedSnapshot();
    const validation = validateSnapshot(data);
    if (!validation.clean) throw new Error(validation.errors.join('\n'));
    index = buildGraphIndex(data);
    const counts = truthCounts(data.nodes);
    Object.entries(counts).forEach(([status, count]) => { const field = $(`#count-${status.toLowerCase()}`); if (field) field.textContent = count; });
    $('#app').hidden = false;
    renderLabels();
    try {
      universe = new Universe($('#universe'), data, index, { onNode: nodeCard, onFrame: updateGalaxyLabels });
      window.__CKK_DEBUG__ = { visibleNodePositions: () => universe.visibleNodePositions() };
    } catch (error) {
      fallbackView(error);
    }
    classicFan = new ClassicFan($('#classic-fan'), data, index);
    bindUI();
    const requestedView = new URL(window.location.href).searchParams.get('view');
    const browserView = localStorage.getItem('ckk:view-mode:browser');
    setApplicationView(requestedView === 'classic' || browserView === 'classic' ? 'classic' : 'universe', { persist: false, updateUrl: false });
    await enableAdminTools();
    $('#loading').remove();
    window.__CKK_READY_AT__ = performance.now();
    window.__CKK_READY__ = true;
    window.__CKK_STATE__ = { generationId: data.generation_id, runId: data.run.id, nodes: data.nodes.length, edges: data.edges.length, domains: DOMAINS, crossDomainBridges: 0 };
    window.__CKK_VIEW_AUDIT__ = {
      sameDataReference: () => Boolean(universe && classicFan && universe.data === classicFan.data && universe.data === data),
      generation: () => ({ selected: data.generation_id, universe: universe?.data.generation_id, classic: classicFan.generationId() }),
      nodeIds: () => ({ selected: selectedNodeIds(), universe: universe?.data.nodes.map((node) => String(node.id)) || [], classic: classicFan.nodeIds() }),
      activeView: () => activeView,
      seedResult: () => lastSeedResult,
    };
  } catch (error) {
    console.error(error);
    const fragment = $('#error-template').content.cloneNode(true);
    $('pre', fragment).textContent = error.stack || error.message;
    document.body.append(fragment);
    $('#loading')?.remove();
    window.__CKK_ERROR__ = error.message;
  }
}

start();
