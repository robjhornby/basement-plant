# Establish Python project quality baseline

Type: task
Status: resolved
Parent: ../map.md
Blocked by: 01

## Question

What repository baseline should be put in place before production analysis code grows beyond the prototype?

Turn the user's Python preferences into a concrete local-development project setup proposal or implementation task: package layout, Ruff lint/format config, type-checking choice if any, test runner, dependency groups, local checks, naming conventions, and migration path from the throwaway prototype. CI can be noted as later-phase polish; do not let remote automation concerns block the local CSV-to-static-site pipeline.

## Answer

The repository now has a concrete local Python quality baseline for production analysis work:

- `pyproject.toml` describes the project, keeps runtime dependencies focused on `duckdb` and `polars`, and adds a `dev` dependency group with `ruff`, `pytest`, and `pyright`.
- Ruff is configured for formatting and linting with a 100-character line length, Python 3.14 target, import sorting, annotation checks, modernisation checks, and common correctness/style rules.
- Pyright is the type checker, set to strict mode for `src`, `tests`, and `main.py`.
- Pytest is configured to discover tests under `tests` with `src` on the import path.
- `src/basement_analysis/` is the production package skeleton, including `py.typed`.
- The project is packaged with Hatchling, explicitly includes `src/basement_analysis`, and exposes a `basement` console script.
- `tests/test_package_import.py` verifies the package import path.
- `main.py` is now a thin typed entrypoint delegating into the package.
- `README.md` documents the local checks, dependency management commands, package layout, coding conventions, and migration path from the throwaway prototype.

The prototype directory remains deliberately excluded from strict Ruff/Pyright gates. Validated prototype behavior should be migrated into `src/basement_analysis/` one calculation at a time, with focused tests, rather than hardened in place.

Verified local commands:

```bash
uv sync
uv run python -c "import basement_analysis; print(basement_analysis.__file__)"
uv run basement
uv build
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```
