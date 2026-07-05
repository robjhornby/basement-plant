# Grill hosted processing stack decision

Type: grilling
Status: open
Parent: ../map.md
Blocked by: 33

## Question

Given the researched decision tree for hosted data processing and static dashboard/report
generation, which architecture should the project pursue next?

Use the research asset from
[Research hosted processing and static generation decision tree](33-research-hosted-processing-and-static-generation-decision-tree.md)
to explain each branch to the user in practical terms before asking for a choice. Ask one question
at a time. Make the tradeoffs explicit: standard Cloudflare Workers versus Python Workers versus
Containers versus Pages/CI/local-heavy generation, package compatibility, operational complexity,
cost, reproducibility, how much Python analysis code can be reused, and how quickly the project can
get back to useful basement dampness analysis.

Resolve with the chosen direction, rejected alternatives, and the next prototype or implementation
tickets that should remain in the map.
