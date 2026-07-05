# Uncertainty Pipeline Integration Prototype Notes

Prototype status: throwaway.

Question answered: should MetroloPy or another measurement-uncertainty library be integrated inside
DuckDB/Polars frames, or should the production pipeline carry scalar estimates and uncertainty
columns while reconstructing rich uncertainty objects only at analysis/report boundaries?

One command:

```bash
uv run python prototypes/uncertainty-pipeline-integration/prototype.py
```

## What The Prototype Compares

- A pure Python analysis boundary that returns ordinary result objects.
- DuckDB SQL macros and DuckDB Python UDFs for scalar columns.
- Polars expressions that keep the calculation vectorized as scalar columns.
- Polars `map_elements` returning a struct, as a row-wise escape hatch near a Polars pipeline.

## Initial Verdict

Keep the canonical uncertainty model in pure Python functions. That is the best boundary for
MetroloPy `gummy` objects, named budget components, units, common-mode/correlation rules, and report
formatting. Use Polars expressions for bulk row transforms after validating them against the pure
Python functions on representative rows.

Do not store MetroloPy objects, Python dataclasses, or Polars `Object` columns inside the production
tabular pipeline. DuckDB and Polars should carry serializable scalar fields such as:

- `absolute_humidity_g_m3`
- `absolute_humidity_standard_uncertainty_g_m3`
- `absolute_humidity_expanded_uncertainty_g_m3`
- optional component columns for inspection
- `uncertainty_budget_version` or a foreign key to budget metadata

DuckDB SQL macros are viable for scalar columns if DuckDB owns a particular transform, but they
duplicate the psychrometric formula in SQL. DuckDB Python UDFs and Polars `map_elements` are useful
as temporary wiring checks, but they should not be the first production implementation for raw
time-series calculations because they cross into Python row by row and make performance harder to
reason about.

## Verified Prototype Run

Command:

```bash
uv run python prototypes/uncertainty-pipeline-integration/prototype.py
```

Observed on the sample readings:

- Polars expression max delta from the pure Python baseline: `0.000000000000`.
- Polars `map_elements` max delta from the pure Python baseline: `0.000000000000`.
- DuckDB SQL macro max delta from the pure Python baseline: `0.000000000000`.
- DuckDB Python UDF max delta from the pure Python baseline: `0.000000000000`.

Observed prototype timings on 20,000 synthetic rows:

- Pure Python functions: about `0.03s`.
- Polars expressions: about `0.004s`.
- Polars `map_elements`: about `0.07s`.
- DuckDB SQL macros, including scratch table setup and repeated macro expansion: about `4.6s`.
- DuckDB Python UDFs, including scratch table setup and row-wise Python calls: about `7.4s`.

These timings are orientation checks only, not a formal benchmark. The useful signal is that Polars
expressions are the natural bulk-row path. DuckDB Python UDFs are now proven viable with `numpy`
installed, but row-wise Python crossings and SQL duplication should not become the default
architecture.

## Recommended Production Shape

1. Implement a small pure Python uncertainty API in `src/basement_analysis`, with serializable budget
   inputs and scalar result outputs.
2. Add a MetroloPy adapter only at report/research boundaries, once the dependency is accepted.
3. Implement equivalent Polars expressions for high-volume row calculations.
4. Test Polars outputs against the canonical Python functions on representative readings and edge
   cases.
5. Persist only scalar results and budget metadata in DuckDB/DuckLake if persistence becomes useful.

## Why This Is Not Yet Production Code

The script uses a compact fixed STH51 budget and synthetic benchmark rows. It does not model
same-sensor cancellation, daily means, autocorrelation, placement uncertainty, drift scenarios, or
Monte Carlo checks. Those belong in production modules once the local CSV-to-static-site pipeline is
being hardened.
