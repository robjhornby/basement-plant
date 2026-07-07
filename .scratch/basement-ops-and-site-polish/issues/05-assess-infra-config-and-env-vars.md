# Assess infra config spread and environment-variable consolidation

Type: research
Parent: ../map.md
Status: resolved

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

## Answer

Full inventory (every occurrence, file:line, with the config-surface sketch):
[assets/05-infra-config-inventory.md](../assets/05-infra-config-inventory.md).

**Verdict: the cross-tool spread is acceptable as-is; a small mechanical consolidation is worth
doing inside Python and the tests, plus removing the tofu `zone_name` default.** Specified as the
follow-up task ticket
[Mechanical config consolidation](14-mechanical-config-consolidation.md).

### Risk assessment per duplication

**Real-but-mitigated: bucket names, worker name (tofu ↔ wrangler).** `basement-pipeline` /
`basement-site` / `basement-email-ingest` each live in `variables.tf` defaults *and* the
corresponding `wrangler.jsonc`, with "must match" comments on both sides. Wrangler cannot read
tofu variables, so the only "fix" is generating wrangler.jsonc from a template or adding a parity
check script — machinery heavier than the problem, because these names are effectively frozen
(renaming an R2 bucket means create-new-and-migrate, at which point you're editing everything
anyway) and drift fails loud (a Worker bound to a nonexistent bucket fails at deploy, not
silently). **Keep the comments, do nothing.**

**Real-but-frozen: the object-key layout (TS worker ↔ Python ↔ workflow shell).** The
`raw-emails/csv/manifests` key shapes exist in four code places across three languages with no
shared schema — the genuine change-one-break-another shape. But the layout is frozen by the
objects already stored in R2 (changing it means a data migration, not a config edit), the
write/read parity is guarded by tests that assert exact keys on both sides, and there is no cheap
cross-language sharing mechanism on the Free/no-build-step constraints. **Accept; the parity
tests are the enforcement.** Same reasoning for the `x_sense`/`x-sense` partition-spelling split
(verified: separate namespaces, each internally consistent, both frozen by stored data) and the
`parquet` prefix.

**Real-and-cheap-to-fix: intra-Python triplication.** The EA station id `270397` is a proper
constant in `static_site.py` but independently hardcoded in `curated_dataset.py:77` (partition
path — write-side only; verified the reader globs without naming the station, so drift mislabels
new data rather than breaking reads) and `summaries.py:292` (prose label). The raw-key prefix
`raw-emails/source=x-sense` is likewise repeated across `raw_email_ingest.py` and `cli.py`.
**Consolidate into shared Python constants — ticket 14.**

**The domain.** `robjhornby.com` appears in exactly two live-config places: the tofu `zone_name`
default (`variables.tf:14` — everything else in tofu correctly derives from the variable, e.g.
the ingest address in `locals.tf`) and the site Worker's route in `wrangler.jsonc:8-9`. The other
~20 occurrences are docs prose and test fixtures. Mechanism per case: drop the tofu default so
the real value lives only in gitignored `production.tfvars` (with an `example.com` placeholder in
`example.tfvars`); switch the TS test fixtures to neutral domains, matching the Python tests'
existing `example.test` convention; the wrangler route **stays** — a route must name its zone,
wrangler config has no variable indirection for it, and one occurrence in the deploy contract is
the irreducible minimum. Docs/README prose stays too: the repo is public, the site URL is
public, and prose describing the deployed system is documentation, not config spread. Net result:
the domain appears in code exactly once (the route), which satisfies the "not throughout the
codebase" goal without new machinery. **Ticket 14.**

**Already clean (no action):** account/zone ids (no defaults, real values only in gitignored
tfvars/envrc); the ingest email address (assembled once in tofu locals, absent from worker
source); the GitHub Actions workflow (all identity via `secrets.*`, no hardcoded names/domain);
R2 env-var names (`R2_CREDENTIAL_ENV_VARS` in `curated_dataset.py` is the contract). The
`index.html`/`physics-report.html` triplication (worker allowlist, workflow sync includes, Python
output names) is real but the page set is about to be revisited by the redesign arm — noted there
rather than churned now.
