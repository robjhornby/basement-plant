# Define local static site audience, privacy, and core views

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 01, 05, 08, 10, 12

## Question

Who is the local static dashboard/report for, and which views should be included in the first locally viewable version?

Use the local-first direction from [Refocus roadmap on local CSV-to-static-site first](21-refocus-roadmap-on-local-csv-to-static-site-first.md): local CSV files are the data source, the full analysis runs locally, and the pipeline generates static web pages locally. Do not decide remote hosting, `robjhornby.com` publishing, SES/S3 ingestion, or server automation in this ticket.

Keep the later publication privacy boundary in mind, but optimize this ticket for local feedback. Confirm the intended audience and which local views matter most: latest local run summary, daily trends, raw measurement plots, rain overlays, leak hypothesis evidence, uncertainty-aware report values, physics explainer, raw data explorer, article embeds, or a deliberately small first page.

## Answer

The first `Local static site` is for the `Owner-analyst`: the homeowner analysing their own basement data and checking whether the analysis is physically defensible. It is not for public readers yet, and should privilege fast local feedback, auditability, and analytical usefulness over article polish.

The first locally viewable version should be one dense analytical page with these views:

- latest run summary and data freshness;
- daily absolute-humidity and relative-humidity trends, with uncertainty where available;
- raw basement/control measurement plots;
- rainfall and outdoor-humidity overlay;
- cautious hypothesis evidence panel for `Basement drying`, `Weather-related leaking`, and `Steady-state leaking`.

Defer the physics explainer, raw data explorer, article/embed structure, and publication-grade narrative until the first page exposes what the analysis actually says.

Privacy posture for this ticket: local-only output may include detailed timestamps, sensor labels, and diagnostic views needed for analysis. Later public publication needs a separate privacy/pass-through decision before any generated artifacts are published.
