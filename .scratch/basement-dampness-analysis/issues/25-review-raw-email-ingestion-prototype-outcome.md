# Review raw email ingestion prototype outcome

Type: grilling
Status: resolved
Parent: ../map.md
Blocked by: 19

## Question

Does the real-email ingestion prototype match the user's actual X-Sense email workflow closely
enough to become the basis for production ingestion?

Review [Prototype raw email CSV processing state](19-prototype-raw-email-csv-processing-state.md)
and [Raw Email CSV Processing State Prototype Notes](../prototypes/19-raw-email-csv-processing-state-notes.md)
with the user before any infrastructure work begins. Keep this intentionally short: the goal is not
to redesign ingestion from scratch, but to let the user accept, reject, or redirect the prototype
conclusions.

Ask for feedback on:

- whether the real sample is representative: one daily email containing all three sensor CSV
  attachments;
- whether the Gmail forwarding path is expected to preserve the original `Message-ID`, or whether
  forwarded copies may get a new identity;
- whether production ingestion should match the exact current subject and attachment filename
  pattern, or stay tolerant of subject/filename changes;
- whether the user can provide one duplicate, forwarded, or resend example before duplicate-handling
  logic is treated as proven.

Resolve this only after recording the user's direction. Then update downstream ingestion tickets if
the accepted path differs from the prototype recommendation.

## Answer

The real-email ingestion prototype is accepted as the basis for the next production ingestion step,
with intentionally narrow assumptions.

User direction:

- Assume the provided real `.eml` is representative enough: future emails can be expected to look
  basically like this one.
- Do not spend more planning time on whether Gmail forwarding preserves identities. Treat
  `Message-ID` dedupe as useful if it works, but let production reveal whether forwarded copies
  preserve or change identity.
- Match the exact current subject and attachment filename pattern for now. If that breaks later,
  fix the parser then rather than overgeneralising now.

Downstream implication: [Provision email-to-S3 ingest infrastructure](18-provision-email-to-s3-ingest-infrastructure.md)
can proceed. The production parser should start strict around the observed X-Sense email shape and
keep attachment content hashing as a backstop, but should not block infrastructure work on more
duplicate/forwarded examples.
