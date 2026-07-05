from __future__ import annotations

import json
import time
from pathlib import Path

import duckdb
from workers import Response, WorkerEntrypoint


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        started_at = time.perf_counter()
        object_key = "fixtures/basement-sensor.parquet"
        bucket_object = await self.env.BASEMENT_BUCKET.get(object_key)

        if bucket_object is None:
            return Response(
                json.dumps(
                    {
                        "ok": False,
                        "error": f"Missing R2 object: {object_key}",
                        "duckdb_version": duckdb.__version__,
                    },
                    indent=2,
                ),
                status=404,
                headers={"content-type": "application/json"},
            )

        parquet_bytes = await bucket_object.arrayBuffer()
        fixture_path = Path("/tmp/basement-sensor.parquet")
        fixture_path.write_bytes(bytes(parquet_bytes))

        connection = duckdb.connect(":memory:")
        connection.execute("SET threads = 1")
        connection.execute("SET memory_limit = '96MB'")
        summary = connection.execute(
            """
            SELECT
                count(*) AS row_count,
                min(observed_at) AS first_observed_at,
                max(observed_at) AS last_observed_at,
                avg(relative_humidity_percent) AS average_relative_humidity_percent,
                avg(temperature_celsius) AS average_temperature_celsius
            FROM read_parquet(?)
            """,
            [str(fixture_path)],
        ).fetchone()

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 3)
        return Response(
            json.dumps(
                {
                    "ok": True,
                    "duckdb_version": duckdb.__version__,
                    "elapsed_ms": elapsed_ms,
                    "summary": {
                        "row_count": summary[0],
                        "first_observed_at": str(summary[1]),
                        "last_observed_at": str(summary[2]),
                        "average_relative_humidity_percent": summary[3],
                        "average_temperature_celsius": summary[4],
                    },
                },
                indent=2,
            ),
            headers={"content-type": "application/json"},
        )
