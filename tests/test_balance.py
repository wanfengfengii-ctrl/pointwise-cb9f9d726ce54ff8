from dataclasses import replace
from fractions import Fraction as F
import json
import unittest
from gridledger.delivery.service import LedgerService
from gridledger.archive.grid_store import load_grid_revision
from gridledger.grids.faces import cell_face_uses
from gridledger.observations.model import MassRecord, FluxRecord

def counts(service):
    names = ("grid_revisions", "sources", "observation_revisions", "observation_members",
             "plans", "results", "result_cells", "result_faces", "result_sources")
    return {name: service.connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
            for name in names}

def uniform_records(grid, *, a=0, b=1, values=None, rates=None, prefix=""):
    values, rates = values or {}, rates or {}
    masses, fluxes = [], []
    for cell in grid.cells:
        start, end = values.get(cell.id, (F(0), F(0)))
        label = prefix + str(cell.id)
        masses.extend((MassRecord(grid.id, cell.id, a, start, label + "-start"),
                       MassRecord(grid.id, cell.id, b, end, label + "-end")))
        for use in cell_face_uses(grid, cell.id):
            segments = rates.get((cell.id, use.side), [(a, b, F(0))])
            if isinstance(segments, (int, F)):
                segments = [(a, b, segments)]
            for n, (u, v, rate) in enumerate(segments):
                fluxes.append(FluxRecord(grid.id, cell.id, use.side, u, v, rate,
                                         label + "-" + use.side + "-" + str(n)))
    return masses, fluxes

def seed_two(service, *, local=False):
    grid_id = service.put_grid("estuary", (2, 1))
    grid = load_grid_revision(service.connection, grid_id)
    values = {(0, 0): (10, 8), (1, 0): (10, 11)}
    rates = {((0, 0), "east"): 3, ((1, 0), "west"): -3,
             ((0, 0), "west"): -1, ((1, 0), "east"): 2}
    if local:
        values = {(0, 0): (10, 10), (1, 0): (10, 10)}
        rates = {((0, 0), "east"): 3, ((1, 0), "west"): -3}
    masses, fluxes = uniform_records(grid, values=values, rates=rates)
    return grid_id, service.put_observations(grid_id, masses, fluxes)

class TestUniformBalance(unittest.TestCase):
    def setUp(self):
        self.service = LedgerService()
        self.addCleanup(self.service.close)

    def test_two_cells(self):
        grid_id, revision = seed_two(self.service)
        plan = self.service.compile_window(grid_id, revision, 0, 1)
        result = self.service.read_result(self.service.audit(plan))
        self.assertEqual([(c["change"], c["outflow"], c["residual"]) for c in result["cells"]],
                         [(F(-2), F(2), F(0)), (F(1), F(-1), F(0))])
        self.assertEqual(result["anomalous_cells"], [])
        boundary = result["boundary"]
        self.assertEqual((boundary["total_change"], boundary["total_outflow"], boundary["total_residual"]),
                         (F(-1), F(1), F(0)))
        self.assertEqual(len(boundary["faces"]), 6)
        self.assertNotIn(["x", 1, 0], [face["face"] for face in boundary["faces"]])
        self.assertEqual(sum(c["integral"] for c in result["sources"] if c["kind"] == "flux"), F(1))
        print("POINTWISE_SCENARIO " + json.dumps({
            "case_id": "v1", "input": {"mass": [[10, 8], [10, 11]], "internal_rates": [3, -3]},
            "expected": ["0", "0"], "actual": [str(c["residual"]) for c in result["cells"]],
            "downstream_expected": "1", "downstream_actual": str(boundary["total_outflow"]),
            "code_paths": ["gridledger/balances/cell_accounts.py", "gridledger/balances/boundary_accounts.py",
                           "gridledger/delivery/results.py"],
            "oracle": "hand arithmetic -2+3-1=0 and 1-3+2=0; exterior -1+2=1"}))

    def test_zero_mass(self):
        g = self.service.put_grid("zero", (1, 1), spacing=(2, 3))
        grid = load_grid_revision(self.service.connection, g)
        masses, fluxes = uniform_records(grid, values={(0, 0): (0, 1)})
        r = self.service.put_observations(g, masses, fluxes)
        report = self.service.read_result(self.service.audit(self.service.compile_window(g, r, 0, 1)))
        self.assertEqual((report["cells"][0]["change"], report["cells"][0]["outflow"],
                          report["cells"][0]["residual"]), (F(1), F(0), F(1)))
        self.assertEqual(report["anomalous_cells"], [[0, 0]])

    def test_local_anomalies(self):
        g, r = seed_two(self.service, local=True)
        result = self.service.read_result(self.service.audit(self.service.compile_window(g, r, 0, 1)))
        self.assertEqual([c["residual"] for c in result["cells"]], [F(3), F(-3)])
        self.assertEqual(result["anomalous_cells"], [[0, 0], [1, 0]])
        self.assertEqual(result["boundary"]["total_residual"], F(0))

    def test_internal_face_conflict(self):
        g, r = seed_two(self.service)
        record = FluxRecord(g, (1, 0), "west", 0, 1, -2, "conflict")
        r = self.service.put_observations(g, fluxes=[record])
        p = self.service.compile_window(g, r, 0, 1)
        before = counts(self.service)
        with self.assertRaises(ValueError):
            self.service.audit(p)
        self.assertEqual(counts(self.service), before)

    def test_segmentwise_conflict(self):
        for right, succeeds in (([-1, -3], False), ([-3, -1], True)):
            with self.subTest(right=right), LedgerService() as service:
                g = service.put_grid("async", (2, 1))
                grid = load_grid_revision(service.connection, g)
                rates = {((0, 0), "east"): [(0, F(1, 2), 3), (F(1, 2), 1, 1)],
                         ((1, 0), "west"): [(0, F(1, 2), right[0]), (F(1, 2), 1, right[1])]}
                m, f = uniform_records(grid, rates=rates)
                r = service.put_observations(g, m, f)
                p = service.compile_window(g, r, 0, 1)
                if succeeds:
                    report = service.read_result(service.audit(p))
                    self.assertEqual([c["outflow"] for c in report["cells"]], [F(2), F(-2)])
                else:
                    with self.assertRaises(ValueError):
                        service.audit(p)
                    self.assertEqual(counts(service)["results"], 0)

    def test_outward_total_rate_not_density(self):
        g = self.service.put_grid("wide", (1, 1), spacing=(3, 5))
        grid = load_grid_revision(self.service.connection, g)
        m, f = uniform_records(grid, values={(0, 0): (7, 5)}, rates={((0, 0), "west"): 2})
        r = self.service.put_observations(g, m, f)
        report = self.service.read_result(self.service.audit(self.service.compile_window(g, r, 0, 1)))
        self.assertEqual(report["cells"][0]["outflow"], F(2))
        self.assertEqual(report["cells"][0]["residual"], F(0))

    def test_asynchronous_shared_face(self):
        g = self.service.put_grid("asynchronous", (2, 1))
        grid = load_grid_revision(self.service.connection, g)
        rates = {((0, 0), "east"): [(0, F(1, 3), 3), (F(1, 3), 1, 1)],
                 ((1, 0), "west"): [(0, F(1, 6), -3), (F(1, 6), F(1, 3), -3),
                                     (F(1, 3), F(1, 2), -1), (F(1, 2), 1, -1)]}
        m, f = uniform_records(grid, rates=rates,
                               values={(0, 0): (0, F(-5, 3)), (1, 0): (0, F(5, 3))})
        r = self.service.put_observations(g, m, f)
        report = self.service.read_result(self.service.audit(self.service.compile_window(g, r, 0, 1)))
        self.assertEqual([c["outflow"] for c in report["cells"]], [F(5, 3), F(-5, 3)])
        self.assertEqual([c["residual"] for c in report["cells"]], [F(0), F(0)])
