/**
 * Cloudflare Pages Function: proxy /api/* to the Railway backend (avoids browser CORS).
 * Set BACKEND_URL in Pages → Settings → Environment variables (Production).
 */
export async function onRequest(context) {
  const backend =
    context.env.BACKEND_URL || "https://ai-voiceagent-production-cad3.up.railway.app";
  const url = new URL(context.request.url);
  const target = `${backend.replace(/\/$/, "")}${url.pathname}${url.search}`;

  const headers = new Headers(context.request.headers);
  headers.delete("host");

  return fetch(target, {
    method: context.request.method,
    headers,
    body:
      context.request.method !== "GET" && context.request.method !== "HEAD"
        ? context.request.body
        : undefined,
    redirect: "follow",
  });
}
