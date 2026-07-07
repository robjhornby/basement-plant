# Assess infra config spread and environment-variable consolidation

Type: research
Parent: ../map.md

## Question

Where do deployment values (domain, bucket names, addresses, coordinates, station ids) live
today, and which should be consolidated into variables/environment configuration instead of being
spread through the repo? The user specifically wants to avoid `robjhornby.com` appearing
throughout the codebase.

Known spread from the review: the domain appears in `infra/cloudflare/tofu/variables.tf`
(defaults), `infra/cloudflare/workers/site/wrangler.jsonc` (route pattern), the site Worker
source's `/basement` base path, docs, and the GitHub Actions workflow indirectly via secrets;
bucket names are duplicated between tofu variables and both wrangler configs (with comments
noting they must match); weather coordinates and the EA station id are constants in
`static_site.py`.

Resolve with a written assessment: an inventory of duplicated/hardcoded values, which duplications
are real risks (change one place, silently break another) versus harmless defaults, what the
consolidation mechanism would be per case (tofu variables as source of truth, wrangler `vars`,
workflow env, Python settings), and either "current spread is acceptable because X" or a specified
follow-up task ticket for the mechanical consolidation. Keep the Workers-Free/no-database
constraints; don't introduce config machinery heavier than the problem.
