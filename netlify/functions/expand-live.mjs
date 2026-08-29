export default async () => new Response(JSON.stringify({
  ok: false,
  sealed: true,
  message: 'Historical v6 HTML seed is sealed; automatic expansion is disabled.',
}), {
  status: 409,
  headers: {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
  },
});
