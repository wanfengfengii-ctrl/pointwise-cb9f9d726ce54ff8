# GridLedger

GridLedger serves the simulated Estuary Environmental Computing Laboratory. Its data
processor receives uniform two-dimensional grid observations from an upstream
simulation, and its reviewer consumes fixed mass-balance reports. GridLedger
does not run that simulation. It accepts several independent grids; each audit
belongs to exactly one grid revision.

The working day is: accept a grid; check its cells and outward face identities;
import endpoint masses; import piecewise-constant outward total flow rates;
freeze an observation revision; compile a time window; inspect every cell's
residual; publish and export the fixed report to the reviewer. Reports retain
their original numbers and source records after later corrections.

## Run

Python 3.11 and its standard library are the only requirements. Run from the
repository root; no installation is needed.

    python3.11 -B -m unittest discover -s tests -v
    python3.11 -B -m gridledger.delivery.service demo --example examples/two_cells.json

The runtime manifest contains these same argv arrays. Tests use only their own
temporary directories or in-memory SQLite databases. The demo uses an in-memory
archive and the finite public sample. It asserts the hand-calculated result,
exports the real report, and prints a POINTWISE_SCENARIO record before the JSON.

## Public object API

Import LedgerService from gridledger.delivery.service and MassRecord, FluxRecord
from gridledger.observations.model. Use a service as a context manager, or close it.

* LedgerService(path=":memory:") opens or creates an archive. Reopening compatible
  archives preserves all revisions, results and user SQLite objects.
* put_grid(name, shape, origin=(0,0), spacing=(1,1)) returns an integer fixed grid ID.
  Shape accepts positive integral int/Fraction counts; origin and positive spacing
  accept int/Fraction. bool, float, null and malformed geometry raise ValueError.
  Equal names or specifications may have different immutable grid IDs.
* MassRecord(grid_id, cell_id, time, value, source_id, unit="mass") describes one
  exact endpoint observation. cell_id is (i,j).
* FluxRecord(grid_id, cell_id, side, start, end, rate, source_id, unit="mass/time")
  describes outward total flow on west/east/south/north. It is already signed
  outward and already integrated over the face spatially.
* put_observations(grid_id, masses=(), fluxes=(), base_revision=None) returns a new
  integer observation revision ID. By default it inherits the latest revision of
  that grid; an explicit base_revision permits a fixed branch. Matching logical
  keys replace members; others are inherited. Every successful call creates a
  revision, including an empty or identical batch.
* compile_window(grid_id, observation_id, a, b) returns an immutable, archived
  WindowPlan with an integer id. a and b are exact rational numbers and a<b.
* audit(plan) accepts that WindowPlan or its archived integer ID and returns a
  published result ID. Plans survive closing and reopening.
* read_result(result_id) returns a new nested dictionary containing fixed bindings,
  window, cells, anomalous_cells, boundary and sources.
* export_result(result_id, text_file_object) writes deterministic exact JSON.

For inspection, load_grid_revision(service.connection, grid_id) is available
from gridledger.archive.grid_store. GridRevision.cell/face and the functions in
gridledger.grids.faces expose immutable topology. The connection is exposed for
archive inspection and SQLite application extensions; arbitrary SQL data edits
are outside the immutable-record API.

## Input and error rules

Logical mass keys are (grid,cell,time); logical flow keys are
(grid,cell,side,start,end). Source IDs are global immutable record identities.
A correction uses a new source ID; an existing source ID may only refer to
identical content. Repeated keys in a batch, conflicting sources, wrong units
or nonpositive intervals raise ValueError. A cell, side or grid reference outside
the specified grid raises KeyError. Invalid batches leave no partial records or
revision. Imports may be incomplete for a particular window and never fill gaps,
interpolate masses or implicitly split old intervals.

Each cell needs a mass exactly at both window endpoints. Each directed face
must cover [a,b) exactly once; touching intervals are legal, gaps and positive
overlaps fail compilation with ValueError. Zero is a valid mass or flow.
Every clipped source contribution retains its original record, clipped interval,
duration and exact integral. Two sides of an internal face must be opposite
on every common time interval. Conflicts fail audit with ValueError even when
their full-window integrals cancel.

Mass change is end minus start; cell outflow is the sum of its four outward
integrals; residual is their sum. Nonzero residuals are valid published findings.
All cells are retained, and anomalous_cells contains exactly the nonzero ones.
The boundary includes only exterior faces. Global residual equals total mass
change plus boundary outflow; it does not replace local findings.

SQLite errors propagate unchanged and roll back the entire affected transaction.
Missing IDs raise KeyError. Export write errors propagate and do not alter the
archive (the target may already have received a prefix). Incompatible schemas
raise an error and are preserved rather than reset. No concurrent writers,
automatic recovery or scheduling are provided.

## Representation and regression coverage

All physical values and times use Fraction; units are mass, time and mass/time.
Coordinates, durations and integrals never pass through floats. JSON rationals
are {"$fraction":[numerator,positive_denominator]} in reduced form; immutable
tuples use {"$tuple":[...]}. decode_value in gridledger.delivery.codec restores
these exact values. Output order is stable by grid-local identities, intervals
and source IDs. Repeated exports of one fixed result are byte-identical.

The six regression files cover topology and scoped atomic imports; endpoint and
interval completeness; clipped fractional evidence; instantaneous internal-face
consistency; local and boundary balances; source corrections and frozen plans;
detached reads and exact reopen/export; schema preservation; and real SQLite
trigger failures during multitable publication. Expected balances are hand
arithmetic and independently written fractions, not calls to the implementation
being checked.

See RUNBOOK.md for a small object-input session and docs/invariants.md for
the archive-to-report invariants.
