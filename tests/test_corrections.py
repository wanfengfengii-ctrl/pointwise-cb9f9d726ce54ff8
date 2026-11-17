"""Public boundary regressions for window flux corrections.

Expected values are hand arithmetic, independent of the implementation.
"""
from fractions import Fraction as F
import sqlite3
import tempfile
import unittest
from pathlib import Path
from gridledger.delivery.service import LedgerService
from gridledger.archive.observation_store import load_observation_revision
from gridledger.observations.model import MassRecord, FluxRecord
from tests.test_balance import counts

SIDES = ("west", "east", "south", "north")


def seed_cell(service, extra_masses=(), north=None):
    g = service.put_grid("boundary", (1, 1))
    masses = [MassRecord(g, (0, 0), 0, 0, "m0"),
              MassRecord(g, (0, 0), 3, -6, "m3")]
    masses.extend(MassRecord(g, (0, 0), t, v, sid) for t, v, sid in extra_masses)
    fluxes = []
    for side in SIDES:
        if side == "east":
            specs = [(0, 3, 2, "A")]
        elif side == "north" and north is not None:
            specs = north
        else:
            specs = [(0, 3, 0, "zero-" + side)]
        fluxes.extend(FluxRecord(g, (0, 0), side, a, b, rate, sid)
                      for a, b, rate, sid in specs)
    return g, service.put_observations(g, masses, fluxes)


def east_rows(service, g, revision, a=0, b=3):
    plan = service.compile_window(g, revision, a, b)
    return [(c.record.source_id, c.start, c.end)
            for c in plan.face_contributions((0, 0), "east")]


class TestCorrectionBoundaries(unittest.TestCase):
    def test_v1_archive_without_fragment_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v1.sqlite"
            with LedgerService(path) as service:
                g, r = seed_cell(service)
                # Simulate an archive written by V1: no fragment table at all.
                service.connection.execute("DROP TABLE observation_flux_fragments")
                service.connection.execute("PRAGMA user_version = 1")
            with LedgerService(path) as service:
                # The V1 revision still compiles with full-interval membership.
                self.assertEqual(east_rows(service, g, r), [("A", 0, 3)])
                self.assertEqual(
                    service.read_result(service.audit(
                        service.compile_window(g, r, 0, 3)))["cells"][0]["outflow"], F(6))
                r2 = service.correct_fluxes(
                    g, [FluxRecord(g, (0, 0), "east", 1, 2, 5, "B")], base_revision=r)
                self.assertEqual(east_rows(service, g, r2),
                                 [("A", 0, 1), ("B", 1, 2), ("A", 2, 3)])
            with LedgerService(path) as service:
                self.assertEqual(east_rows(service, g, r2),
                                 [("A", 0, 1), ("B", 1, 2), ("A", 2, 3)])
                self.assertEqual(east_rows(service, g, r), [("A", 0, 3)])

    def test_base_revision_validation(self):
        with LedgerService() as service:
            g, r = seed_cell(service)
            for bad in (None, True, 0, -1, F(1, 2), 1.5, "1"):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    service.correct_fluxes(g, [], base_revision=bad)
            with self.assertRaises(KeyError):
                service.correct_fluxes(g, [], base_revision=r + 100)
            with self.assertRaises(KeyError):
                service.correct_fluxes(g + 100, [], base_revision=r)

    def test_parent_and_mass_key_inheritance(self):
        with LedgerService() as service:
            g, r = seed_cell(service)
            r2 = service.correct_fluxes(
                g, [FluxRecord(g, (0, 0), "east", 1, 2, 5, "B")], base_revision=r)
            loaded = load_observation_revision(service.connection, r2)
            self.assertEqual(loaded.parent_id, r)
            self.assertEqual(loaded.masses,
                             load_observation_revision(service.connection, r).masses)
            # The base revision is frozen; the correction does not reach back.
            self.assertEqual(east_rows(service, g, r), [("A", 0, 3)])
            # Mass keys still replace completely on a corrected base.
            r3 = service.put_observations(
                g, masses=[MassRecord(g, (0, 0), 3, -9, "m3b")], base_revision=r2)
            report = service.read_result(service.audit(service.compile_window(g, r3, 0, 3)))
            # change -9-0=-9; east 2*1+5*1+2*1=9; residual 0.
            self.assertEqual([(c["change"], c["outflow"], c["residual"])
                              for c in report["cells"]], [(F(-9), F(9), F(0))])

    def test_outside_gap_survives_other_face_correction(self):
        with LedgerService() as service:
            g, r = seed_cell(service, north=[(0, 1, 0, "N1")])
            r2 = service.correct_fluxes(
                g, [FluxRecord(g, (0, 0), "east", 1, 2, 5, "B")], base_revision=r)
            with self.assertRaises(ValueError):
                service.compile_window(g, r2, 0, 3)  # north gap [1,3) preserved
            r3 = service.correct_fluxes(
                g, [FluxRecord(g, (0, 0), "north", 1, 3, 0, "N2")], base_revision=r2)
            report = service.read_result(service.audit(service.compile_window(g, r3, 0, 3)))
            self.assertEqual(report["cells"][0]["outflow"], F(9))  # east 9, north 0
            self.assertEqual(report["cells"][0]["residual"], F(3))

    def test_subwindow_clips_effective_fragments(self):
        with LedgerService() as service:
            g, r = seed_cell(service, extra_masses=[(F(1, 2), -1, "mh"),
                                                    (F(5, 2), -8, "m5h")])
            r2 = service.correct_fluxes(
                g, [FluxRecord(g, (0, 0), "east", 1, 2, 5, "B")], base_revision=r)
            plan = service.compile_window(g, r2, F(1, 2), F(5, 2))
            rows = [(c.record.source_id, c.start, c.end, c.integral)
                    for c in plan.face_contributions((0, 0), "east")]
            # A[1/2,1)=1, B[1,2)=5, A[2,5/2)=1; original records keep [0,3)/[1,2).
            self.assertEqual(rows, [("A", F(1, 2), F(1), F(1)),
                                    ("B", F(1), F(2), F(5)),
                                    ("A", F(2), F(5, 2), F(1))])
            report = service.read_result(service.audit(plan))
            # change -8-(-1)=-7; outflow 1+5+1=7; residual 0.
            self.assertEqual([(c["change"], c["outflow"], c["residual"])
                              for c in report["cells"]], [(F(-7), F(7), F(0))])

    def test_fragment_write_failure_is_atomic(self):
        with LedgerService() as service:
            g, r = seed_cell(service)
            before = counts(service)
            fragments_before = service.connection.execute(
                "SELECT COUNT(*) FROM observation_flux_fragments").fetchone()[0]
            service.connection.execute(
                "CREATE TRIGGER reject_fragment BEFORE INSERT ON observation_flux_fragments "
                "BEGIN SELECT RAISE(ABORT,'fragment-write'); END")
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    service.correct_fluxes(
                        g, [FluxRecord(g, (0, 0), "east", 1, 2, 5, "B")], base_revision=r)
            finally:
                service.connection.execute("DROP TRIGGER reject_fragment")
            self.assertEqual(counts(service), before)
            self.assertEqual(service.connection.execute(
                "SELECT COUNT(*) FROM observation_flux_fragments").fetchone()[0],
                fragments_before)
            self.assertFalse(service.connection.in_transaction)
            # The default base for the ordinary entry is unchanged by the failure.
            self.assertEqual(east_rows(service, g, service.put_observations(g)),
                             [("A", 0, 3)])


if __name__ == "__main__":
    unittest.main()
