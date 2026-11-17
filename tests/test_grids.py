from dataclasses import replace
from fractions import Fraction as F
import unittest
from gridledger.delivery.service import LedgerService
from gridledger.archive.grid_store import load_grid_revision
from gridledger.grids.faces import internal_face_pairs, boundary_face_uses
from gridledger.observations.model import MassRecord, FluxRecord
from tests.test_balance import uniform_records, counts

class TestGridAcceptance(unittest.TestCase):
    def setUp(self):
        self.service = LedgerService()
        self.addCleanup(self.service.close)

    def test_invalid_geometry(self):
        g = self.service.put_grid("valid", (F(2), 1), origin=(-2, F(1, 3)), spacing=(F(1, 2), 2))
        expected = load_grid_revision(self.service.connection, g)
        for arguments in ({"spacing": (0, 1)}, {"spacing": (1, -1)}, {"shape": (0, 1)},
                          {"shape": (True, 1)}, {"shape": (F(3, 2), 1)}, {"origin": (0.0, 0)},
                          {"shape": (1,)}, {"name": ""}, {"spacing": (None, 1)}):
            kwargs = {"name": "bad", "shape": (1, 1), **arguments}
            before = counts(self.service)
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self.service.put_grid(**kwargs)
            self.assertEqual(counts(self.service), before)
            self.assertEqual(load_grid_revision(self.service.connection, g), expected)

    def test_valid_topology(self):
        g = self.service.put_grid("two", (2, 1))
        grid = load_grid_revision(self.service.connection, g)
        self.assertEqual((len(grid.cells), len(grid.faces), sum(len(f.uses) for f in grid.faces)), (2, 7, 8))
        pairs = internal_face_pairs(grid)
        self.assertEqual(len(pairs), 1)
        face, left, right = pairs[0]
        self.assertEqual(face.id, ("x", 1, 0))
        self.assertEqual((left.cell_id, right.cell_id, left.sign, right.sign), ((0, 0), (1, 0), 1, -1))
        self.assertEqual(len(boundary_face_uses(grid)), 6)
        self.assertEqual([c.area for c in grid.cells], [F(1), F(1)])

    def test_grid_scoped_records(self):
        first = self.service.put_grid("first", (1, 1))
        second = self.service.put_grid("second", (1, 1))
        m1, f1 = uniform_records(load_grid_revision(self.service.connection, first), prefix="first")
        m2, f2 = uniform_records(load_grid_revision(self.service.connection, second),
                                 values={(0, 0): (20, 21)}, prefix="second")
        self.service.put_observations(first, m1, f1)
        r2 = self.service.put_observations(second, m2, f2)
        for masses, fluxes in ((m1, []), ([], f1)):
            before = counts(self.service)
            with self.assertRaises(KeyError):
                self.service.put_observations(second, masses, fluxes)
            self.assertEqual(counts(self.service), before)
        p = self.service.compile_window(second, r2, 0, 1)
        self.assertEqual(p.endpoints[0][0].value, F(20))

    def test_batch_atomic(self):
        g = self.service.put_grid("batch", (1, 1))
        grid = load_grid_revision(self.service.connection, g)
        m, f = uniform_records(grid)
        cases = [
            ([m[0], replace(m[1], unit="kg")], f, ValueError),
            ([m[0], replace(m[0], source_id="duplicate")], f, ValueError),
            (m, [f[0], replace(f[0], source_id="duplicate")], ValueError),
            (m, [replace(f[0], side="up")], KeyError),
            ([replace(m[0], cell_id=(8, 8))], f, KeyError),
            (m, [replace(f[0], end=f[0].start)], ValueError),
            (m, [replace(f[0], unit="mass")], ValueError),
            (m, [replace(f[0], source_id=m[0].source_id)], ValueError),
        ]
        for masses, fluxes, error in cases:
            before = counts(self.service)
            with self.subTest(error=error, masses=masses, fluxes=fluxes), self.assertRaises(error):
                self.service.put_observations(g, masses, fluxes)
            self.assertEqual(counts(self.service), before)
        r = self.service.put_observations(g, m, f)
        before = counts(self.service)
        with self.assertRaises(ValueError):
            self.service.put_observations(g, [replace(m[0], value=9)])
        self.assertEqual(counts(self.service), before)
        self.assertEqual(self.service.compile_window(g, r, 0, 1).observation_id, r)

    def test_record_numeric_contract(self):
        for bad in (True, 0.5, None, "1/2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MassRecord(1, (0, 0), 0, bad, "bad")
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                FluxRecord(1, (0, 0), "east", 0, 1, bad, "bad")
