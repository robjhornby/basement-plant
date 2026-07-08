import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";

import worker, { siteObjectKey } from "../src/index";

describe("siteObjectKey", () => {
  it("maps only the known publication paths", () => {
    expect(siteObjectKey("/basement/")).toBe("index.html");
    expect(siteObjectKey("/basement/index.html")).toBe("index.html");
    expect(siteObjectKey("/basement/physics-report.html")).toBe("physics-report.html");
    expect(siteObjectKey("/")).toBeNull();
    expect(siteObjectKey("/basement")).toBeNull();
    expect(siteObjectKey("/basement/cache/open_meteo.json")).toBeNull();
    expect(siteObjectKey("/basement/../index.html")).toBeNull();
    expect(siteObjectKey("/basement-other/physics-report.html")).toBeNull();
  });
});

describe("site Worker", () => {
  it("redirects the extensionless base path so relative links stay under /basement/", async () => {
    const response = await worker.fetch(new Request("https://example.test/basement"), env);

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe("https://example.test/basement/");
  });

  it("serves the dashboard HTML from R2", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(new Request("https://example.test/basement/"), env);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(response.headers.get("cache-control")).toBe("public, max-age=600, no-transform");
    expect(response.headers.get("etag")).not.toBeNull();
    expect(await response.text()).toContain("Dashboard");
  });

  it("answers a matching If-None-Match with a bodyless 304", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const firstResponse = await worker.fetch(new Request("https://example.test/basement/"), env);
    const etag = firstResponse.headers.get("etag");
    expect(etag).not.toBeNull();

    const revalidation = await worker.fetch(
      new Request("https://example.test/basement/", {
        headers: { "if-none-match": etag! },
      }),
      env,
    );

    expect(revalidation.status).toBe(304);
    expect(revalidation.headers.get("etag")).toBe(etag);
    expect(revalidation.headers.get("cache-control")).toBe("public, max-age=600, no-transform");
    expect(await revalidation.text()).toBe("");
  });

  it("serves the full body when If-None-Match does not match", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(
      new Request("https://example.test/basement/", {
        headers: { "if-none-match": '"stale-etag"' },
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect(await response.text()).toContain("Dashboard");
  });

  it("serves the physics report HTML from R2", async () => {
    await env.SITE_BUCKET.put("physics-report.html", "<!doctype html><h1>Physics</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(
      new Request("https://example.test/basement/physics-report.html"),
      env,
    );

    expect(response.status).toBe(200);
    expect(await response.text()).toContain("Physics");
  });

  it("supports HEAD requests for smoke tests", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(
      new Request("https://example.test/basement/", { method: "HEAD" }),
      env,
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await response.text()).toBe("");
  });

  it("rejects non-GET-or-HEAD requests and unknown paths", async () => {
    const postResponse = await worker.fetch(
      new Request("https://example.test/basement/", { method: "POST" }),
      env,
    );
    const missingResponse = await worker.fetch(
      new Request("https://example.test/basement/raw-emails/message.eml"),
      env,
    );
    const outsideBasePathResponse = await worker.fetch(
      new Request("https://example.test/raw-emails/message.eml"),
      env,
    );

    expect(postResponse.status).toBe(405);
    expect(postResponse.headers.get("allow")).toBe("GET, HEAD");
    expect(missingResponse.status).toBe(404);
    expect(outsideBasePathResponse.status).toBe(404);
  });
});
