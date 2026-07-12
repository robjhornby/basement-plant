# Basement Site Worker

Wrangler-managed Worker that serves the generated basement static site from the
dedicated private `basement-site` R2 bucket.

Routes:

- `/basement` -> `/basement/` (`308`)
- `/basement/` and `/basement/index.html` -> `index.html`

All other paths return `404`; methods other than `GET` and `HEAD` return `405`.
The Worker is intentionally not a general-purpose R2 file browser.

```bash
npm install
npm run types
npm run check
npm test
npm run deploy
```

Publication is separate from Worker deploys. The GitHub Actions runner writes
the rendered dashboard HTML into `s3://basement-site/` using R2 S3-compatible
credentials.
