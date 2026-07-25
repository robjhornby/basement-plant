# Log

<!-- append only, one line per entry, newest at the bottom -->
<!-- fields: date (who) thread verb: what [link] -->
<!-- verbs: saw (observation) | chose (decision + reason) | did (landed work) -->

- 2026-07-12 (rob) deploy-frutiger-aero did: Frutiger Aero redesign merged (PR #4) and published to basement-site via green dispatch run [.scratch/basement-ops-and-site-polish/issues/22-verify-and-deploy-frutiger-aero-redesign.md]
- 2026-07-12 (rob) deploy-frutiger-aero saw: live smoke test found stale Worker (asset 404s, report still 200) and a re-uploaded physics-report.html in R2 — both fixes need privileged commands [.scratch/basement-ops-and-site-polish/issues/22-verify-and-deploy-frutiger-aero-redesign.md]
- 2026-07-18 (rob) dehumidifier-estimate did: next-full tank estimate inferred from basement RH, published in the site footer [.scratch/dehumidifier-next-full-estimate/PRD.md]
- 2026-07-18 (rob) site-build-cleanup did: Frutiger Aero assets pre-generated + committed, slow image tests removed, suite ~45s→~2s [.scratch/site-build-static-assets-and-test-cleanup/PRD.md]
- 2026-07-25 (agent) deploy-frutiger-aero did: live re-verify — the two 07-12 blockers are resolved; all seven frutiger-aero assets 200 image/webp, index 200 (cache-control/ETag/304 correct), physics-report.html 404, no external requests [.scratch/basement-ops-and-site-polish/issues/22-verify-and-deploy-frutiger-aero-redesign.md]
- 2026-07-25 (agent) deploy-frutiger-aero saw: two acceptance items still unverified — visual chart-interaction/console pass in a real browser, and whether physics-report.html was deleted from R2 vs just orphaned by the Worker allowlist (public route 404s either way) [.scratch/basement-ops-and-site-polish/issues/22-verify-and-deploy-frutiger-aero-redesign.md]
- 2026-07-25 (rob) deploy-frutiger-aero did: ticket 22 resolved — Rob confirmed done, visual pass accepted and R2 object accepted (public route 404s); Frutiger Aero dashboard shipped to https://robjhornby.com/basement/ [.scratch/basement-ops-and-site-polish/issues/22-verify-and-deploy-frutiger-aero-redesign.md]
- 2026-07-18 (tank-estimator) saw: PRD "Reference ground truth" extraction-cycle counts (91/135/149) are not reproducible from the spec-verbatim detection thresholds — 8 interpretation variants tried; best event-fidelity impl counts 86/130/142 while all six event timestamps match within 5 min and durations within 0.01 d [tests/test_tank_estimator_snapshot_validation.py] (migrated from COMPASS.md)
- 2026-07-25 (rob) email-ingest did: X-Sense sends emails straight to the Cloudflare ingestion address; live site's real data is driven by that feed — ticket 20 done [.scratch/basement-dampness-analysis/issues/20-configure-source-email-delivery-to-cloudflare-ingest.md]
- 2026-07-25 (agent) record-migration did: retired COMPASS.md for the STATUS.md + LOG.md record; documented the log format in AGENTS.md; carried the one live COMPASS signal into this log [AGENTS.md]
