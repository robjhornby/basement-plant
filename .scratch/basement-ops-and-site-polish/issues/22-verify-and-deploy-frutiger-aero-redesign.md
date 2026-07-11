# Verify and deploy Frutiger Aero redesign

Type: task
Status: claimed
Parent: ../map.md
Blocked by: 19, 20, 21

## Question

Run the final production verification and deploy the Frutiger Aero redesign.

Resolve when:

- The generated site is checked in a real browser at desktop and mobile widths for first fold,
  full page, chart interaction, and no console errors.
- Page weight is measured, including HTML, chart payloads, and same-origin image derivatives; any
  unexpectedly large asset is called out and either fixed or explicitly accepted.
- The page makes no external requests.
- R2 publication includes the expected HTML and image objects and excludes the public physics
  report.
- The live `https://robjhornby.com/basement/` route is smoke-tested after deploy for status,
  cache headers, ETags/304 behavior, chart render, and asset loading.
