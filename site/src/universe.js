import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { DOMAINS } from './model.js';

const STATUS_COLORS = Object.freeze({
  KNOWN: new THREE.Color(0xf4fbff),
  REDISCOVERED: new THREE.Color(0xffc85b),
  VARIANT: new THREE.Color(0x62d9ff),
  UNMATCHED: new THREE.Color(0xa36bed),
});

const KIND_ORDER = ['RECURRENCE', 'SYMMETRY', 'BOUNDCOND', 'CARRIER', 'CYCLE', 'INTEGER', 'PRODUCT', 'BUNDLE', 'BOUNDARY', 'WEIGHT', 'FILTER'];

function hashNumber(value) {
  let hash = 2166136261;
  for (const char of String(value)) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function seeded(seed) {
  let state = seed || 1;
  return () => {
    state = Math.imul(1664525, state) + 1013904223 | 0;
    return (state >>> 0) / 4294967296;
  };
}

function makeGlowTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 128; canvas.height = 128;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, 'rgba(255,255,255,.82)');
  gradient.addColorStop(.12, 'rgba(120,205,255,.32)');
  gradient.addColorStop(.46, 'rgba(90,100,255,.08)');
  gradient.addColorStop(1, 'rgba(0,0,0,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}

export class Universe {
  constructor(canvas, data, index, callbacks = {}) {
    this.canvas = canvas;
    this.data = data;
    this.index = index;
    this.callbacks = callbacks;
    this.nodePositions = new Map();
    this.instanceByNode = new Map();
    this.nodeByInstance = [];
    this.baseScales = [];
    this.filters = new Set(Object.keys(STATUS_COLORS));
    this.keys = new Set();
    this.lastFrameAt = performance.now();
    this.flightVelocity = new THREE.Vector3();
    this.cameraGoal = null;
    this.selectedId = null;
    this.active = true;
    this.exploreIds = new Set();
    this.exploreMix = 0;
    this.targetExploreMix = 0;
    this.disposed = false;
    this.setup();
  }

  setup() {
    if (!window.WebGL2RenderingContext) throw new Error('WebGL2 is unavailable.');
    this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, alpha: false, powerPreference: 'high-performance' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(window.innerWidth, window.innerHeight, false);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x02050d);
    this.scene.fog = new THREE.FogExp2(0x02050d, 0.00145);
    this.camera = new THREE.PerspectiveCamera(54, window.innerWidth / window.innerHeight, .1, 1900);
    this.camera.position.set(0, 95, 360);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = .055;
    this.controls.minDistance = 12;
    this.controls.maxDistance = 900;
    this.controls.target.set(0, 0, 0);
    this.controls.screenSpacePanning = false;
    this.controls.zoomSpeed = .8;
    this.glowTexture = makeGlowTexture();
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.physicsGroup = new THREE.Group();
    this.scene.add(this.physicsGroup);
    this.addLights();
    this.addStars();
    this.addPhysicsGalaxy();
    this.addMissingGalaxies();
    this.bindEvents();
    this.animate();
  }

  addLights() {
    this.scene.add(new THREE.AmbientLight(0x8db9ff, 1.1));
    const cyan = new THREE.PointLight(0x5fd9ff, 1100, 450, 1.8); cyan.position.set(40, 80, 110); this.scene.add(cyan);
    const violet = new THREE.PointLight(0xa25cff, 800, 400, 1.8); violet.position.set(-110, -40, -70); this.scene.add(violet);
  }

  addStars() {
    const random = seeded(340276);
    const positions = new Float32Array(6200 * 3);
    const colors = new Float32Array(6200 * 3);
    for (let i = 0; i < 6200; i += 1) {
      const radius = 180 + random() * 1050;
      const theta = random() * Math.PI * 2;
      const phi = Math.acos(2 * random() - 1);
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.cos(phi);
      positions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
      const value = .35 + random() * .65;
      colors[i * 3] = value * .72; colors[i * 3 + 1] = value * .84; colors[i * 3 + 2] = value;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    this.stars = new THREE.Points(geometry, new THREE.PointsMaterial({ size: .75, vertexColors: true, transparent: true, opacity: .72, sizeAttenuation: true }));
    this.scene.add(this.stars);
  }

  physicsPosition(node, clusterSizes) {
    const kindIndex = Math.max(0, KIND_ORDER.indexOf(node.kind));
    const angle = kindIndex / KIND_ORDER.length * Math.PI * 2 - Math.PI / 2;
    const clusterRadius = node.kind === 'PRODUCT' || node.kind === 'BUNDLE' ? 82 : 66;
    const center = new THREE.Vector3(Math.cos(angle) * clusterRadius, Math.sin(angle) * clusterRadius * .62, (Number(node.dim) - 2) * 14);
    const ordinal = clusterSizes.get(node.kind).indexOf(node);
    const random = seeded(hashNumber(node.id));
    const localAngle = ordinal * 2.399963 + random() * .4;
    const localRadius = 4 + Math.sqrt(ordinal + 1) * 3.5;
    return center.add(new THREE.Vector3(
      Math.cos(localAngle) * localRadius,
      Math.sin(localAngle) * localRadius * .55,
      (random() - .5) * 24 + Number(node.depth) * 3,
    ));
  }

  addPhysicsGalaxy() {
    const clusterSizes = new Map(KIND_ORDER.map((kind) => [kind, this.data.nodes.filter((node) => node.kind === kind)]));
    const geometry = new THREE.IcosahedronGeometry(1, 1);
    const material = new THREE.MeshStandardMaterial({ roughness: .24, metalness: .15, emissive: 0x071426, emissiveIntensity: .7 });
    this.nodeMesh = new THREE.InstancedMesh(geometry, material, this.data.nodes.length);
    this.nodeMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    const helper = new THREE.Object3D();
    this.data.nodes.forEach((node, index) => {
      const position = this.physicsPosition(node, clusterSizes);
      const scale = .72 + Math.min(2.5, Math.sqrt(Number(node.paths || 1)) * .11) + (node.verdict === 'REDISCOVERED' ? .65 : 0);
      helper.position.copy(position); helper.scale.setScalar(scale); helper.updateMatrix();
      this.nodeMesh.setMatrixAt(index, helper.matrix);
      this.nodeMesh.setColorAt(index, STATUS_COLORS[node.verdict] || STATUS_COLORS.UNMATCHED);
      this.nodePositions.set(String(node.id), position);
      this.instanceByNode.set(String(node.id), index);
      this.nodeByInstance[index] = node;
      this.baseScales[index] = scale;
    });
    this.nodeMesh.instanceColor.needsUpdate = true;
    this.physicsGroup.add(this.nodeMesh);
    this.addRelationLanes();
    this.addBeacons();
    this.addGalaxyNebula(new THREE.Vector3(0, 0, -18), 150, 0x2764a2, this.physicsGroup, 900, .27);
  }

  addRelationLanes() {
    const vertices = [];
    for (const edge of this.data.edges) {
      const source = this.nodePositions.get(String(edge.source_id));
      const target = this.nodePositions.get(String(edge.target_id));
      if (!source || !target) continue;
      const midpoint = source.clone().add(target).multiplyScalar(.5);
      const lift = Math.min(22, source.distanceTo(target) * .15);
      midpoint.z += lift;
      vertices.push(source.x, source.y, source.z, midpoint.x, midpoint.y, midpoint.z, midpoint.x, midpoint.y, midpoint.z, target.x, target.y, target.z);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    const material = new THREE.LineBasicMaterial({ color: 0x5e82a5, transparent: true, opacity: .105, depthWrite: false });
    this.relations = new THREE.LineSegments(geometry, material);
    this.physicsGroup.add(this.relations);
  }

  addBeacons() {
    const material = new THREE.SpriteMaterial({ map: this.glowTexture, color: 0xffc85b, transparent: true, opacity: .8, depthWrite: false, blending: THREE.AdditiveBlending });
    this.beacons = [];
    for (const node of this.data.nodes.filter((item) => item.verdict === 'REDISCOVERED')) {
      const sprite = new THREE.Sprite(material.clone());
      sprite.position.copy(this.nodePositions.get(String(node.id)));
      sprite.scale.set(24, 24, 1);
      sprite.userData.nodeId = String(node.id);
      this.physicsGroup.add(sprite);
      this.beacons.push(sprite);
    }
  }

  addGalaxyNebula(center, radius, color, parent, count = 500, opacity = .18) {
    const random = seeded(hashNumber(`${center.x}:${center.y}:${center.z}:${color}`));
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      const angle = random() * Math.PI * 8;
      const radial = Math.pow(random(), .65) * radius;
      positions[i * 3] = center.x + Math.cos(angle) * radial;
      positions[i * 3 + 1] = center.y + (random() - .5) * radius * .42;
      positions[i * 3 + 2] = center.z + Math.sin(angle) * radial * .42;
    }
    const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const points = new THREE.Points(geometry, new THREE.PointsMaterial({ color, size: 1.3, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending }));
    parent.add(points);
    return points;
  }

  addMissingGalaxies() {
    this.missingGroups = {};
    Object.entries(DOMAINS).filter(([, domain]) => !domain.executable).forEach(([key, domain]) => {
      const group = new THREE.Group();
      const center = new THREE.Vector3(...domain.center);
      const shell = new THREE.Mesh(
        new THREE.IcosahedronGeometry(42, 2),
        new THREE.MeshBasicMaterial({ color: domain.color, wireframe: true, transparent: true, opacity: .075, depthWrite: false }),
      );
      shell.position.copy(center); group.add(shell);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(52, .22, 4, 90),
        new THREE.MeshBasicMaterial({ color: domain.color, transparent: true, opacity: .28 }),
      );
      ring.position.copy(center); ring.rotation.x = 1.15; ring.rotation.z = .4; group.add(ring);
      this.addGalaxyNebula(center, 68, domain.color, group, 340, .22);
      group.userData.center = center; group.userData.key = key;
      this.scene.add(group); this.missingGroups[key] = group;
    });
  }

  bindEvents() {
    this.handleResize = () => {
      this.camera.aspect = window.innerWidth / window.innerHeight;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(window.innerWidth, window.innerHeight, false);
    };
    this.handleClick = (event) => {
      if (event.target !== this.canvas) return;
      const rect = this.canvas.getBoundingClientRect();
      this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(this.pointer, this.camera);
      const hit = this.raycaster.intersectObject(this.nodeMesh, false)[0];
      if (hit && hit.instanceId !== undefined) {
        const node = this.nodeByInstance[hit.instanceId];
        if (this.filters.has(node.verdict)) this.callbacks.onNode?.(node);
      }
    };
    this.handleKeyDown = (event) => { if (!event.metaKey && !event.ctrlKey) this.keys.add(event.code); };
    this.handleKeyUp = (event) => this.keys.delete(event.code);
    window.addEventListener('resize', this.handleResize);
    window.addEventListener('keydown', this.handleKeyDown);
    window.addEventListener('keyup', this.handleKeyUp);
    this.canvas.addEventListener('click', this.handleClick);
  }

  updateFlight(delta) {
    const direction = new THREE.Vector3();
    const forward = new THREE.Vector3(); this.camera.getWorldDirection(forward); forward.y = 0; forward.normalize();
    const right = new THREE.Vector3().crossVectors(forward, this.camera.up).normalize();
    if (this.keys.has('KeyW')) direction.add(forward);
    if (this.keys.has('KeyS')) direction.sub(forward);
    if (this.keys.has('KeyD')) direction.add(right);
    if (this.keys.has('KeyA')) direction.sub(right);
    if (this.keys.has('KeyE')) direction.y += 1;
    if (this.keys.has('KeyQ')) direction.y -= 1;
    if (direction.lengthSq()) direction.normalize().multiplyScalar(70 * delta);
    this.flightVelocity.lerp(direction, 1 - Math.pow(.03, delta));
    this.camera.position.add(this.flightVelocity);
    this.controls.target.add(this.flightVelocity);
  }

  updateGoal(delta) {
    if (!this.cameraGoal) return;
    const amount = 1 - Math.pow(.002, delta);
    this.camera.position.lerp(this.cameraGoal.position, amount);
    this.controls.target.lerp(this.cameraGoal.target, amount);
    if (this.camera.position.distanceTo(this.cameraGoal.position) < .4) this.cameraGoal = null;
  }

  animate = () => {
    if (this.disposed) return;
    const now = performance.now();
    const delta = Math.min(.05, Math.max(0, (now - this.lastFrameAt) / 1000));
    this.lastFrameAt = now;
    if (this.active) {
      this.updateFlight(delta);
      this.updateGoal(delta);
      this.controls.update();
      this.stars.rotation.y += delta * .002;
      Object.values(this.missingGroups).forEach((group, index) => { group.rotation.y += delta * (.015 + index * .004); });
      this.beacons.forEach((beacon, index) => { const pulse = 20 + Math.sin(performance.now() * .002 + index) * 4; beacon.scale.set(pulse, pulse, 1); });
      const nextMix = THREE.MathUtils.lerp(this.exploreMix, this.targetExploreMix, 1 - Math.pow(.002, delta));
      if (Math.abs(nextMix - this.exploreMix) > .001) { this.exploreMix = nextMix; this.updateNodeMatrices(); }
      this.renderer.render(this.scene, this.camera);
      this.callbacks.onFrame?.(this.camera);
    }
    requestAnimationFrame(this.animate);
  };

  updateNodeMatrices() {
    const helper = new THREE.Object3D();
    this.data.nodes.forEach((node, index) => {
      const visible = this.filters.has(node.verdict);
      const position = this.nodePositions.get(String(node.id));
      const selected = String(node.id) === this.selectedId;
      const explored = this.exploreIds.has(String(node.id));
      helper.position.copy(position);
      if (explored && this.exploreMix > 0) {
        const direction = position.clone().normalize();
        if (!direction.lengthSq()) direction.set(0, 1, 0);
        helper.position.add(direction.multiplyScalar(54 * this.exploreMix));
      }
      const explorationScale = this.exploreIds.size ? (explored ? 1 + 1.8 * this.exploreMix : 1 - .82 * this.exploreMix) : 1;
      helper.scale.setScalar(visible ? this.baseScales[index] * (selected ? 2 : 1) * explorationScale : .001); helper.updateMatrix();
      this.nodeMesh.setMatrixAt(index, helper.matrix);
    });
    this.nodeMesh.instanceMatrix.needsUpdate = true;
  }

  setFilters(statuses) {
    this.filters = new Set(statuses);
    this.updateNodeMatrices();
  }

  setActive(active) {
    this.active = Boolean(active);
    this.controls.enabled = this.active;
  }

  exploreNodes(ids) {
    this.exploreIds = new Set(ids.map(String).filter((id) => this.nodePositions.has(id)));
    this.selectedId = null;
    this.targetExploreMix = this.exploreIds.size ? 1 : 0;
    if (this.exploreIds.size) {
      const centroid = [...this.exploreIds].reduce((sum, id) => sum.add(this.nodePositions.get(id)), new THREE.Vector3()).multiplyScalar(1 / this.exploreIds.size);
      this.cameraGoal = { target: centroid.clone(), position: centroid.clone().add(new THREE.Vector3(0, 24, 110)) };
    } else {
      this.cameraGoal = { target: new THREE.Vector3(0, -20, -55), position: new THREE.Vector3(0, 145, 530) };
    }
    this.updateNodeMatrices();
  }

  clearExplore() {
    this.exploreIds.clear();
    this.targetExploreMix = 0;
    this.updateNodeMatrices();
  }

  focusNode(nodeId) {
    const id = String(nodeId);
    const position = this.nodePositions.get(id);
    if (!position) return;
    this.selectedId = id;
    this.setFilters([...this.filters]);
    this.cameraGoal = { target: position.clone(), position: position.clone().add(new THREE.Vector3(0, 12, 38)) };
  }

  focusDomain(key) {
    if (key === 'physics') {
      this.cameraGoal = { target: new THREE.Vector3(), position: new THREE.Vector3(0, 72, 260) };
    } else if (DOMAINS[key]) {
      const target = new THREE.Vector3(...DOMAINS[key].center);
      this.cameraGoal = { target, position: target.clone().add(new THREE.Vector3(0, 36, 140)) };
    } else {
      this.reset();
    }
  }

  reset() {
    this.selectedId = null;
    this.clearExplore();
    this.setFilters([...this.filters]);
    this.cameraGoal = { target: new THREE.Vector3(0, -20, -55), position: new THREE.Vector3(0, 145, 530) };
  }

  project(position) {
    const projected = position.clone().project(this.camera);
    return { x: (projected.x * .5 + .5) * window.innerWidth, y: (-projected.y * .5 + .5) * window.innerHeight, visible: projected.z > -1 && projected.z < 1 };
  }

  labelPositions() {
    const labels = { physics: this.project(new THREE.Vector3(0, 115, 0)) };
    for (const [key, domain] of Object.entries(DOMAINS)) {
      if (key !== 'physics') labels[key] = this.project(new THREE.Vector3(domain.center[0], domain.center[1] + 58, domain.center[2]));
    }
    return labels;
  }

  visibleNodePositions() {
    return this.data.nodes.map((node) => ({ id: String(node.id), verdict: node.verdict, ...this.project(this.nodePositions.get(String(node.id))) }));
  }

  dispose() {
    this.disposed = true;
    window.removeEventListener('resize', this.handleResize);
    window.removeEventListener('keydown', this.handleKeyDown);
    window.removeEventListener('keyup', this.handleKeyUp);
    this.canvas.removeEventListener('click', this.handleClick);
    this.renderer.dispose();
  }
}
