import path from "node:path";

import { defineWorkersConfig } from "@cloudflare/vitest-pool-workers/config";

export default defineWorkersConfig({
  resolve: {
    alias: {
      // Repo-level local data directory holding the real .eml sample.
      "@repo-data": path.resolve(import.meta.dirname, "../../../../data"),
    },
  },
  test: {
    poolOptions: {
      workers: {
        wrangler: { configPath: "./wrangler.jsonc" },
      },
    },
  },
});
