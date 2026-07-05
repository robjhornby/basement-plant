# Design Cloudflare static publication

Type: task
Status: open
Parent: ../map.md
Blocked by: 27, 28

## Question

How should the hosted Cloudflare analysis job publish the generated basement static site after
reading Parquet data from R2 and running the production analysis pipeline?

Compare Cloudflare Pages direct upload, Workers static assets, and writing generated site artifacts
back to R2 behind a Worker route. Preserve the local `uv run basement` workflow as a reproducible
debug path.
