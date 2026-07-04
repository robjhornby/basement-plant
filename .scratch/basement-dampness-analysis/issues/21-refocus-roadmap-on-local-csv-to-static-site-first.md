# Refocus roadmap on local CSV-to-static-site first

Type: grilling
Status: resolved
Parent: ../map.md

## Question

Should the next phase keep pursuing SES, S3, `robjhornby.com`, AWS, Cloudflare, and server automation, or should it defer remote infrastructure until the local analysis and static site work end-to-end from local CSVs?

## Answer

Defer remote hosting, S3, SES email routing, publishing to `robjhornby.com`, AWS/Cloudflare setup, and full server-side automation.

The current phase should be local-first:

- local CSV files are the data source;
- the full analysis runs locally;
- the pipeline produces static web pages locally;
- the pages are viewable locally for feedback and iteration.

Only after the local CSV-to-static-site workflow is useful should a later project phase handle SES email ingestion, S3 storage, publishing to `robjhornby.com`, AWS/Cloudflare provisioning, and eventually server-side automated ingestion/rendering.

Earlier remote-oriented decisions still describe likely later architecture, but they are no longer active near-term implementation scope.
