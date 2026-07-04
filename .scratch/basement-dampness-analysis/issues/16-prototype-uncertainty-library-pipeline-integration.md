# Prototype uncertainty-library pipeline integration

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 07, 14

## Question

How should MetroloPy or another measurement-uncertainty library integrate with the production analysis pipeline, especially across DuckDB and/or Polars boundaries?

Build a small implementation spike or design prototype after the uncertainty plan and Python project baseline are clear. Compare at least:

- isolating uncertainty propagation in pure Python analysis functions;
- using DuckDB user-defined functions;
- using Polars expressions, maps, or plugin-style boundaries if appropriate.

The output should give the user concrete architecture/implementation options to review, including ergonomics, performance risks, testability, and whether uncertainty objects should appear inside tabular frames or only at analysis boundaries.

## Answer

Prototype assets:

- [Uncertainty Pipeline Integration Prototype](../prototypes/16-uncertainty-pipeline-integration.py)
- [Uncertainty Pipeline Integration Prototype Notes](../prototypes/16-uncertainty-pipeline-integration-notes.md)

Use a pure Python uncertainty API as the canonical integration boundary. That is where MetroloPy `gummy` objects, units, named budget components, common-mode/correlation rules, cancellation assumptions, and report formatting belong. DuckDB and Polars should not carry MetroloPy objects, Python dataclasses, or Polars `Object` columns as the default production shape.

For bulk row transforms, implement scalar Polars expressions after validating them against the canonical pure Python functions on representative readings and edge cases. The frame shape should be serializable scalar columns such as absolute humidity estimate, standard uncertainty, expanded uncertainty, optional component columns, and a budget-version reference.

DuckDB SQL macros can compute equivalent scalar results, but they duplicate formula logic in SQL and should only be used if DuckDB owns a specific transform. DuckDB Python UDFs are viable with `numpy` installed and match the canonical Python output, but they are not the right default raw-row boundary because they cross the SQL/Python boundary row by row and were the slowest measured path in this spike. Polars `map_elements` is a viable low-volume escape hatch but gives up the main performance and clarity benefits of Polars expressions.

Verified command:

```bash
uv run python .scratch/basement-dampness-analysis/prototypes/16-uncertainty-pipeline-integration.py
```

The runnable paths matched the pure Python baseline on the sample rows:

- Polars expression max delta: `0.000000000000`.
- Polars `map_elements` max delta: `0.000000000000`.
- DuckDB SQL macro max delta: `0.000000000000`.
- DuckDB Python UDF max delta: `0.000000000000`.

No new wayfinder tickets were added. The decision should guide later production implementation: canonical Python functions first, Polars expression parity second, MetroloPy only at analysis/report boundaries unless a later ticket justifies broadening that dependency.
