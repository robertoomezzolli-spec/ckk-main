import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';
import { adminSessionToken, authorizeAdmin } from '../netlify/functions/admin-session.mjs';
import { buildGraphIndex } from '../site/src/model.js';
import { normalizeSeedExpression, resolveSeedExploration } from '../site/src/seed-explorer.js';

const snapshot = JSON.parse(await readFile(new URL('../site/public/data/run34.json', import.meta.url), 'utf8'));
const basicRequest = (username, password) => new Request('https://ckk.example/.netlify/functions/admin-session', {
  headers: { authorization: `Basic ${Buffer.from(`${username}:${password}`).toString('base64')}` },
});

test('admin session is fail-closed and returns an opaque per-user preference key', () => {
  const env = { CKK_USER: 'admin', CKK_PASSWORD: 'correct', CKK_ADMIN_USERS: 'admin' };
  assert.equal(authorizeAdmin(new Request('https://ckk.example'), env), null);
  assert.equal(authorizeAdmin(basicRequest('admin', 'wrong'), env), null);
  const authorized = authorizeAdmin(basicRequest('admin', 'correct'), env);
  assert.equal(authorized.username, 'admin');
  assert.match(authorized.preferenceKey, /^[a-f0-9]{20}$/);
  assert.equal(authorizeAdmin(basicRequest('admin', 'correct'), env).preferenceKey, authorized.preferenceKey);
});

test('signed admin session cookie survives navigation and fails closed when tampered', () => {
  const env = { CKK_USER: 'admin', CKK_PASSWORD: 'correct', CKK_ADMIN_USERS: 'admin' };
  const token = adminSessionToken('admin', 'correct');
  const request = new Request('https://ckk.example/.netlify/functions/admin-session', { headers: { cookie: `other=1; ckk_admin_session=${token}` } });
  assert.equal(authorizeAdmin(request, env)?.username, 'admin');
  assert.equal(authorizeAdmin(new Request(request.url, { headers: { cookie: 'ckk_admin_session=tampered' } }), env), null);
  assert.notEqual(token, adminSessionToken('admin', 'changed-password'));
});

test('admin controls are disabled when production credentials are not configured', () => {
  const token = adminSessionToken('admin', 'correct');
  const request = new Request('https://ckk.example/.netlify/functions/admin-session', { headers: { cookie: `ckk_admin_session=${token}` } });
  assert.equal(authorizeAdmin(request, {}), null);
});

test('edge gate keeps public CKK readable and limits credential prompts to admin login', async () => {
  const source = await readFile(new URL('../netlify/edge-functions/gate.ts', import.meta.url), 'utf8');
  assert.match(source, /url\.pathname === "\/admin-login"/);
  assert.match(source, /url\.pathname === "\/admin-logout"/);
  assert.match(source, /Max-Age=\$\{SIX_MONTHS\}/);
  assert.match(source, /HttpOnly; Secure; SameSite=Lax/);
  assert.match(source, /return context\.next\(\);\s*\n};/);
  assert.doesNotMatch(source, /return new Response\("Authentication required"/);
});

test('E = mc² normalization is deterministic', () => {
  assert.deepEqual(normalizeSeedExpression(' E = m c² '), { original: 'E = m c²', normalized: 'e=mc^2', display: 'E = mc²' });
  assert.equal(normalizeSeedExpression('E=mc^2').normalized, 'e=mc^2');
});

test('sealed Einstein blind probe resolves to NO STRUCTURAL PATH without label inference', () => {
  const before = JSON.stringify(snapshot);
  const result = resolveSeedExploration('E = mc²', snapshot, buildGraphIndex(snapshot));
  assert.equal(result.recognized, true);
  assert.equal(result.probeId, 'probe:einstein:mass-energy');
  assert.equal(result.verdict, 'NO_STRUCTURAL_PATH');
  assert.deepEqual(result.matchedNodes, []);
  assert.deepEqual(result.provenance, []);
  assert.match(result.explanation, /no explicit structural attachment/i);
  assert.equal(JSON.stringify(snapshot), before, 'exploration must not mutate the SEALED snapshot');
});

test('unsupported labels and formulas cannot manufacture matches', () => {
  const copy = structuredClone(snapshot);
  copy.nodes[0].label = 'E = mc² gravity Einstein';
  const result = resolveSeedExploration('unregistered = expression', copy, buildGraphIndex(copy));
  assert.equal(result.recognized, false);
  assert.equal(result.verdict, 'NO_STRUCTURAL_PATH');
  assert.equal(result.matchedNodes.length, 0);
});

test('only explicit stored attachment IDs produce a structural path', () => {
  const fixture = structuredClone(snapshot);
  fixture.external_probes = [{ id: 'probe:einstein:mass-energy', formula: 'E = mc²', attachment: null, attached_node_id: '22' }];
  const result = resolveSeedExploration('E=mc^2', fixture, buildGraphIndex(fixture));
  assert.equal(result.verdict, 'STRUCTURAL_PATH');
  assert.deepEqual(result.matchedNodes.map((node) => String(node.id)), ['22']);
  assert.ok(result.provenance.every((edge) => String(edge.source_id) === '22' || String(edge.target_id) === '22'));
});
