FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app
COPY pyproject.toml prototype.py ./
RUN uv sync --no-dev

COPY curated-data-snapshot /data/curated

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
ENTRYPOINT ["uv", "run", "python", "prototype.py"]
CMD ["--serve", "--host", "0.0.0.0", "--port", "8080", "--parquet-root", "/data/curated"]
