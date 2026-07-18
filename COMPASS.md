# Compass

## Signals

- 2026-07-18 (tank-estimator TDD task) PRD "Reference ground truth" extraction-cycle counts (91/135/149) are not reproducible from the spec-verbatim detection thresholds — 8 interpretation variants tried (prominence base, smoothing window 3–13, float epsilon, scipy find_peaks, peak counting, collapse distance); best event-fidelity implementation counts 86/130/142 while all six event timestamps match within 5 minutes and durations within 0.01 d. Deviation documented in tests/test_tank_estimator_snapshot_validation.py.
