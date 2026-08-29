import { renderPhysicsCard, renderStatusGlossary } from '../physics-cards.js';

const COLORS = ['#416f90', '#b27a2e', '#76548f', '#35664b', '#a74646', '#2f8585'];
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);

export class ClassicFan {
  constructor(root, data, index, callbacks = {}) {
    this.root = root;
    this.data = data;
    this.index = index;
    this.callbacks = callbacks;
    this.focus = null;
    this.exploreIds = new Set();
    this.build();
    this.render();
  }

  build() {
    this.root.innerHTML = `
      <div class="classic-shell" data-testid="classic-fan">
        <header class="classic-header"><div><h1>Der lebende Fächer</h1><p>CKK · generative structure map · SEALED snapshot</p></div><div class="classic-version">grammar ${esc(this.data.grammar_version)} · RUN ${esc(this.data.run.id)}</div></header>
        <div class="classic-layout">
          <main class="classic-main">
            <div class="classic-stats" data-classic-stats></div>
            <p class="classic-legend">vertical axis = operator depth · d0…d4 = structural dimension · black = known · gold = rediscovered · dashed gold ring = historical structural confluence</p>
            <p class="classic-help">Click a confluence to isolate its stored seed-rooted paths. Click any node for its Physics Card.</p>
            <svg class="classic-graph" data-classic-graph viewBox="0 0 1280 690" role="img" aria-label="Classic CKK fan"></svg>
          </main>
          <aside class="classic-sidebar">
            <section><h2>EXTERNAL PHYSICS PROBES</h2><div data-classic-probes></div></section>
            <section><h2>KNOWN PHYSICS IN THE FAN</h2><div data-classic-known></div></section>
            <section><h2>SCIENTIFIC INSPECTION</h2><a class="classic-science-link" href="/science">OPEN SCIENTIFIC CONTROL PLANE</a><div data-classic-status></div></section>
          </aside>
        </div>
        <aside class="classic-detail" data-classic-detail hidden></aside>
      </div>`;
    this.graph = this.root.querySelector('[data-classic-graph]');
    this.detail = this.root.querySelector('[data-classic-detail]');
  }

  render() {
    const counts = this.data.nodes.reduce((result, node) => ({ ...result, [node.verdict]: (result[node.verdict] || 0) + 1 }), {});
    this.root.querySelector('[data-classic-stats]').innerHTML = `
      <div><b>${this.data.nodes.length}</b><span>structures</span></div><div><b>${this.data.edges.length}</b><span>relations</span></div>
      <div><b>${this.data.duality_clusters.length}</b><span>confluences</span></div><div><b>${counts.KNOWN || 0}</b><span>known</span></div><div><b>${counts.REDISCOVERED || 0}</b><span>rediscovered</span></div>`;
    this.draw();
    this.renderSidebar();
  }

  clusterFor(id) {
    return this.index.legacyClusters.get(String(id));
  }

  draw() {
    const depths = [...new Set(this.data.nodes.map((node) => Number(node.depth) || 0))].sort((a, b) => a - b);
    const positions = new Map();
    const W = 1280; const H = 690; const L = 78; const R = 35; const T = 54; const B = 36;
    depths.forEach((depth, depthIndex) => {
      const row = this.data.nodes.filter((node) => Number(node.depth || 0) === depth).sort((a, b) => Number(b.paths || 1) - Number(a.paths || 1) || String(a.id).localeCompare(String(b.id)));
      const y = T + (H - T - B) * (depthIndex / Math.max(1, depths.length - 1));
      row.forEach((node, nodeIndex) => positions.set(String(node.id), { x: L + (W - L - R) * ((nodeIndex + .5) / row.length), y, node }));
    });
    this.positions = positions;
    const active = new Map();
    if (this.focus?.branches) this.focus.branches.forEach((branch, branchIndex) => branch.seed_chain.forEach((id, index) => {
      active.set(String(id), branchIndex);
      if (index) active.set(`${branch.seed_chain[index - 1]}>${id}`, branchIndex);
    }));
    let output = '';
    depths.forEach((depth, index) => {
      const y = T + (H - T - B) * (index / Math.max(1, depths.length - 1));
      output += `<line x1="57" y1="${y}" x2="1252" y2="${y}"/><text class="level" x="8" y="${y + 4}">DEPTH ${depth}</text>`;
    });
    this.data.edges.forEach((edge) => {
      const source = positions.get(String(edge.source_id)); const target = positions.get(String(edge.target_id));
      if (!source || !target) return;
      const branch = active.get(`${edge.source_id}>${edge.target_id}`);
      const explored = this.exploreIds.has(String(edge.source_id)) && this.exploreIds.has(String(edge.target_id));
      const dimmed = (this.focus && branch === undefined) || (this.exploreIds.size && !explored);
      output += `<path class="classic-edge${explored ? ' seed-path' : ''}" d="M${source.x},${source.y} C${source.x},${(source.y + target.y) / 2} ${target.x},${(source.y + target.y) / 2} ${target.x},${target.y}" stroke="${branch !== undefined ? COLORS[branch % COLORS.length] : '#d5cdc0'}" opacity="${dimmed ? .1 : .82}" stroke-width="${explored ? 3 : branch !== undefined ? 3 : 1}"/>`;
    });
    positions.forEach(({ x, y, node }) => {
      const branch = active.get(String(node.id));
      const explored = this.exploreIds.has(String(node.id));
      const dimmed = (this.focus && branch === undefined) || (this.exploreIds.size && !explored);
      const radius = 4 + Math.min(8, Math.sqrt(Number(node.paths || 1)) * 1.3);
      if (this.clusterFor(node.id)) output += `<circle class="confluence-ring" cx="${x}" cy="${y}" r="${radius + 5}" opacity="${dimmed ? .12 : 1}"/>`;
      output += `<circle class="classic-node ${esc(node.verdict)}${explored ? ' seed-match' : ''}" cx="${x}" cy="${y}" r="${explored ? radius + 4 : radius}" data-id="${esc(node.id)}" opacity="${dimmed ? .12 : 1}"/>`;
    });
    this.graph.innerHTML = output;
    this.graph.querySelectorAll('[data-id]').forEach((element) => { element.onclick = () => this.select(element.dataset.id); });
  }

  renderSidebar() {
    const probes = this.data.external_probes || this.data.probes || [];
    this.root.querySelector('[data-classic-probes]').innerHTML = probes.map((probe) => `<article class="classic-probe"><strong>${esc(probe.name || probe.title || probe.id)}</strong><div>${esc(probe.formula)}</div><small>${probe.attachment == null ? 'attachment: null · external blind probe' : 'stored structural attachment'}</small></article>`).join('') || '—';
    const known = this.data.nodes.filter((node) => ['KNOWN', 'REDISCOVERED'].includes(node.verdict));
    this.root.querySelector('[data-classic-known]').innerHTML = known.map((node) => `<button class="classic-known ${node.verdict.toLowerCase()}" data-known-id="${esc(node.id)}"><strong>${esc(node.label || `${node.kind} d${node.dim}`)}</strong><small>${esc(node.verdict)} · ${esc(node.kind)} d${node.dim}</small></button>`).join('');
    this.root.querySelectorAll('[data-known-id]').forEach((button) => { button.onclick = () => this.select(button.dataset.knownId); });
    this.root.querySelector('[data-classic-status]').innerHTML = renderStatusGlossary();
  }

  select(id) {
    const node = this.index.nodes.get(String(id));
    if (!node) return;
    this.focus = this.clusterFor(id) || null;
    this.draw();
    this.detail.hidden = false;
    this.detail.innerHTML = `<button class="classic-close" data-classic-close>×</button>${renderPhysicsCard(node, this.data)}<a class="classic-science-link" href="/science?structure=${encodeURIComponent(id)}">INSPECT STRUCTURE IN SCIENTIFIC</a>`;
    this.detail.querySelector('[data-classic-close]').onclick = () => { this.detail.hidden = true; };
    this.detail.querySelectorAll('.node-link').forEach((button) => { button.onclick = () => this.select(button.dataset.nodeId); });
    this.detail.querySelector('[data-reset-graph]')?.addEventListener('click', () => { this.focus = null; this.exploreIds.clear(); this.draw(); });
    this.callbacks.onNode?.(node);
  }

  exploreNodes(ids) {
    this.exploreIds = new Set(ids.map(String));
    this.focus = null;
    this.draw();
    if (this.exploreIds.size) this.graph.classList.add('exploring');
    else this.graph.classList.add('no-path-pulse');
    window.setTimeout(() => this.graph.classList.remove('exploring', 'no-path-pulse'), 1800);
  }

  clearExplore() {
    this.exploreIds.clear(); this.draw();
  }

  generationId() { return this.data.generation_id; }
  nodeIds() { return this.data.nodes.map((node) => String(node.id)); }
}
