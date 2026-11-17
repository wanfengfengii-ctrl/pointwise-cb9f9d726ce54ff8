from gridledger.archive.schema import connect_archive
from gridledger.archive.grid_store import save_grid_revision, load_grid_revision
from gridledger.archive.observation_store import (
    load_source_record, save_observation_revision, load_observation_revision)
from gridledger.archive.plan_store import save_plan, load_plan, publish_result, load_result_rows
from gridledger.observations.revisions import build_observation_revision
from gridledger.windows.compiler import compile_window_plan
from gridledger.windows.model import WindowPlan
from gridledger.balances.execution import execute_balance
from gridledger.delivery.results import build_result_snapshot, restore_result_snapshot
from gridledger.delivery.export import write_result_json

class LedgerService:
    def __init__(self, path=":memory:"):
        self.connection = connect_archive(path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def close(self):
        self.connection.close()

    def put_grid(self, name, shape, origin=(0, 0), spacing=(1, 1)):
        return save_grid_revision(self.connection, name, shape, origin, spacing)

    def put_observations(self, grid_id, masses=(), fluxes=(), *, base_revision=None):
        grid = load_grid_revision(self.connection, grid_id)
        if base_revision is None:
            row = self.connection.execute(
                "SELECT MAX(id) FROM observation_revisions WHERE grid_id=?", (grid_id,)).fetchone()
            base_revision = row[0]
        previous = load_observation_revision(self.connection, base_revision) if base_revision is not None else None
        sources = {sid: load_source_record(self.connection, sid)
                   for (sid,) in self.connection.execute("SELECT source_id FROM sources")}
        candidate = build_observation_revision(grid, previous, masses, fluxes, sources)
        return save_observation_revision(self.connection, candidate).id

    def compile_window(self, grid_id, observation_id, a, b):
        grid = load_grid_revision(self.connection, grid_id)
        observation = load_observation_revision(self.connection, observation_id)
        return save_plan(self.connection, compile_window_plan(grid, observation, a, b))

    def audit(self, plan):
        if isinstance(plan, WindowPlan):
            if plan.id is None:
                raise ValueError("plan has not been archived")
            fixed = load_plan(self.connection, plan.id)
            if fixed != plan:
                raise ValueError("plan differs from archived binding")
        elif isinstance(plan, int) and not isinstance(plan, bool):
            fixed = load_plan(self.connection, plan)
        else:
            raise ValueError("expected archived WindowPlan or plan id")
        grid = load_grid_revision(self.connection, fixed.grid_id)
        result = execute_balance(grid, fixed)
        return publish_result(self.connection, build_result_snapshot(fixed, result))

    def read_result(self, result_id):
        return restore_result_snapshot(load_result_rows(self.connection, result_id))

    def export_result(self, result_id, target):
        write_result_json(self.read_result(result_id), target)

def main():
    import argparse
    from fractions import Fraction
    import json
    from pathlib import Path
    from gridledger.grids.faces import cell_face_uses
    from gridledger.observations.model import MassRecord, FluxRecord

    parser = argparse.ArgumentParser(description="Offline uniform-grid observation audit")
    parser.add_argument("command", choices=["demo"])
    parser.add_argument("--example", default="examples/two_cells.json")
    args = parser.parse_args()
    sample = json.loads(Path(args.example).read_text(encoding="utf-8"))
    with LedgerService() as service:
        grid_id = service.put_grid(**sample["grid"])
        grid = load_grid_revision(service.connection, grid_id)
        masses, fluxes = [], []
        for item in sample["masses"]:
            masses.append(MassRecord(grid_id, tuple(item["cell"]), item["time"],
                                     item["value"], item["source"]))
        rates = {(tuple(item["cell"]), item["side"]): item["rate"] for item in sample["rates"]}
        for cell in grid.cells:
            for use in cell_face_uses(grid, cell.id):
                source = "flow-" + str(cell.id[0]) + "-" + str(cell.id[1]) + "-" + use.side
                fluxes.append(FluxRecord(grid_id, cell.id, use.side, 0, 1,
                                         rates[(cell.id, use.side)], source))
        revision = service.put_observations(grid_id, masses, fluxes)
        plan = service.compile_window(grid_id, revision, 0, 1)
        result_id = service.audit(plan)
        snapshot = service.read_result(result_id)
        actual = {"residuals": [str(c["residual"]) for c in snapshot["cells"]],
                  "boundary_outflow": str(snapshot["boundary"]["total_outflow"])}
        expected = {"residuals": ["0", "0"], "boundary_outflow": "1"}
        if actual != expected:
            raise AssertionError((actual, expected))
        import io
        from gridledger.delivery.codec import decode_value
        target = io.StringIO()
        service.export_result(result_id, target)
        exported = decode_value(json.loads(target.getvalue()))
        downstream = [str(c["change"]) for c in exported["cells"]]
        if downstream != ["-2", "1"]:
            raise AssertionError(downstream)
        print("POINTWISE_SCENARIO " + json.dumps({
            "case_id": "v1", "input": sample, "expected": expected, "actual": actual,
            "downstream_expected": ["-2", "1"], "downstream_actual": downstream,
            "code_paths": ["gridledger/windows/compiler.py", "gridledger/balances/execution.py",
                           "gridledger/archive/plan_store.py", "gridledger/delivery/export.py"],
            "oracle": "independent two-cell arithmetic: -2+3-1=0; 1-3+2=0"}))
        print(target.getvalue(), end="")

if __name__ == "__main__":
    main()
