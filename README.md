# Basement

Local basement dampness analysis and static reporting tools.

## Python Baseline

Use `uv` for all Python commands and dependency changes.

Local checks:

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Development dependencies live in the `dev` dependency group:

```bash
uv add --dev <package>
uv remove --dev <package>
```

Runtime dependencies should stay limited to libraries needed by the analysis and generated reports.

The project is packaged from `src/basement_analysis/` using Hatchling. After
`uv sync`, the package is importable in `uv run` commands and the console script
is available as:

```bash
uv run basement
```

That command builds the local static basement dashboard at
`build/basement-site/index.html`. The default build derives a local partitioned
Parquet analytical dataset at `build/basement-site/curated-data/`, then reads it
through DuckDB before rendering the dashboard and report. Use `--refresh-weather`
to refetch public weather API data instead of using the local cache.

To rebuild the site from an existing curated dataset without rereading CSVs or
calling weather APIs:

```bash
uv run basement --reuse-curated
```

Use `--curated-data-dir <path>` to place or read the curated Parquet dataset
outside the generated site directory.

To parse downloaded raw X-Sense `.eml` files into the Cloudflare/R2 object-key
layout locally:

```bash
uv run basement ingest-emails \
  --raw-email-dir data/email \
  --object-store-dir build/basement-ingest-objects
```

The command scans for `.eml` files recursively, copies raw messages under
`raw-emails/source=x-sense/`, extracts first-seen valid CSV attachments under
`csv/source=x-sense/`, and writes ingest manifests under `manifests/ingest/`.
If you download objects from R2 with their key structure already present under
the input directory, pass `--raw-object-key-prefix ""` to preserve those local
relative paths as object keys.

## Layout

- `src/basement_analysis/` is the production package. New analysis, physics,
  uncertainty, ingestion, and report-generation code should start here.
- `tests/` contains automated tests for production code.
- `prototypes/` contains throwaway prototypes, one prototype per subdirectory.
  Do not harden them in place; migrate validated calculations into `src/` with tests.
- `infra/` contains durable infrastructure definitions and notes that are expected
  to survive beyond a single wayfinding ticket.
- `data/` contains local sensor exports and event CSVs.
- `.scratch/` contains local issue-tracker artifacts only. Do not put durable
  implementation code or reusable infrastructure there.

## Coding Conventions

- Prefer fully typed functions and dataclasses or small typed value objects for
  domain records.
- Use full-name `snake_case` variables for analysis quantities. Avoid terse names
  for physical values, sensor fields, and uncertainty terms.
- Keep pure calculations separate from file I/O and report rendering so physics
  behavior is testable.
- Treat prototype-derived claims as assumptions until supported by tests,
  event data, or documented sources.

## Migration Path

1. Move one validated prototype calculation at a time into `src/basement_analysis/`.
2. Add focused tests for the migrated behavior before wiring it into a pipeline.
3. Keep CSV parsing, event handling, psychrometric calculations, uncertainty
   propagation, weather joins, and static rendering as separate modules unless
   real duplication appears.
4. Use the prototype reports only as reference outputs while replacing them with
   tested production modules.
