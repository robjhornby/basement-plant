# Prototype uncertainty-library pipeline integration

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 07, 14

## Question

How should MetroloPy or another measurement-uncertainty library integrate with the production analysis pipeline, especially across DuckDB and/or Polars boundaries?

Build a small implementation spike or design prototype after the uncertainty plan and Python project baseline are clear. Compare at least:

- isolating uncertainty propagation in pure Python analysis functions;
- using DuckDB user-defined functions;
- using Polars expressions, maps, or plugin-style boundaries if appropriate.

The output should give the user concrete architecture/implementation options to review, including ergonomics, performance risks, testability, and whether uncertainty objects should appear inside tabular frames or only at analysis boundaries.
