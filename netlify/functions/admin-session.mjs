import crypto from 'node:crypto';

function parseBasic(value) {
  if (!value?.startsWith('Basic ')) return null;
  try {
    const decoded = Buffer.from(value.slice(6), 'base64').toString('utf8');
    const separator = decoded.indexOf(':');
    return separator < 0 ? null : { username: decoded.slice(0, separator), password: decoded.slice(separator + 1) };
  } catch {
    return null;
  }
}

function equal(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

export function adminSessionToken(username, password) {
  return crypto.createHmac('sha256', String(password)).update(String(username)).digest('base64url');
}

function cookieValue(request, name) {
  const cookie = request.headers.get('cookie') || '';
  for (const part of cookie.split(';')) {
    const [key, ...value] = part.trim().split('=');
    if (key === name) return value.join('=');
  }
  return null;
}

export function authorizeAdmin(request, env = process.env) {
  const credentials = parseBasic(request.headers.get('authorization'));
  const configuredUser = env.CKK_USER || '';
  const configuredPassword = env.CKK_PASSWORD || '';
  const admins = new Set(String(env.CKK_ADMIN_USERS || configuredUser).split(',').map((item) => item.trim()).filter(Boolean));
  if (!configuredUser || !configuredPassword || !admins.has(configuredUser)) return null;
  const validBasic = credentials
    && equal(credentials.username, configuredUser)
    && equal(credentials.password, configuredPassword);
  const suppliedToken = cookieValue(request, 'ckk_admin_session');
  const validSession = suppliedToken && equal(suppliedToken, adminSessionToken(configuredUser, configuredPassword));
  if (!validBasic && !validSession) return null;
  return {
    username: configuredUser,
    preferenceKey: crypto.createHash('sha256').update(`ckk-admin-view:${configuredUser}`).digest('hex').slice(0, 20),
  };
}

export default async (request) => {
  const admin = authorizeAdmin(request);
  if (!admin) return Response.json({ admin: false }, { status: 401, headers: { 'cache-control': 'no-store' } });
  return Response.json({ admin: true, preference_key: admin.preferenceKey, logout_url: '/admin-logout' }, { headers: { 'cache-control': 'no-store' } });
};
