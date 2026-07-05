# Adapt analysis to local partitioned Parquet DuckDB path

Type: task
Status: resolved
Parent: ../map.md

## Question

Adapt the local analysis path so the production analysis can use plain partitioned Parquet files
queried through DuckDB as its primary analytical input shape, before the Cloudflare Container
prototype tries to read equivalent Parquet objects from R2.

Keep this local-first and implementation-focused:

- derive a local curated Parquet dataset from the existing X-Sense CSV and event inputs;
- use deterministic, Cloudflare/R2-friendly object-style paths and Hive-style partitioning where
  useful;
- query the Parquet dataset through DuckDB rather than loading all analytical input from CSV files;
- preserve the existing generated dashboard/report behavior as much as practical while allowing
  prototype code to change where it improves the hosted-ready shape;
- keep Python plus `uv` as the development and execution model;
- avoid Iceberg/R2 Data Catalog for now.

Resolve with the local Parquet layout, the DuckDB query boundary, any remaining CSV-only fallback
behavior, and the command/tests that prove the static site can be generated from the curated
Parquet path.

## Answer

Implemented the local curated Parquet path in production code.

Local Parquet layout:

- `build/basement-site/curated-data/sensor_readings/source=x_sense/location_slug=<slug>/year=<YYYY>/month=<MM>/part-00000.parquet`
- `build/basement-site/curated-data/events/source=local_manual/year=<YYYY>/month=<MM>/part-00000.parquet`
- `build/basement-site/curated-data/weather_hours/source=open_meteo/year=<YYYY>/month=<MM>/part-00000.parquet`
- `build/basement-site/curated-data/rain_readings/source=environment_agency/station=270397/year=<YYYY>/month=<MM>/part-00000.parquet`

DuckDB query boundary:

- `src/basement_analysis/curated_dataset.py` owns Parquet writing and DuckDB reads.
- `build_static_site()` now rebuilds the curated dataset from CSV/API inputs by default, then reloads all analytical sensor, event, weather, and rain records through DuckDB `read_parquet(..., hive_partitioning = true)` before constructing the shared `SiteAnalysisSummary`.
- Static rendering remains downstream of the same summary contract, so dashboard/report behavior is preserved while the analytical input shape is hosted-ready.

Remaining CSV-only fallback behavior:

- CSV and weather API readers remain as the local ingestion/curation source.
- `uv run basement --reuse-curated` skips CSV/API rereads and renders directly from existing curated Parquet files.
- `--curated-data-dir <path>` allows the curated object tree to live outside the generated site directory.

Proof commands:

- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run pyright`
- `uv run pytest`
- `uv run basement`
- `uv run basement --reuse-curated`

The real local build generated `build/basement-site/index.html` and `build/basement-site/physics-report.html` from `build/basement-site/curated-data`, with 571,021 sensor rows, 3,384 weather hours, and 2,680 rain readings loaded through the curated path.
