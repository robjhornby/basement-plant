# Deployment config spread inventory (asset for issue 05)

Produced 2026-07-08 by a repo-wide sweep for issue
[05 Assess infra config spread](../issues/05-assess-infra-config-and-env-vars.md).
Spot-checked findings: the `x_sense`/`x-sense` split and the `station=270397` read-path claim were
verified by hand (the curated rain reader globs `rain_readings/` without naming the station, so
that literal is write-side partition naming only).

## Structural sketch (config surfaces)

| Surface | Role |
|---|---|
| `infra/cloudflare/tofu/variables.tf` | Declares typed variables with defaults for `account_id`, `zone_id` (no default — must be supplied), `zone_name` ("robjhornby.com"), `pipeline_bucket_name` ("basement-pipeline"), `site_bucket_name` ("basement-site"), `r2_location`, `ingest_address_local_part`, `email_ingest_worker_name` ("basement-email-ingest"). **This is the closest thing to a source of truth** for domain, bucket names, and the ingest worker name — it even carries explicit "must match wrangler.jsonc" comments. |
| `infra/cloudflare/tofu/locals.tf` | Derives `ingest_email_address` from `zone_name` + `ingest_address_local_part`. Source of truth for the ingest email address (as a variable composition, not a literal). |
| `infra/cloudflare/tofu/env/example.tfvars` (tracked) / `env/production.tfvars` (gitignored) | Real `account_id`/`zone_id` only exist in the gitignored `production.tfvars`; nothing sensitive is committed. `example.tfvars` documents the same defaults as `variables.tf`, commented out, as a third copy. |
| `infra/cloudflare/workers/email-ingest/wrangler.jsonc`, `infra/cloudflare/workers/site/wrangler.jsonc` | Independent, hand-maintained JSON with its own literal `name`, `bucket_name`, and (site only) `routes[].pattern`/`zone_name`. Wrangler has no way to read the tofu variables, so these are manually kept in sync — annotated with "Must match the OpenTofu ... variable" comments on the bucket side only (not on worker name/route). |
| `infra/cloudflare/workers/*/src/*.ts` | Own literal constants: `SITE_BASE_PATH = "/basement"` (site), `SOURCE = "x-sense"` + object-key template literals (email-ingest). No shared package/module between the two workers or with Python. |
| `src/basement_analysis/static_site.py` | Source of truth for `CAVERSHAM_LATITUDE`/`CAVERSHAM_LONGITUDE`/`ENVIRONMENT_AGENCY_RAIN_STATION` — consistently reused within this one module, but not exported to/imported by `curated_dataset.py` or `summaries.py` (which independently hardcode the station id), and not referenced by TS code at all. |
| `src/basement_analysis/cli.py`, `raw_email_ingest.py`, `hosted_curation.py`, `curated_dataset.py` | Each independently hardcodes object-key prefixes (`"raw-emails/source=x-sense"`, `"csv/source=x-sense/..."`, `"manifests/ingest/..."`, `"parquet"`, `"station=270397"`) — no shared constants module for the object-key layout, mirroring (with hand-kept parity, per test comments) the TS worker's literals. |
| `.github/workflows/basement-site.yml` | No hardcoded bucket names/domain — consumes `R2_BUCKET`, `R2_SITE_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` purely as `secrets.*` → `env`. It does hardcode the object-key prefixes (`manifests/ingest`, `csv/source=x-sense`, `parquet`) inline in shell, a fourth copy of those path fragments. |
| `.envrc` / `infra/cloudflare/tofu/.envrc` (both gitignored) | Local-only real credentials/account id, following the `R2_ENDPOINT_URL`/`R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/`R2_BUCKET` naming convention documented in READMEs. Python's env-var names (`curated_dataset.py:21`, `hosted_curation.py:37`) are the consumer-side contract. |
| `docs/architecture/cloudflare-email-r2-static-site.md` | Documentation-only restatement of domain, bucket names, and object-key layout — no code reads it. |

No class has a single enforced source of truth across languages/tools; tofu `variables.tf` is the *intended* source for bucket/domain/worker names (per its "must match" comments), but wrangler and Python each hardcode their own copies with no automated check.

## 1. Domain `robjhornby.com` / `/basement` base path

| File:Line | Value | Role |
|---|---|---|
| `infra/cloudflare/tofu/variables.tf:7` | `robjhornby.com` (in description) | doc comment on `zone_id` var |
| `infra/cloudflare/tofu/variables.tf:14` | `"robjhornby.com"` | default of `zone_name` variable (source-of-truth default) |
| `infra/cloudflare/tofu/locals.tf:2` | `"${var.ingest_address_local_part}@${var.zone_name}"` | derives ingest address from `zone_name` |
| `infra/cloudflare/tofu/email_routing.tf:7` | `robjhornby.com` | comment, manual dashboard step |
| `infra/cloudflare/tofu/env/example.tfvars:6` | `# zone_name = "robjhornby.com"` | commented default, tracked |
| `infra/cloudflare/tofu/README.md:26,34` | `basement.robjhornby.com`, `robjhornby.com` | prose |
| `infra/cloudflare/README.md:22` | `https://robjhornby.com/basement/` | prose |
| `infra/cloudflare/workers/site/wrangler.jsonc:8` | `"pattern": "robjhornby.com/basement*"` | **Worker route pattern** (live routing config) |
| `infra/cloudflare/workers/site/wrangler.jsonc:9` | `"zone_name": "robjhornby.com"` | **Worker route zone_name** (live routing config) |
| `infra/cloudflare/workers/site/src/index.ts:2` | `SITE_BASE_PATH = "/basement"` | TS constant, drives redirect + object-key mapping |
| `infra/cloudflare/workers/site/test/site.spec.ts:21,24,32,45,59,70,74,78` | `https://robjhornby.com/basement...` (8 occurrences) | test fixture URLs |
| `infra/cloudflare/workers/site/README.md:8-10` | `/basement`, `/basement/`, `/basement/physics-report.html` | prose |
| `infra/cloudflare/workers/email-ingest/README.md:59,67,94` | `basement-ingest@robjhornby.com`, `robjhornby.com` | curl example / prose |
| `infra/cloudflare/workers/email-ingest/test/email-ingest.spec.ts:29,43` | `basement-ingest@robjhornby.com` | test fixtures |
| `docs/architecture/cloudflare-email-r2-static-site.md:48,103,105-107` | `robjhornby.com`, `/basement/` | documentation-only |
| `prototypes/physics-and-metrology-report-mock/README.md:279` | `robjhornby.com` | prototype prose, not live |

## 2. R2 bucket names (`basement-pipeline`, `basement-site`)

| File:Line | Value | Role |
|---|---|---|
| `infra/cloudflare/tofu/variables.tf:20` | `"basement-pipeline"` | default of `pipeline_bucket_name` (intended source of truth) |
| `infra/cloudflare/tofu/variables.tf:26` | `"basement-site"` | default of `site_bucket_name` (intended source of truth) |
| `infra/cloudflare/tofu/r2.tf:6,15` | `var.pipeline_bucket_name` / `var.site_bucket_name` | bucket resources |
| `infra/cloudflare/tofu/outputs.tf:2-3` | comment: "wrangler.jsonc bucket_name" | explicit cross-reference note |
| `infra/cloudflare/tofu/env/example.tfvars:7-8` | commented defaults | tracked |
| `infra/cloudflare/tofu/README.md:3-4,22-23`, `infra/cloudflare/README.md:15-16,22` | both names | prose |
| `infra/cloudflare/workers/email-ingest/wrangler.jsonc:9-11` | `"bucket_name": "basement-pipeline"` + **"Must match the OpenTofu pipeline_bucket_name variable"** | **live R2 binding** |
| `infra/cloudflare/workers/site/wrangler.jsonc:3` | `"name": "basement-site"` | Worker's deployed name (same string as bucket, not tofu-linked — no `site_worker_name` variable exists) |
| `infra/cloudflare/workers/site/wrangler.jsonc:14-17` | `"bucket_name": "basement-site"` + **"Must match the OpenTofu site_bucket_name variable"** | **live R2 binding** |
| `infra/cloudflare/workers/*/README.md`, `package.json`/lockfiles | names / derived npm names | prose / package naming |
| `prototypes/cloudflare-container-duckdb-analysis/NOTES.md:53` | `R2_BUCKET=basement-pipeline` | prototype example, not live |

Worker-name duplication: `infra/cloudflare/tofu/variables.tf:41-44` (`"basement-email-ingest"`, description says **"must match wrangler.jsonc name"**) ↔ `infra/cloudflare/workers/email-ingest/wrangler.jsonc:3` (live deploy name).

## 3. Email addresses

The **live** ingest address is assembled exactly once, in tofu (`locals.tf:2` =
`ingest_address_local_part` + `zone_name`); the worker source contains no address literal (routing
is Cloudflare Email Routing config, not code). All other occurrences are docs/test fixtures:
`email-ingest/README.md:59,94`, `email-ingest.spec.ts:28-29,42-45,115,117` (mix of the real
address and `example.test` synthetics), and Python tests already use `*@example.test` throughout
(`tests/test_raw_email_ingest.py`).

## 4. Weather coordinates & EA station id `270397`

| File:Line | Value | Role |
|---|---|---|
| `src/basement_analysis/static_site.py:37-40` | `CAVERSHAM_LATITUDE = 51.47`, `CAVERSHAM_LONGITUDE = -0.97`, `ENVIRONMENT_AGENCY_RAIN_STATION = "270397"` | **module constants, de facto source of truth**; used at `:161-162` (Open-Meteo params), `:247,250` (EA URL, cache filename) |
| `src/basement_analysis/curated_dataset.py:77` | `"station=270397"` literal | **independent hardcode** — Hive partition path when writing rain Parquet; write-side only (the reader at `:346` globs `rain_readings/` without naming the station) |
| `src/basement_analysis/summaries.py:292` | `"Environment Agency station 270397 rainfall"` literal | **independent hardcode** — human-readable data-source label |
| `tests/test_curated_dataset.py:75` | partition path fixture | mirrors `curated_dataset.py:77` |
| `prototypes/physics-and-metrology-report-mock/README.md:225` | `270397` | prototype prose |

Coordinates are already deliberately coarse (2 dp ≈ ~1 km, "Caversham") per the public-repo
constraint. No lat/lon/station occurrences exist in any TS/infra file — purely a Python concern.

## 5. Cloudflare account id / zone id

Clean. `variables.tf:1-9` declares both with **no defaults**; real values live only in gitignored
`env/production.tfvars` and `.envrc` files (confirmed untracked); `example.tfvars:2-3` holds
zero-placeholders. Nothing in Python/TS source contains a literal account/zone id.

## 6. GitHub Actions workflow (`.github/workflows/basement-site.yml`)

No hardcoded bucket names, domain, or ids — all identity arrives via `secrets.*` → env
(`R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_SITE_BUCKET`,
lines 18-22). Hardcoded pieces are path/prefix literals: `manifests/ingest`, `csv/source=x-sense`
(lines 52,54), `s3://$R2_BUCKET/parquet` (lines 73,81,92), publishable filenames `index.html`,
`physics-report.html` (line 93), plus the self-referential workflow filename (line 41) and cron
literal (line 6).

## 7. Cross-boundary literals (object-key layout and friends)

**Email-pipeline object-key layout** (`raw-emails/source=x-sense/...`, `csv/source=x-sense/...`,
`manifests/{ingest,rejections}/source=x-sense/...`) is defined independently in four code places
plus docs, with no shared schema:

- `infra/cloudflare/workers/email-ingest/src/ingest.ts:10-17,90,186-187,256` (write side; `SOURCE = "x-sense"`, template literals)
- `src/basement_analysis/raw_email_ingest.py:70,269-270,379-380` (local-parity parser; 3 literals)
- `src/basement_analysis/cli.py:99` (CLI default, another copy)
- `src/basement_analysis/hosted_curation.py:47` (read side: `manifests/ingest`)
- `.github/workflows/basement-site.yml:52,54` (read side, shell)
- Parity is guarded by tests: `email-ingest.spec.ts:16-20` asserts exact keys mirroring the Python tests.

Note: TS `PARSER_VERSION = "basement_email_ingest_worker.v1"` vs Python
`PARSER_VERSION = "basement_analysis.raw_email_ingest.v1"` are **intentionally different**
(separate parser identities), despite parallel doc comments.

**Curated `parquet` prefix**: `hosted_curation.py:42` (`s3://{bucket}/parquet`), `cli.py:152`
(help text), workflow lines 73,81,92.

**Publishable site filenames** (`index.html`, `physics-report.html`) triplicated:
`site/src/index.ts:1` (`SITE_OBJECT_KEYS` allowlist), workflow line 93 (sync includes), Python
build output filenames.

**R2 env-var names** (the contract, not values): `curated_dataset.py:21`
(`R2_CREDENTIAL_ENV_VARS` tuple — closest thing to a source of truth), `curated_dataset.py:112-114`,
`hosted_curation.py:37`, `cli.py:53-54,152`, workflow, tests, READMEs.

**Partition-spelling split**: curated sensor partition uses `source=x_sense` (underscore,
`curated_dataset.py:62`) while the raw layer uses `source=x-sense` (hyphen) throughout. Verified:
these are separate namespaces (curated Parquet partitions vs raw email/CSV object keys), each
internally consistent, and both spellings are frozen by objects already stored in R2.
