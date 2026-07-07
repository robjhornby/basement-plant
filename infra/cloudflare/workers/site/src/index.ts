const SITE_OBJECT_KEYS = new Set(["index.html", "physics-report.html"]);
const SITE_BASE_PATH = "/basement";

export function siteObjectKey(pathname: string): string | null {
  if (pathname === `${SITE_BASE_PATH}/` || pathname === `${SITE_BASE_PATH}/index.html`) {
    return "index.html";
  }
  if (!pathname.startsWith(`${SITE_BASE_PATH}/`)) {
    return null;
  }

  const pathKey = pathname.slice(SITE_BASE_PATH.length + 1);
  return SITE_OBJECT_KEYS.has(pathKey) ? pathKey : null;
}

function trailingSlashRedirect(request: Request): Response | null {
  const url = new URL(request.url);
  if (url.pathname !== SITE_BASE_PATH) {
    return null;
  }

  url.pathname = `${SITE_BASE_PATH}/`;
  return Response.redirect(url.toString(), 308);
}

function responseHeaders(object: R2ObjectBody): Headers {
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  headers.set("cache-control", "no-transform");
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

    const redirect = trailingSlashRedirect(request);
    if (redirect !== null) {
      return redirect;
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
