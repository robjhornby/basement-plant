import { env } from "cloudflare:workers";
import { describe, expect, it } from "vitest";

import worker, { siteObjectKey } from "../src/index";

describe("siteObjectKey", () => {
  it("maps only the known publication paths", () => {
    expect(siteObjectKey("/")).toBe("index.html");
    expect(siteObjectKey("/index.html")).toBe("index.html");
    expect(siteObjectKey("/physics-report.html")).toBe("physics-report.html");
    expect(siteObjectKey("/cache/open_meteo.json")).toBeNull();
    expect(siteObjectKey("/../index.html")).toBeNull();
  });
});

describe("site Worker", () => {
  it("serves the dashboard HTML from R2", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(new Request("https://basement.robjhornby.com/"), env);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await response.text()).toContain("Dashboard");
  });

  it("serves the physics report HTML from R2", async () => {
    await env.SITE_BUCKET.put("physics-report.html", "<!doctype html><h1>Physics</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(
      new Request("https://basement.robjhornby.com/physics-report.html"),
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
      new Request("https://basement.robjhornby.com/", { method: "HEAD" }),
      env,
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await response.text()).toBe("");
  });

  it("rejects non-GET-or-HEAD requests and unknown paths", async () => {
    const postResponse = await worker.fetch(
      new Request("https://basement.robjhornby.com/", { method: "POST" }),
      env,
    );
    const missingResponse = await worker.fetch(
      new Request("https://basement.robjhornby.com/raw-emails/message.eml"),
      env,
    );

    expect(postResponse.status).toBe(405);
    expect(postResponse.headers.get("allow")).toBe("GET, HEAD");
    expect(missingResponse.status).toBe(404);
  });
});
