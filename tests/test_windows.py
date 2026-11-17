from dataclasses import replace
from fractions import Fraction as F
import unittest
from gridledger.delivery.service import LedgerService
from gridledger.archive.grid_store import load_grid_revision
from tests.test_balance import uniform_records, counts

def fractional_input(service):
    g = service.put_grid("fractional", (1, 1))
    grid = load_grid_revision(service.connection, g)
    m, f = uniform_records(grid, a=F(1, 4), b=F(3, 4), values={(0, 0): (4, F(13, 4))},
                           rates={((0, 0), "east"): [(0, F(1, 3), 2),
                                                      (F(1, 3), F(1, 2), 5),
                                                      (F(1, 2), 1, -1)]})
    return g, m, f

class TestWindowIntegration(unittest.TestCase):
    def setUp(self):
        self.service = LedgerService()
        self.addCleanup(self.service.close)

    def test_fractional_breakpoints(self):
        g, m, f = fractional_input(self.service)
        r = self.service.put_observations(g, m, f)
        p = self.service.compile_window(g, r, F(1, 4), F(3, 4))
        evidence = p.face_contributions((0, 0), "east")
        self.assertEqual([c.duration for c in evidence], [F(1, 12), F(1, 6), F(1, 4)])
        self.assertEqual([c.integral for c in evidence], [F(1, 6), F(5, 6), F(-1, 4)])
        self.assertEqual([(c.start, c.end) for c in evidence],
                         [(F(1, 4), F(1, 3)), (F(1, 3), F(1, 2)), (F(1, 2), F(3, 4))])
        self.assertEqual([(c.record.start, c.record.end) for c in evidence],
                         [(F(0), F(1, 3)), (F(1, 3), F(1, 2)), (F(1, 2), F(1))])
        self.assertEqual([c.record.source_id for c in evidence],
                         ["(0, 0)-east-0", "(0, 0)-east-1", "(0, 0)-east-2"])
        result = self.service.read_result(self.service.audit(p))
        self.assertEqual(result["cells"][0]["outflow"], F(3, 4))
        self.assertEqual(result["cells"][0]["residual"], F(0))
        self.assertEqual([s["duration"] for s in result["sources"]
                          if s["kind"] == "flux" and s["record"]["side"] == "east"],
                         [F(1, 12), F(1, 6), F(1, 4)])

    def test_missing_inputs(self):
        for missing in ("start", "end", "flux"):
            with self.subTest(missing=missing), LedgerService() as service:
                g = service.put_grid("missing", (1, 1))
                m, f = uniform_records(load_grid_revision(service.connection, g))
                if missing == "start":
                    m = m[1:]
                elif missing == "end":
                    m = m[:1]
                else:
                    f = f[1:]
                r = service.put_observations(g, m, f)
                before = counts(service)
                with self.assertRaises(ValueError):
                    service.compile_window(g, r, 0, 1)
                self.assertEqual(counts(service), before)

    def test_coverage_boundaries(self):
        cases = [
            ([(0, F(1, 2), 0), (F(1, 2), 1, 0)], True),
            ([(0, F(1, 3), 0), (F(1, 2), 1, 0)], False),
            ([(0, F(2, 3), 0), (F(1, 2), 1, 0)], False),
            ([(0, F(1, 4), 0), (F(1, 8), F(1, 2), 0), (F(5, 8), 1, 0)], False),
            ([(-2, 0, 7), (0, 1, 0), (1, 2, 9)], True),
        ]
        for segments, succeeds in cases:
            with self.subTest(segments=segments), LedgerService() as service:
                g = service.put_grid("coverage", (1, 1))
                m, f = uniform_records(load_grid_revision(service.connection, g),
                                       rates={((0, 0), "north"): segments})
                r = service.put_observations(g, m, f)
                before = counts(service)
                if succeeds:
                    p = service.compile_window(g, r, 0, 1)
                    result = service.read_result(service.audit(p))
                    self.assertEqual(result["cells"][0]["outflow"], F(0))
                else:
                    with self.assertRaises(ValueError):
                        service.compile_window(g, r, 0, 1)
                    self.assertEqual(counts(service), before)

    def test_binding_mismatch(self):
        g = self.service.put_grid("one", (1, 1))
        g2 = self.service.put_grid("two", (1, 1))
        m, f = uniform_records(load_grid_revision(self.service.connection, g))
        r = self.service.put_observations(g, m, f)
        before = counts(self.service)
        with self.assertRaises(ValueError):
            self.service.compile_window(g2, r, 0, 1)
        self.assertEqual(counts(self.service), before)
        p = self.service.compile_window(g, r, 0, 1)
        with self.assertRaises(ValueError):
            self.service.audit(replace(p, b=F(2)))
        for a, b in ((0, 0), (1, 0), (False, 1), (0, 1.0)):
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                self.service.compile_window(g, r, a, b)
