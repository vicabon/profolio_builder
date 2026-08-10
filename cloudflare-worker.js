/**
 * Cloudflare Worker：TWSE / Yahoo Finance 唯讀轉發代理
 *
 * 用途：讓靜態 GitHub Pages 頁面的前端 JS 能直接取得台股/美股即時報價，
 * 繞過瀏覽器對 mis.twse.com.tw 與 query1/2.finance.yahoo.com 的 CORS 限制。
 *
 * 安全設計：
 * - 只允許轉發到白名單網域（TWSE / Yahoo），不是任意 URL 的開放代理。
 * - 只允許 GET，不轉發 cookie/憑證。
 * - 回應加上寬鬆 CORS header，讓 github.io 網域可讀取。
 *
 * 部署方式：
 * 1. 到 https://dash.cloudflare.com → Workers & Pages → Create Worker
 * 2. 貼上這份程式碼，Deploy
 * 3. 記下 Worker 網址（例如 https://portfolio-proxy.<你的帳號>.workers.dev）
 * 4. 填入 portfolio.html 開頭的 WORKER_BASE_URL
 */

const ALLOWED_HOSTS = new Set([
  "mis.twse.com.tw",
  "query1.finance.yahoo.com",
  "query2.finance.yahoo.com",
]);

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }
    if (request.method !== "GET") {
      return new Response("Method not allowed", { status: 405, headers: CORS_HEADERS });
    }

    const reqUrl = new URL(request.url);
    const target = reqUrl.searchParams.get("url");
    if (!target) {
      return new Response("Missing ?url=", { status: 400, headers: CORS_HEADERS });
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      return new Response("Invalid url", { status: 400, headers: CORS_HEADERS });
    }

    if (!ALLOWED_HOSTS.has(targetUrl.hostname)) {
      return new Response("Host not allowed", { status: 403, headers: CORS_HEADERS });
    }

    const upstreamHeaders = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    };
    if (targetUrl.hostname === "mis.twse.com.tw") {
      upstreamHeaders["Referer"] = "https://mis.twse.com.tw/stock/index.jsp";
    }
    const upstream = await fetch(targetUrl.toString(), { headers: upstreamHeaders });

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
        ...CORS_HEADERS,
      },
    });
  },
};
