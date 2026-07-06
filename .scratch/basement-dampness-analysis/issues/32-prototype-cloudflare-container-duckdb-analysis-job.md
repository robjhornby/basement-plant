# Prototype Cloudflare Container DuckDB analysis job

Type: prototype
Status: claimed
Parent: ../map.md
Blocked by: 31

## Question

Can a Cloudflare Container run the required Python plus DuckDB analysis workflow against Parquet
objects in R2, under realistic deployment, startup, CPU, memory, disk, cost, and orchestration
constraints?

Build the smallest Cloudflare Container prototype, or a locally simulated equivalent that maps
closely to Cloudflare Containers, that runs normal Python with `uv`, imports DuckDB, reads plain
partitioned Parquet directly from R2 through an R2/S3-compatible path, generates representative
static publication artifacts, writes those artifacts back to R2, and identifies how a minimal
Worker control plane would trigger it. Do not include final public static-site publication,
scheduling, retries, alerts, or advanced orchestration in this prototype unless they are required
to prove the runtime path. Use the result to decide whether Containers are the hosted analysis
compute surface, or whether the project should fall back to another Cloudflare-only option.
