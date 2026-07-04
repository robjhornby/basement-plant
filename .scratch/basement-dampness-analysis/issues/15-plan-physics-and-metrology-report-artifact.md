# Plan physics and metrology report artifact

Type: prototype
Status: resolved
Parent: ../map.md
Blocked by: 06, 07, 10, 13

## Question

What should the locally generated explanatory physics/metrology report or article look like once the model, uncertainty budget, leak/rain analysis strategy, and first local static-site views are known?

Create a rough outline or mock report that explains the physics behind drying out a basement, the uncertainty model, the interpretation of dashboard values, and the limits of the evidence. The artifact should first support local static-page generation and local feedback; it can later be adapted for publication or blog posts.

## Answer

Prototype asset: [Physics And Metrology Report Mock](../prototypes/15-physics-and-metrology-report-mock.md)

The physics/metrology report should be a companion explanation page linked from the dense local dashboard, not the dashboard's first screen. The dashboard remains the fast owner-analyst view; the report explains why the displayed quantities are physically meaningful, which uncertainty assumptions are included, and how to read cautious evidence about `Basement drying`, `Weather-related leaking`, `Steady-state leaking`, `Whole-house humidity change`, and `Sensor/dehumidifier artifact`.

The report should be generated locally as Markdown/HTML from the same analysis summary objects as the dashboard. Its first structure is: report header and evidential boundary, plain-language finding summary, relative-humidity-vs-absolute-humidity explanation, psychrometric equations, event-period comparability, GUM-style uncertainty budget, comparison-reading rules, moisture-balance vocabulary, hypothesis evidence, rain/steady-leak interpretation, conclusion-changing observations, and a technical appendix.

Keep the initial audience local and analytical. Public/blog adaptation should be a later privacy and editorial pass after the analysis has stable results. The newly sharp follow-up is how the static generator should share summary objects between the dashboard and report without duplicating calculations; that should wait until [Build weather-inclusive end-to-end prototype](17-build-weather-inclusive-end-to-end-prototype.md) produces the first real local page shape.
