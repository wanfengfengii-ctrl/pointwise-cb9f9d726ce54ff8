# GridLedger invariants

A fixed grid ID scopes every cell (i,j) and directed side. A geometric face uses
the positive x or y direction as a stable reference. Interior faces have exactly
two opposite uses; exterior faces have one. Stored specifications reconstruct
the same rational geometry and identities on reopen.

Records carry immutable source IDs, units and complete grid-scoped logical keys.
A revision stores concrete source membership. Replacements never rewrite source
content or old revision membership. Validation finishes before a batch writes;
SQL still encloses the complete new revision and its sources in one transaction.

A window chooses exact endpoint records and clips every directed face to [a,b).
A sorted cursor proves coverage exactly once, including zero-rate segments.
A contribution stores both original and clipped intervals, and integral equals
outward total rate times clipped duration. Face length and direction are not
applied again. The common partition of each interior pair proves instantaneous
opposition, which is stronger than full-window integral cancellation.

For each cell, residual = M(b)-M(a)+sum(outward integrals). The anomaly set is
computed cell by cell. Independently, internal integrals cancel in pairs and
the sum of cell residuals equals global mass change plus exterior outflow.
Nonzero residuals are observations to report, not permission to alter input.

Plans save their concrete endpoints and contributions, and audit compares a
provided plan to its persisted binding. Results save the complete delivery
snapshot split into root, cell, exterior-face and source rows. Their counts and
ordinals must agree on reading. Publication commits all rows once or rolls all
of them back. Fixed reads decode persisted rows; they do not execute plans.

Fraction encoding preserves reduced integer numerator and positive denominator.
No float conversion is used. Every read creates detached containers. Exports
sort stable business identities and retain all source records and contributions.
A destination exception cannot mutate the stored result.

Schema initialization checks required columns, keys, relationships and version
inside its own transaction. Compatible user tables, indexes and triggers are
retained. Initialization never clears observations, recreates sample data or
advances business revisions. Physical grid and observation IDs are archive-local.
