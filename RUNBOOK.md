# Offline processing runbook

Use Python 3.11 from the project root. No setup command or external data is needed.
The executable argv is recorded in .pointwise-runtime.json; run-manifest.json
also lists the focused regression groups without replacing full discovery.

    python3.11 -B -m unittest discover -s tests -v
    python3.11 -B -m gridledger.delivery.service demo --example examples/two_cells.json

The sample contains two unit cells, four endpoint records and all eight directed
face rates. The left account is change -2, outflow 2, residual 0; the right account
is change 1, outflow -1, residual 0. The six exterior face uses sum to outflow 1.
No flow is synthesized by the demo; the finite sample explicitly includes zeros.

A minimal in-memory object-input session:

    from fractions import Fraction as F
    from io import StringIO
    from gridledger.delivery.service import LedgerService
    from gridledger.observations.model import MassRecord, FluxRecord

    with LedgerService() as ledger:
        g = ledger.put_grid("one", (1, 1))
        masses = [MassRecord(g, (0,0), 0, 0, "mass-start"),
                  MassRecord(g, (0,0), 1, F(-1,3), "mass-end")]
        flows = [FluxRecord(g, (0,0), side, 0, 1,
                            F(1,3) if side == "east" else F(0), "flow-" + side)
                 for side in ("west", "east", "south", "north")]
        r = ledger.put_observations(g, masses, flows)
        p = ledger.compile_window(g, r, 0, 1)
        result_id = ledger.audit(p)
        report = ledger.read_result(result_id)
        assert report["cells"][0]["residual"] == 0
        target = StringIO()
        ledger.export_result(result_id, target)
        print(target.getvalue())

For persistent work, pass a project-owned database path to LedgerService.
Keep returned grid, observation, plan and result IDs. Reopen that same path
and audit a saved plan ID or read/export a saved result ID. Reading a result
does not load current observations or run the balance algorithm.

To correct an observation, import the same logical key with a new source ID.
The new revision inherits all other records. An explicitly chosen older base
revision creates a branch. Changing segment boundaries adds different logical
keys; remove overlap from the input design or compile a different revision.
The API never silently interprets a new interval as deletion of an old interval.

To investigate a rejected window, check its exact endpoints and each directed
face's complete half-open coverage. To investigate rejected internal consistency,
inspect the source IDs and common interval in the ValueError. Do not replace
conflicting observations by an average. To investigate a valid nonzero residual,
inspect report["cells"], report["anomalous_cells"] and the original records in
report["sources"]; a global zero does not imply local agreement.

A failed destination can contain partial text. Retry export from the same result
ID into another target; the fixed archive remains unchanged. Publication errors
produce no result ID and no partial result rows. Tests use real SQLite triggers
to check this behavior, then remove the trigger and publish a successful control.
