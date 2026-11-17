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

## Window corrections and effective membership

A revision's flux membership pairs each member source with a set of effective
half-open fragments inside its original record interval. Archives written
before corrections carry no fragment rows; their members are fully effective
on their complete intervals. Source records are never rewritten, shortened or
fabricated, and a fully hidden source stays in the immutable source library.
Schema version 2 adds only the fragment table; version-1 archives open and are
upgraded in place, while version-1 code refuses version-2 archives.

correct_fluxes(grid_id, fluxes, *, base_revision) requires an explicit base
revision. Each correction record subtracts its own interval from the base
revision's effective fragments on the same directed face — spanning several
old sources and filling gaps — and becomes effective on its complete original
interval, even when an identical source is reused. Other directed faces, mass
members and out-of-window fragments are inherited unchanged. Touching
correction intervals in one batch are legal and order-free; positive-length
overlaps fail with ValueError. Every accepted call, including an empty batch,
commits exactly one new child of the named base; failures commit nothing and
do not move the default latest revision.

put_observations keeps full logical-key replacement: a matching key hands
exactly its still-effective fragments to the replacement record; a key whose
base-revision domain is empty joins as a new full-interval key without
restoring hidden ancestors. It never implicitly covers other members, so
imports may still leave gaps or overlaps for compile_window to reject.

compile_window sorts each directed face's effective fragments by time, merges
continuous same-source spans into one segment, keeps disconnected spans
separate, clips to the requested window and proves exact coverage once.
Evidence keeps the original record and the clipped interval; internal faces
are checked opposite on every common subinterval. Old revisions, plans and
results never change; reads decode stored rows and never recompute.
