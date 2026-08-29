const S = document.getElementById('g');
const stats = document.getElementById('stats');
const detail = document.getElementById('detail');
const events = document.getElementById('events');
const queue = document.getElementById('queue');
const physics = document.getElementById('physics');
const probes = document.getElementById('probes');
const status = document.getElementById('status');
const statusKey = document.getElementById('status-key');
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
const CARD_MODULE = import('./physics-cards.js');
const COLORS = ['#416f90', '#b27a2e', '#76548f', '#35664b', '#a74646', '#2f8585'];
let DATA = null; let POS = null; let FOCUS = null;

function clusterFor(id) { return (DATA?.duality_clusters || []).find((cluster) => cluster.target_node_id === id); }

function render(data) {
  DATA = data;
  document.getElementById('version').textContent = `grammar ${data.run?.grammar_version || '—'}`;
  document.querySelector('.legend').textContent = 'vertical axis = operator depth · d0…d4 = structural dimension · black = known · gold = rediscovered · dashed gold ring = structural confluence';
  const verdictCounts = {}; const dimensionCounts = {};
  data.nodes.forEach((node) => { verdictCounts[node.verdict] = (verdictCounts[node.verdict] || 0) + 1; dimensionCounts[Number(node.dim) || 0] = (dimensionCounts[Number(node.dim) || 0] || 0) + 1; });
  const dimensions = Object.entries(dimensionCounts).sort(([a], [b]) => Number(a) - Number(b)).map(([dimension, count]) => `d${dimension}: ${count}`).join(' · ');
  stats.innerHTML = `<div class="stat"><b>${data.nodes.length}</b>structures</div><div class="stat"><b>${data.edges.length}</b>relations</div><div class="stat"><b>${(data.duality_clusters || []).length}</b>confluences</div><div class="stat"><b>${verdictCounts.KNOWN || 0}</b>known</div><div class="stat rediscovered-stat"><b>${verdictCounts.REDISCOVERED || 0}</b>rediscovered</div><div class="stat dimension-stat"><b>dimension</b>${esc(dimensions)}</div>`;
  draw(data); renderProbes(data); renderPhysics(data); renderQueue(data); renderEvents(data);
  CARD_MODULE.then(({ renderStatusGlossary }) => { statusKey.innerHTML = renderStatusGlossary(); });
  status.innerHTML = `<span class="live">LIVE</span> · ${new Date(data.now).toLocaleTimeString()}`;
}

function draw(data) {
  const depths = [...new Set(data.nodes.map((node) => Number(node.depth) || 0))].sort((a, b) => a - b);
  const positions = new Map(); const W = 1280; const H = 690; const L = 78; const R = 35; const T = 54; const B = 36;
  depths.forEach((depth, depthIndex) => {
    const row = data.nodes.filter((node) => (Number(node.depth) || 0) === depth).sort((a, b) => (b.paths || 1) - (a.paths || 1));
    const y = T + (H - T - B) * (depthIndex / Math.max(1, depths.length - 1));
    row.forEach((node, index) => positions.set(node.id, { x: L + (W - L - R) * ((index + 0.5) / row.length), y, node }));
  });
  POS = positions;
  const active = new Map();
  if (FOCUS) FOCUS.branches.forEach((branch, branchIndex) => branch.seed_chain.forEach((id, index) => { active.set(id, branchIndex); if (index) active.set(`${branch.seed_chain[index - 1]}>${id}`, branchIndex); }));
  let output = '';
  depths.forEach((depth, depthIndex) => { const y = T + (H - T - B) * (depthIndex / Math.max(1, depths.length - 1)); output += `<line x1="57" y1="${y}" x2="1252" y2="${y}" stroke="#eee8de"/><text class="level" x="8" y="${y + 4}">DEPTH ${depth}</text>`; });
  data.edges.forEach((edge) => {
    const source = positions.get(edge.source_id); const target = positions.get(edge.target_id); if (!source || !target) return;
    const branch = active.get(`${edge.source_id}>${edge.target_id}`); const dimmed = Boolean(FOCUS) && branch === undefined;
    output += `<path d="M${source.x},${source.y} C${source.x},${(source.y + target.y) / 2} ${target.x},${(source.y + target.y) / 2} ${target.x},${target.y}" fill="none" stroke="${branch !== undefined ? COLORS[branch % 6] : '#d5cdc0'}" stroke-opacity="${dimmed ? 0.12 : 0.82}" stroke-width="${branch !== undefined ? 3 : 1}"/>`;
  });
  positions.forEach((position) => {
    const node = position.node; const branch = active.get(node.id); const dimmed = Boolean(FOCUS) && branch === undefined; const radius = 4 + Math.min(8, Math.sqrt(node.paths || 1) * 1.3); const verdictClass = (node.verdict || 'UNMATCHED').replace(/[^A-Z_]/g, '');
    if (clusterFor(node.id)) output += `<circle cx="${position.x}" cy="${position.y}" r="${radius + 5}" fill="none" stroke="#96722f" stroke-dasharray="3 2" opacity="${dimmed ? 0.15 : 1}"/>`;
    output += `<circle class="node ${verdictClass}" cx="${position.x}" cy="${position.y}" r="${radius}" data-id="${esc(node.id)}" opacity="${dimmed ? 0.14 : 1}" ${branch !== undefined ? `style="stroke:${COLORS[branch % 6]};stroke-width:3"` : ''}/>`;
  });
  S.innerHTML = output; S.querySelectorAll('.node').forEach((element) => { element.onclick = () => select(element.dataset.id); });
}

function focusPath(sourceId, targetId) { FOCUS = { branches: [{ seed_chain: [sourceId, targetId] }] }; draw(DATA); }

async function select(id) {
  const node = DATA.nodes.find((candidate) => candidate.id === id); if (!node) return;
  FOCUS = clusterFor(id) || null; draw(DATA);
  const { renderPhysicsCard } = await CARD_MODULE; detail.innerHTML = renderPhysicsCard(node, DATA);
  detail.querySelectorAll('.node-link').forEach((button) => { button.onclick = () => select(button.dataset.nodeId); });
  detail.querySelectorAll('.path-link').forEach((button) => { button.onclick = () => focusPath(button.dataset.pathSource, button.dataset.pathTarget); });
  detail.querySelector('[data-reset-graph]')?.addEventListener('click', () => { FOCUS = null; draw(DATA); });
}

function renderProbes(data) { probes.innerHTML = (data.probes || []).map((probe) => `<div class="probe"><strong>${esc(probe.name)}</strong><div class="formula">${esc(probe.formula)}</div><span class="badge">${esc(probe.status)}</span> <span class="badge">${esc(probe.domain)}</span><br><small>${esc(probe.note)}</small></div>`).join('') || '—'; }
function renderPhysics(data) { const rows = data.nodes.filter((node) => node.verdict === 'KNOWN' || node.verdict === 'REDISCOVERED'); physics.innerHTML = rows.map((node) => `<button class="phys ${node.verdict.toLowerCase()}" data-id="${esc(node.id)}"><strong>${esc(node.label || node.kind)}</strong><small>${esc(node.verdict)} · ${esc(node.kind)} d${node.dim}${clusterFor(node.id) ? ' · CONFLUENCE' : ''}</small></button>`).join('') || 'No physics labels yet.'; physics.querySelectorAll('.phys').forEach((element) => { element.onclick = () => select(element.dataset.id); }); }
function renderQueue(data) { queue.innerHTML = data.queue.map((item, index) => `<div class="q">#${index + 1} ${esc(item.kind)} d${item.dim}<br><small>priority ${Number(item.priority).toFixed(2)}</small></div>`).join('') || 'empty'; }
function renderEvents(data) { events.innerHTML = data.events.map((event) => `<div class="event"><b>${esc(event.event_type)}</b><br>${esc(event.summary)}<br><small>${new Date(event.created_at).toLocaleString()}</small></div>`).join('') || 'none'; }
async function tick() { try { const response = await fetch('/.netlify/functions/state', { cache: 'no-store' }); if (!response.ok) throw Error(response.status); render(await response.json()); } catch (error) { status.textContent = `OFFLINE · ${error.message}`; } }
tick(); setInterval(tick, 4000);
