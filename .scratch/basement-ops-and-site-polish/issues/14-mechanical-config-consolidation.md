# Mechanical config consolidation

Type: task
Parent: ../map.md
Status: resolved

## Question

Apply the small mechanical cleanup specified by
[Assess infra config spread and environment-variable consolidation](05-assess-infra-config-and-env-vars.md),
without introducing cross-tool config generation or heavier machinery.

Resolve when:

- The Environment Agency rainfall station id has one Python source of truth, reused by
  `static_site.py`, `curated_dataset.py`, `summaries.py`, and their tests.
- The raw X-Sense email object-key prefix has one Python source of truth, reused by
  `raw_email_ingest.py`, `cli.py`, and tests.
- The OpenTofu `zone_name` variable no longer defaults to `robjhornby.com`; the tracked example
  tfvars uses a neutral placeholder, while production keeps the real value in gitignored tfvars.
- TypeScript test fixtures that only need a representative URL/email use neutral example domains
  instead of `robjhornby.com`; the live site Worker route in `wrangler.jsonc` remains the single
  hardcoded deployed domain occurrence.
- Tests, Ruff, formatting, and Pyright pass.

Keep unchanged:

- Wrangler bucket names/routes, because Wrangler cannot read tofu variables and drift fails loud.
- Documentation prose that describes the public deployment URL.
- Cross-language object-key layout literals outside Python, because the stored R2 layout is frozen
  and parity tests are the cheaper enforcement mechanism.

## Answer

All four consolidations applied; every check passes (35 pytest, 8+8 Worker vitest, Ruff lint +
format, strict Pyright, `tofu validate`).

- **Station id**: `ENVIRONMENT_AGENCY_RAIN_STATION = "270397"` now lives in `summaries.py` — the
  lowest module in the import graph (`curated_dataset` and `static_site` both already import from
  it, so no new module and no cycles). `static_site.py` imports it instead of redefining it,
  `curated_dataset.py` builds the `station=` partition path from it, `summaries.py` uses it in the
  weather-sources label, and `test_curated_dataset.py` asserts the partition path via the constant.
- **Raw key prefix**: `X_SENSE_RAW_OBJECT_KEY_PREFIX = "raw-emails/source=x-sense"` is a module
  constant in `raw_email_ingest.py`, used as the `process_raw_email_batch` default; `cli.py`
  imports it for the `--raw-object-key-prefix` argparse default, and `test_raw_email_ingest.py`
  uses it for both the input prefix and the expected raw-object key.
- **Tofu zone_name**: the `default = "robjhornby.com"` is removed (and the `zone_id` description
  no longer names the domain); `example.tfvars` now sets `zone_name = "example.com"` as a required
  value; the gitignored `production.tfvars` sets the real `zone_name = "robjhornby.com"`.
- **TS fixtures**: `site.spec.ts` fetches against `https://example.test/...` (the Worker derives
  redirects from the request URL, so nothing depended on the real domain) and
  `email-ingest.spec.ts` uses `basement-ingest@example.test`, matching the Python tests'
  `example.test` convention.

Remaining tracked-code occurrences of the domain are exactly the sanctioned set: the site Worker
route in `wrangler.jsonc` (the deploy contract) plus docs/README prose and one dashboard-navigation
comment in `email_routing.tf`. Bucket names, wrangler routes, and non-Python object-key literals
were left alone per the keep-unchanged list.
