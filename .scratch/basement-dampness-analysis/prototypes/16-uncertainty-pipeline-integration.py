from __future__ import annotations

import math
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import duckdb
import polars as pl


PROTOTYPE_BANNER = """PROTOTYPE: compare uncertainty propagation boundaries.

Question: should measurement-uncertainty objects live inside the production tabular pipeline, or
should DuckDB/Polars carry plain scalar columns and reconstruct richer uncertainty-library objects
only at analysis/report boundaries?

Run with:
    uv run python .scratch/basement-dampness-analysis/prototypes/16-uncertainty-pipeline-integration.py
"""
TEMPERATURE_ACCURACY_HALFWIDTH_C = 0.4
RELATIVE_HUMIDITY_ACCURACY_HALFWIDTH_PCT = 3.5
TEMPERATURE_QUANTIZATION_HALFWIDTH_C = 0.05
RELATIVE_HUMIDITY_QUANTIZATION_HALFWIDTH_PCT = 0.05
COVERAGE_FACTOR = 2.0


@dataclass(frozen=True)
class Reading:
    sensor_id: str
    temperature_c: float
    relative_humidity_pct: float


@dataclass(frozen=True)
class CoverageResult:
    sensor_id: str
    absolute_humidity_g_m3: float
    standard_uncertainty_g_m3: float
    expanded_uncertainty_g_m3: float


@dataclass(frozen=True)
class OptionVerdict:
    name: str
    ergonomics: str
    performance_risk: str
    testability: str
    frame_shape: str
    recommendation: str


def sample_readings() -> list[Reading]:
    return [
        Reading("basement", 18.0, 70.0),
        Reading("basement", 17.2, 76.5),
        Reading("living_room", 20.1, 58.2),
        Reading("bedroom", 19.4, 61.0),
    ]


def expanded_readings(row_count: int) -> list[Reading]:
    sensors = ["basement", "living_room", "bedroom"]
    rows: list[Reading] = []
    for index in range(row_count):
        rows.append(
            Reading(
                sensor_id=sensors[index % len(sensors)],
                temperature_c=16.5 + (index % 90) / 20,
                relative_humidity_pct=55.0 + (index % 350) / 10,
            )
        )
    return rows


def absolute_humidity_value(
    temperature_c: float,
    relative_humidity_pct: float,
) -> float:
    saturation_vapour_pressure_pa = 611.2 * math.exp(
        (17.62 * temperature_c) / (243.12 + temperature_c)
    )
    vapour_pressure_pa = (relative_humidity_pct / 100.0) * saturation_vapour_pressure_pa
    return 1000.0 * vapour_pressure_pa / (461.5 * (temperature_c + 273.15))


def standard_from_rectangular_halfwidth(halfwidth: float) -> float:
    return halfwidth / math.sqrt(3)


def absolute_humidity_sensitivities(
    temperature_c: float,
    relative_humidity_pct: float,
    step: float = 0.01,
) -> tuple[float, float]:
    temperature_sensitivity = (
        absolute_humidity_value(temperature_c + step, relative_humidity_pct)
        - absolute_humidity_value(temperature_c - step, relative_humidity_pct)
    ) / (2 * step)
    relative_humidity_sensitivity = (
        absolute_humidity_value(temperature_c, relative_humidity_pct + step)
        - absolute_humidity_value(temperature_c, relative_humidity_pct - step)
    ) / (2 * step)
    return temperature_sensitivity, relative_humidity_sensitivity


def absolute_humidity_standard_uncertainty(
    temperature_c: float,
    relative_humidity_pct: float,
) -> float:
    temperature_sensitivity, relative_humidity_sensitivity = absolute_humidity_sensitivities(
        temperature_c,
        relative_humidity_pct,
    )
    temperature_standard_uncertainty_c = math.hypot(
        standard_from_rectangular_halfwidth(TEMPERATURE_ACCURACY_HALFWIDTH_C),
        standard_from_rectangular_halfwidth(TEMPERATURE_QUANTIZATION_HALFWIDTH_C),
    )
    relative_humidity_standard_uncertainty_pct = math.hypot(
        standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_ACCURACY_HALFWIDTH_PCT),
        standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_QUANTIZATION_HALFWIDTH_PCT),
    )
    return math.hypot(
        temperature_sensitivity * temperature_standard_uncertainty_c,
        relative_humidity_sensitivity * relative_humidity_standard_uncertainty_pct,
    )


def pure_python_analysis(readings: Iterable[Reading]) -> list[CoverageResult]:
    results: list[CoverageResult] = []
    for reading in readings:
        standard_uncertainty = absolute_humidity_standard_uncertainty(
            reading.temperature_c,
            reading.relative_humidity_pct,
        )
        results.append(
            CoverageResult(
                sensor_id=reading.sensor_id,
                absolute_humidity_g_m3=absolute_humidity_value(
                    reading.temperature_c,
                    reading.relative_humidity_pct,
                ),
                standard_uncertainty_g_m3=standard_uncertainty,
                expanded_uncertainty_g_m3=COVERAGE_FACTOR * standard_uncertainty,
            )
        )
    return results


def readings_to_polars(readings: Iterable[Reading]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "sensor_id": [reading.sensor_id for reading in readings],
            "temperature_c": [reading.temperature_c for reading in readings],
            "relative_humidity_pct": [reading.relative_humidity_pct for reading in readings],
        }
    )


def absolute_humidity_expr(
    temperature_c: pl.Expr,
    relative_humidity_pct: pl.Expr,
) -> pl.Expr:
    saturation_vapour_pressure_pa = 611.2 * (
        (17.62 * temperature_c) / (243.12 + temperature_c)
    ).exp()
    vapour_pressure_pa = (relative_humidity_pct / 100.0) * saturation_vapour_pressure_pa
    return 1000.0 * vapour_pressure_pa / (461.5 * (temperature_c + 273.15))


def polars_expression_analysis(readings: Iterable[Reading]) -> pl.DataFrame:
    frame = readings_to_polars(readings)
    temperature_c = pl.col("temperature_c")
    relative_humidity_pct = pl.col("relative_humidity_pct")
    absolute_humidity = absolute_humidity_expr(temperature_c, relative_humidity_pct)
    temperature_sensitivity = (
        absolute_humidity_expr(temperature_c + 0.01, relative_humidity_pct)
        - absolute_humidity_expr(temperature_c - 0.01, relative_humidity_pct)
    ) / 0.02
    relative_humidity_sensitivity = (
        absolute_humidity_expr(temperature_c, relative_humidity_pct + 0.01)
        - absolute_humidity_expr(temperature_c, relative_humidity_pct - 0.01)
    ) / 0.02
    temperature_standard_uncertainty_c = math.hypot(
        standard_from_rectangular_halfwidth(TEMPERATURE_ACCURACY_HALFWIDTH_C),
        standard_from_rectangular_halfwidth(TEMPERATURE_QUANTIZATION_HALFWIDTH_C),
    )
    relative_humidity_standard_uncertainty_pct = math.hypot(
        standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_ACCURACY_HALFWIDTH_PCT),
        standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_QUANTIZATION_HALFWIDTH_PCT),
    )
    return frame.with_columns(
        absolute_humidity.alias("absolute_humidity_g_m3"),
        (
            (
                (temperature_sensitivity * temperature_standard_uncertainty_c) ** 2
                + (relative_humidity_sensitivity * relative_humidity_standard_uncertainty_pct) ** 2
            )
            ** 0.5
        ).alias("standard_uncertainty_g_m3"),
    ).with_columns(
        (COVERAGE_FACTOR * pl.col("standard_uncertainty_g_m3")).alias(
            "expanded_uncertainty_g_m3"
        )
    )


def polars_map_analysis(readings: Iterable[Reading]) -> pl.DataFrame:
    result_type = pl.Struct(
        {
            "absolute_humidity_g_m3": pl.Float64,
            "standard_uncertainty_g_m3": pl.Float64,
            "expanded_uncertainty_g_m3": pl.Float64,
        }
    )
    return (
        readings_to_polars(readings)
        .with_columns(
            pl.struct("temperature_c", "relative_humidity_pct")
            .map_elements(
                lambda row: {
                    "absolute_humidity_g_m3": absolute_humidity_value(
                        row["temperature_c"],
                        row["relative_humidity_pct"],
                    ),
                    "standard_uncertainty_g_m3": absolute_humidity_standard_uncertainty(
                        row["temperature_c"],
                        row["relative_humidity_pct"],
                    ),
                    "expanded_uncertainty_g_m3": COVERAGE_FACTOR
                    * absolute_humidity_standard_uncertainty(
                        row["temperature_c"],
                        row["relative_humidity_pct"],
                    ),
                },
                return_dtype=result_type,
            )
            .alias("uncertainty"),
        )
        .unnest("uncertainty")
    )


def duckdb_python_udf_analysis(readings: Iterable[Reading]) -> list[CoverageResult]:
    connection = duckdb.connect(":memory:")
    try:
        connection.create_function(
            "absolute_humidity_value",
            absolute_humidity_value,
            ["DOUBLE", "DOUBLE"],
            "DOUBLE",
        )
        connection.create_function(
            "absolute_humidity_standard_uncertainty",
            absolute_humidity_standard_uncertainty,
            ["DOUBLE", "DOUBLE"],
            "DOUBLE",
        )
        connection.execute(
            "create table readings(sensor_id varchar, temperature_c double, relative_humidity_pct double)"
        )
        connection.executemany(
            "insert into readings values (?, ?, ?)",
            [
                (reading.sensor_id, reading.temperature_c, reading.relative_humidity_pct)
                for reading in readings
            ],
        )
        rows = connection.execute(
            """
            select
                sensor_id,
                absolute_humidity_value(temperature_c, relative_humidity_pct)
                    as absolute_humidity_g_m3,
                absolute_humidity_standard_uncertainty(temperature_c, relative_humidity_pct)
                    as standard_uncertainty_g_m3,
                2 * absolute_humidity_standard_uncertainty(temperature_c, relative_humidity_pct)
                    as expanded_uncertainty_g_m3
            from readings
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        CoverageResult(
            sensor_id=str(row[0]),
            absolute_humidity_g_m3=float(row[1]),
            standard_uncertainty_g_m3=float(row[2]),
            expanded_uncertainty_g_m3=float(row[3]),
        )
        for row in rows
    ]


def duckdb_sql_macro_analysis(readings: Iterable[Reading]) -> list[CoverageResult]:
    connection = duckdb.connect(":memory:")
    try:
        connection.execute(
            """
            create macro absolute_humidity_value_sql(temperature_c, relative_humidity_pct) as (
                1000.0
                * ((relative_humidity_pct / 100.0)
                    * (611.2 * exp((17.62 * temperature_c) / (243.12 + temperature_c))))
                / (461.5 * (temperature_c + 273.15))
            )
            """
        )
        connection.execute(
            f"""
            create macro absolute_humidity_standard_uncertainty_sql(
                temperature_c,
                relative_humidity_pct
            ) as (
                sqrt(
                    (
                        (
                            (
                                absolute_humidity_value_sql(temperature_c + 0.01, relative_humidity_pct)
                                - absolute_humidity_value_sql(temperature_c - 0.01, relative_humidity_pct)
                            ) / 0.02
                        )
                        * sqrt(
                            pow({standard_from_rectangular_halfwidth(TEMPERATURE_ACCURACY_HALFWIDTH_C)}, 2)
                            + pow({standard_from_rectangular_halfwidth(TEMPERATURE_QUANTIZATION_HALFWIDTH_C)}, 2)
                        )
                    ) ** 2
                    +
                    (
                        (
                            (
                                absolute_humidity_value_sql(temperature_c, relative_humidity_pct + 0.01)
                                - absolute_humidity_value_sql(temperature_c, relative_humidity_pct - 0.01)
                            ) / 0.02
                        )
                        * sqrt(
                            pow({standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_ACCURACY_HALFWIDTH_PCT)}, 2)
                            + pow({standard_from_rectangular_halfwidth(RELATIVE_HUMIDITY_QUANTIZATION_HALFWIDTH_PCT)}, 2)
                        )
                    ) ** 2
                )
            )
            """
        )
        connection.execute(
            "create table readings(sensor_id varchar, temperature_c double, relative_humidity_pct double)"
        )
        connection.executemany(
            "insert into readings values (?, ?, ?)",
            [
                (reading.sensor_id, reading.temperature_c, reading.relative_humidity_pct)
                for reading in readings
            ],
        )
        rows = connection.execute(
            """
            select
                sensor_id,
                absolute_humidity_value_sql(temperature_c, relative_humidity_pct)
                    as absolute_humidity_g_m3,
                absolute_humidity_standard_uncertainty_sql(temperature_c, relative_humidity_pct)
                    as standard_uncertainty_g_m3,
                2 * absolute_humidity_standard_uncertainty_sql(temperature_c, relative_humidity_pct)
                    as expanded_uncertainty_g_m3
            from readings
            """
        ).fetchall()
    finally:
        connection.close()
    return [
        CoverageResult(
            sensor_id=str(row[0]),
            absolute_humidity_g_m3=float(row[1]),
            standard_uncertainty_g_m3=float(row[2]),
            expanded_uncertainty_g_m3=float(row[3]),
        )
        for row in rows
    ]


def time_call(label: str, callback: Callable[[], object]) -> tuple[str, float]:
    started_at = time.perf_counter()
    callback()
    return label, time.perf_counter() - started_at


def compare_against_baseline(
    baseline: list[CoverageResult],
    frame_or_results: pl.DataFrame | list[CoverageResult],
) -> float:
    if isinstance(frame_or_results, pl.DataFrame):
        candidates = [
            CoverageResult(
                sensor_id=str(row["sensor_id"]),
                absolute_humidity_g_m3=float(row["absolute_humidity_g_m3"]),
                standard_uncertainty_g_m3=float(row["standard_uncertainty_g_m3"]),
                expanded_uncertainty_g_m3=float(row["expanded_uncertainty_g_m3"]),
            )
            for row in frame_or_results.to_dicts()
        ]
    else:
        candidates = frame_or_results
    deltas: list[float] = []
    for left, right in zip(baseline, candidates, strict=True):
        deltas.extend(
            [
                abs(left.absolute_humidity_g_m3 - right.absolute_humidity_g_m3),
                abs(left.standard_uncertainty_g_m3 - right.standard_uncertainty_g_m3),
                abs(left.expanded_uncertainty_g_m3 - right.expanded_uncertainty_g_m3),
            ]
        )
    return max(deltas)


def option_verdicts() -> list[OptionVerdict]:
    return [
        OptionVerdict(
            name="Pure Python analysis boundary",
            ergonomics=(
                "Best place for MetroloPy/gummy or a project BudgetedQuantity type: normal "
                "functions, units, named components, correlations, and report formatting are visible."
            ),
            performance_risk=(
                "Good for headline values, event summaries, and representative rows; not ideal for "
                "millions of raw points unless vectorized scalar columns are produced first."
            ),
            testability=(
                "Strongest. The psychrometric formula, component budget, cancellation rules, and "
                "coverage formatting can be unit-tested without a database engine."
            ),
            frame_shape=(
                "Frames carry value and standard-uncertainty columns; rich uncertainty objects are "
                "constructed at the boundary."
            ),
            recommendation="Use this as the canonical uncertainty API.",
        ),
        OptionVerdict(
            name="DuckDB SQL macros or Python UDFs",
            ergonomics=(
                "SQL macros can compute scalar columns but duplicate formula logic in SQL. Python UDFs "
                "keep the canonical scalar function available to SQL, but object return values are "
                "awkward and budget structure remains hidden behind registered functions."
            ),
            performance_risk=(
                "SQL macros are plausible for scalar transforms. Python UDFs are high risk for raw "
                "time-series transforms because they cross the SQL/Python boundary repeatedly, though "
                "small summary queries are fine."
            ),
            testability=(
                "Medium. Test the Python function as canonical; SQL macro parity checks are useful "
                "but should not become the source of truth."
            ),
            frame_shape=(
                "Keep scalar columns. Do not store MetroloPy objects in DuckDB; store budget version "
                "and numeric outputs if persistence is needed."
            ),
            recommendation=(
                "Use DuckDB UDFs only for small SQL-side summaries or exploratory wiring; avoid them "
                "as the default raw-row transform."
            ),
        ),
        OptionVerdict(
            name="Polars expressions",
            ergonomics=(
                "Best tabular implementation for bulk derived columns, but it wants scalar math rather "
                "than rich Python uncertainty objects."
            ),
            performance_risk=(
                "Lowest for bulk row transforms when the calculation remains as expressions."
            ),
            testability=(
                "Good if expression output is checked against the canonical pure-Python functions on "
                "representative rows."
            ),
            frame_shape=(
                "Use scalar estimate, standard uncertainty, expanded uncertainty, and optional "
                "component columns; keep budget metadata outside the frame or in a small table."
            ),
            recommendation="Use for production bulk columns after the Python formula is validated.",
        ),
        OptionVerdict(
            name="Polars map_elements or plugin boundary",
            ergonomics=(
                "Can call the Python uncertainty API and unpack structs, but it is still a row-wise "
                "escape hatch. A custom plugin is unjustified for this phase."
            ),
            performance_risk=(
                "Medium to high. It is easier than DuckDB UDFs to keep near the Polars pipeline, but "
                "it gives up much of Polars' expression engine."
            ),
            testability=(
                "Good for wiring, but business rules still belong in the pure Python functions."
            ),
            frame_shape=(
                "Map to scalar struct fields if needed; do not leave Python objects inside a Polars "
                "Object column."
            ),
            recommendation="Use only for low-volume boundary calculations or temporary migration code.",
        ),
    ]


def print_sample_table(baseline: list[CoverageResult]) -> None:
    print("Sample pure-Python boundary results")
    print("sensor_id     absolute_humidity   standard_u   expanded_u95")
    for result in baseline:
        print(
            f"{result.sensor_id:<13} "
            f"{result.absolute_humidity_g_m3:>17.4f} "
            f"{result.standard_uncertainty_g_m3:>12.4f} "
            f"{result.expanded_uncertainty_g_m3:>14.4f}"
        )


def main() -> None:
    readings = sample_readings()
    baseline = pure_python_analysis(readings)
    polars_expression = polars_expression_analysis(readings)
    polars_map = polars_map_analysis(readings)
    duckdb_sql_macro = duckdb_sql_macro_analysis(readings)
    duckdb_python_udf = duckdb_python_udf_analysis(readings)

    print(PROTOTYPE_BANNER.strip())
    print()
    print_sample_table(baseline)
    print()
    print("Agreement with pure Python baseline")
    print(f"Polars expression max delta: {compare_against_baseline(baseline, polars_expression):.12f}")
    print(f"Polars map_elements max delta: {compare_against_baseline(baseline, polars_map):.12f}")
    print(f"DuckDB SQL macro max delta: {compare_against_baseline(baseline, duckdb_sql_macro):.12f}")
    print(f"DuckDB Python UDF max delta: {compare_against_baseline(baseline, duckdb_python_udf):.12f}")

    benchmark_readings = expanded_readings(20_000)
    timings = [
        time_call("pure Python functions", lambda: pure_python_analysis(benchmark_readings)),
        time_call("Polars expressions", lambda: polars_expression_analysis(benchmark_readings)),
        time_call("Polars map_elements", lambda: polars_map_analysis(benchmark_readings)),
        time_call("DuckDB SQL macros", lambda: duckdb_sql_macro_analysis(benchmark_readings)),
        time_call("DuckDB Python UDFs", lambda: duckdb_python_udf_analysis(benchmark_readings)),
    ]
    print()
    print("Prototype timing on 20,000 synthetic rows")
    for label, duration_seconds in timings:
        print(f"{label:<22} {duration_seconds:>8.4f}s")

    print()
    print("Boundary verdicts")
    for verdict in option_verdicts():
        print()
        print(verdict.name)
        print(f"  ergonomics: {verdict.ergonomics}")
        print(f"  performance: {verdict.performance_risk}")
        print(f"  testability: {verdict.testability}")
        print(f"  frame shape: {verdict.frame_shape}")
        print(f"  recommendation: {verdict.recommendation}")

    print()
    print("Overall decision")
    print(
        "Keep uncertainty assumptions and any MetroloPy objects in pure Python boundary functions. "
        "Use Polars expressions for bulk scalar columns once the formulas are validated. Avoid "
        "DuckDB UDFs and Polars Object columns as default raw-row production boundaries."
    )


if __name__ == "__main__":
    main()
