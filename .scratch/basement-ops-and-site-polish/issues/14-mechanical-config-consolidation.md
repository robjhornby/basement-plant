# Mechanical config consolidation

Type: task
Parent: ../map.md

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
