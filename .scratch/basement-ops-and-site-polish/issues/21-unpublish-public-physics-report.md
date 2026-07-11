# Unpublish public physics report

Type: task
Parent: ../map.md

## Question

Remove the physics/metrology report from the hosted public site while preserving local report
generation for private analysis.

Resolve when:

- Hosted builds stop writing `physics-report.html` to the public site bucket.
- The site Worker no longer serves `/basement/physics-report.html` as a live public object.
- Any existing public R2 `physics-report.html` object is removed during deployment cleanup.
- The dashboard no longer links to the physics report.
- Local report rendering remains available for private use, with tests updated to reflect the
  public/private boundary.
