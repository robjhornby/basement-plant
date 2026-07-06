const SITE_OBJECT_KEYS = new Set(["index.html", "physics-report.html"]);

export function siteObjectKey(pathname: string): string | null {
  if (pathname === "/" || pathname === "/index.html") {
    return "index.html";
  }
  const pathKey = pathname.replace(/^\/+/, "");
  return SITE_OBJECT_KEYS.has(pathKey) ? pathKey : null;
}

function responseHeaders(object: R2ObjectBody): Headers {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  if (!headers.has("content-type")) {
    headers.set("content-type", "text/html; charset=utf-8");
  }
  return headers;
}

export default {
  async fetch(request, env): Promise<Response> {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", {
        status: 405,
        headers: { allow: "GET, HEAD" },
      });
    }

    const url = new URL(request.url);
    const objectKey = siteObjectKey(url.pathname);
    if (objectKey === null) {
      return new Response("Not found", { status: 404 });
    }

    const object = await env.SITE_BUCKET.get(objectKey);
    if (object === null) {
      console.warn(JSON.stringify({ event: "site_object_missing", object_key: objectKey }));
      return new Response("Not found", { status: 404 });
    }

    return new Response(request.method === "HEAD" ? null : object.body, {
      headers: responseHeaders(object),
    });
  },
} satisfies ExportedHandler<Env>;
