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
`build/basement-site/index.html`. Use `--refresh-weather` to refetch public
weather API data instead of using the local cache.

## Layout

- `src/basement_analysis/` is the production package. New analysis, physics,
  uncertainty, ingestion, and report-generation code should start here.
- `tests/` contains automated tests for production code.
- `prototypes/basement_dehumidifier/` remains a throwaway evidence source. Do
  not harden it in place; migrate validated calculations into `src/` with tests.
- `data/` contains local sensor exports and event CSVs.
- `.scratch/` contains local issue-tracker artifacts and is not part of the
  production code baseline.

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
