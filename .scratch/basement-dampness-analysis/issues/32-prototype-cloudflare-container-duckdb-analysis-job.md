# Prototype Cloudflare Container DuckDB analysis job

Type: prototype
Status: open
Parent: ../map.md
Blocked by: 31

## Question

Can a Cloudflare Container run the required Python plus DuckDB analysis workflow against Parquet
objects in R2, under realistic deployment, startup, CPU, memory, disk, cost, and orchestration
constraints?

Build the smallest Cloudflare Container prototype, or a locally simulated equivalent that maps
closely to Cloudflare Containers, that runs normal Python, imports DuckDB, reads one representative
Parquet object through an R2-compatible path, returns or writes a tiny summary, and identifies how a
Worker/Durable Object would trigger it. Use the result to decide whether Containers are the hosted
analysis compute surface, or whether the project should fall back to another Cloudflare-only option.
