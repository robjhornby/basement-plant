from __future__ import annotations

from pathlib import Path

import duckdb


def main() -> None:
    output_path = Path("fixtures/basement-sensor.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE readings AS
        SELECT * FROM (
            VALUES
                (TIMESTAMP '2026-07-01 00:00:00', 20.1, 74.2),
                (TIMESTAMP '2026-07-01 01:00:00', 20.0, 74.8),
                (TIMESTAMP '2026-07-01 02:00:00', 19.9, 75.1),
                (TIMESTAMP '2026-07-01 03:00:00', 19.8, 75.4)
        ) AS rows(
            observed_at,
            temperature_celsius,
            relative_humidity_percent
        )
        """
    )
    connection.execute(
        "COPY readings TO ? (FORMAT parquet, COMPRESSION zstd)",
        [str(output_path)],
    )
    print(output_path)


if __name__ == "__main__":
    main()
