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
    const response = await worker.fetch(new Request("https://robjhornby.com/basement"), env);

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe("https://robjhornby.com/basement/");
  });

  it("serves the dashboard HTML from R2", async () => {
    await env.SITE_BUCKET.put("index.html", "<!doctype html><h1>Dashboard</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(new Request("https://robjhornby.com/basement/"), env);

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await response.text()).toContain("Dashboard");
  });

  it("serves the physics report HTML from R2", async () => {
    await env.SITE_BUCKET.put("physics-report.html", "<!doctype html><h1>Physics</h1>", {
      httpMetadata: { contentType: "text/html; charset=utf-8" },
    });

    const response = await worker.fetch(
      new Request("https://robjhornby.com/basement/physics-report.html"),
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
      new Request("https://robjhornby.com/basement/", { method: "HEAD" }),
      env,
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("text/html; charset=utf-8");
    expect(await response.text()).toBe("");
  });

  it("rejects non-GET-or-HEAD requests and unknown paths", async () => {
    const postResponse = await worker.fetch(
      new Request("https://robjhornby.com/basement/", { method: "POST" }),
      env,
    );
    const missingResponse = await worker.fetch(
      new Request("https://robjhornby.com/basement/raw-emails/message.eml"),
      env,
    );
    const outsideBasePathResponse = await worker.fetch(
      new Request("https://robjhornby.com/raw-emails/message.eml"),
      env,
    );

    expect(postResponse.status).toBe(405);
    expect(postResponse.headers.get("allow")).toBe("GET, HEAD");
    expect(missingResponse.status).toBe(404);
    expect(outsideBasePathResponse.status).toBe(404);
  });
});
