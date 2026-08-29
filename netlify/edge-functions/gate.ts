const COOKIE_NAME = "ckk_admin_session";
const SIX_MONTHS = 60 * 60 * 24 * 180;

async function sessionToken(user: string, pass: string) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", encoder.encode(pass), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(user));
  return btoa(String.fromCharCode(...new Uint8Array(signature))).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function basicCredentials(request: Request) {
  const auth = request.headers.get("authorization") || "";
  if (!auth.startsWith("Basic ")) return null;
  try {
    const decoded = atob(auth.slice(6));
    const separator = decoded.indexOf(":");
    return separator < 0 ? null : { user: decoded.slice(0, separator), pass: decoded.slice(separator + 1) };
  } catch {
    return null;
  }
}

export default async (request: Request, context: any) => {
  const url = new URL(request.url);
  const user = Netlify.env.get("CKK_USER") || "ckk";
  const pass = Netlify.env.get("CKK_PASSWORD");

  // The public application is intentionally readable. Missing admin credentials
  // disable admin sessions rather than locking the entire CKK site.
  if (!pass) return context.next();

  if (url.pathname === "/admin-login") {
    const supplied = basicCredentials(request);
    if (supplied?.user === user && supplied.pass === pass) {
      const token = await sessionToken(user, pass);
      const response = Response.redirect(new URL("/", url), 303);
      response.headers.append("Set-Cookie", `${COOKIE_NAME}=${token}; Path=/; Max-Age=${SIX_MONTHS}; HttpOnly; Secure; SameSite=Lax`);
      return response;
    }
    return new Response("CKK admin login", {
      status: 401,
      headers: { "WWW-Authenticate": 'Basic realm="CKK Admin"', "Cache-Control": "no-store" },
    });
  }

  if (url.pathname === "/admin-logout") {
    const response = Response.redirect(new URL("/", url), 303);
    response.headers.append("Set-Cookie", `${COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`);
    return response;
  }

  return context.next();
};
