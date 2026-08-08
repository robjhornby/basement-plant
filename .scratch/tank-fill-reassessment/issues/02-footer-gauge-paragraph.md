# Render the fuel-gauge footer paragraph

Type: task
Parent: ../PRD.md
Status: ready-for-agent
Blocked by: 01

## Question

Render the gauge state from issue 01 as the site footer paragraph, per `../PRD.md`
("Footer rendering"), replacing the current next-full sentence.

Resolve when:

- The footer emits the cumulative lead ("filled N times … X litres") plus exactly one state
  sentence (filling / full-or-overdue / not-running) using the PROPOSED wording in the PRD —
  **confirm the exact wording with Rob first**, then pin it verbatim here before writing tests.
- Number formatting matches the PRD (percent to nearest 5%, litres to nearest whole, time to
  nearest half day; reuse `uncertainty_words`; local-time frame, 24-hour, weekday + day + abbr
  month).
- The "about full" state boundary (fraction threshold for switching filling → full-or-overdue) is
  chosen against real snapshot output and recorded in the Answer.
- Site-render tests assert the paragraph verbatim after the sources paragraph in each state and its
  absence on estimator failure; failure still omits the paragraph, warns in the build log, and
  never blocks publication.

## Comments

Wording is deliberately left PROPOSED in the PRD — do not ship copy Rob hasn't seen. Bring the
three real-state renderings (from the current snapshot) to him, adjust, then freeze.
