"""Public inputs and hand-calculated checks; no V2 implementation."""
import argparse
from dataclasses import replace
from fractions import Fraction as F
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gridledger.delivery.service import LedgerService
from gridledger.delivery.codec import decode_value, canonical_json
from gridledger.archive.observation_store import load_source_record
from gridledger.observations.model import MassRecord, FluxRecord

SIDES = ("west", "east", "south", "north")


def seed(service, *, shape=(1, 1), east=None):
    g = service.put_grid("correction-example", shape)
    masses, fluxes = [], []
    for i in range(shape[0]):
        cell = (i, 0)
        end = -6 if i == 0 else 6
        masses.extend((MassRecord(g, cell, 0, 0, "m%s-start" % i),
                       MassRecord(g, cell, 3, end, "m%s-end" % i)))
        for side in SIDES:
            if i == 0 and side == "east":
                specs = east if east is not None else [(0, 3, 2, "A")]
            elif i == 1 and side == "west":
                specs = [(0, 1, -2, "R1"), (1, 3, -2, "R2")]
            else:
                specs = [(0, 3, 0, "zero-%s-%s" % (i, side))]
            fluxes.extend(FluxRecord(g, cell, side, a, b, rate, sid)
                          for a, b, rate, sid in specs)
    return g, service.put_observations(g, masses, fluxes, base_revision=None)


def record(g, sid, a, b, rate, cell=(0, 0), side="east"):
    return FluxRecord(g, cell, side, a, b, rate, sid)


def rows(plan, cell=(0, 0), side="east"):
    return [(c.record.source_id, c.start, c.end, c.record.start,
             c.record.end, c.record.rate) for c in plan.face_contributions(cell, side)]


def exported(service, rid):
    target = io.StringIO()
    service.export_result(rid, target)
    return target.getvalue()


def counts(service):
    return tuple(service.connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                 for name in ("sources", "observation_revisions", "observation_members",
                              "plans", "results", "result_cells", "result_faces", "result_sources"))


class CorrectionCases(unittest.TestCase):
    def test_middle_and_original_entry(self):
        with LedgerService() as s:
            g, r = seed(s)
            old = s.compile_window(g, r, 0, 3)
            old_id = s.audit(old)
            old_text = exported(s, old_id)
            a = load_source_record(s.connection, "A")
            r2 = s.correct_fluxes(g, [record(g, "B", 1, 2, 5)], base_revision=r)
            p = s.compile_window(g, r2, 0, 3)
            self.assertEqual(rows(p), [("A", 0, 1, 0, 3, 2), ("B", 1, 2, 1, 2, 5),
                                       ("A", 2, 3, 0, 3, 2)])
            rid = s.audit(p)
            report = s.read_result(rid)
            self.assertEqual((report["cells"][0]["outflow"], report["cells"][0]["residual"]), (9, 3))
            evidence = [e for e in report["sources"] if e["kind"] == "flux"
                        and e["record"]["side"] == "east"]
            self.assertEqual([e["clipped"] for e in evidence], [[0, 1], [1, 2], [2, 3]])
            self.assertEqual([e["integral"] for e in evidence], [2, 5, 2])
            self.assertEqual([e["duration"] for e in evidence], [1, 1, 1])
            r3 = s.put_observations(g, fluxes=[record(g, "C", 0, 3, 4)], base_revision=r2)
            p3 = s.compile_window(g, r3, 0, 3)
            self.assertEqual(rows(p3), [("C", 0, 1, 0, 3, 4), ("B", 1, 2, 1, 2, 5),
                                        ("C", 2, 3, 0, 3, 4)])
            self.assertEqual(s.read_result(s.audit(p3))["cells"][0]["outflow"], 13)
            self.assertEqual(exported(s, old_id), old_text)
            self.assertEqual(load_source_record(s.connection, "A"), a)
            decoded = decode_value(json.loads(exported(s, rid)))
            self.assertEqual(decoded["cells"][0]["outflow"], 9)
            self.assertCountEqual(decoded["sources"], report["sources"])

    def test_fractional_multiple_sources_gaps_and_touching(self):
        with LedgerService() as s:
            g, r = seed(s)
            r = s.correct_fluxes(g, [record(g, "B", F(1, 2), F(5, 2), 5)], base_revision=r)
            r = s.correct_fluxes(g, [record(g, "C", 1, 2, -1)], base_revision=r)
            p = s.compile_window(g, r, 0, 3)
            self.assertEqual(rows(p), [
                ("A", 0, F(1, 2), 0, 3, 2), ("B", F(1, 2), 1, F(1, 2), F(5, 2), 5),
                ("C", 1, 2, 1, 2, -1), ("B", 2, F(5, 2), F(1, 2), F(5, 2), 5),
                ("A", F(5, 2), 3, 0, 3, 2)])
            self.assertEqual(sum(c.integral for c in p.face_contributions((0, 0), "east")), 6)
        for old, patch, expected in (
            ([(0, 1, 2, "A"), (1, 3, 4, "D")], [("B", F(1, 2), 2, 5)], F(25, 2)),
            ([(0, 1, 2, "A"), (2, 3, 4, "D")], [("B", 1, 2, 5)], 11),
            (None, [("B", 0, 1, 5), ("C", 1, 2, 7)], 14),
        ):
            with self.subTest(old=old), LedgerService() as s:
                g, r = seed(s, east=old)
                if old is not None and old[1][0] == 2:
                    with self.assertRaises(ValueError):
                        s.compile_window(g, r, 0, 3)
                left = s.correct_fluxes(g, [record(g, *x) for x in patch], base_revision=r)
                right = s.correct_fluxes(g, [record(g, *x) for x in reversed(patch)], base_revision=r)
                lp, rp = s.compile_window(g, left, 0, 3), s.compile_window(g, right, 0, 3)
                self.assertEqual(rows(lp), rows(rp))
                self.assertEqual(s.read_result(s.audit(lp))["cells"][0]["outflow"], expected)

    def test_empty_reuse_and_fully_hidden_key(self):
        with LedgerService() as s:
            g, r = seed(s)
            r2 = s.correct_fluxes(g, [record(g, "B", 1, 2, 5)], base_revision=r)
            empty = s.correct_fluxes(g, [], base_revision=r2)
            self.assertNotEqual(empty, r2)
            self.assertEqual(rows(s.compile_window(g, empty, 0, 3)),
                             rows(s.compile_window(g, r2, 0, 3)))
            restored = s.correct_fluxes(g, [record(g, "A", 0, 3, 2)], base_revision=r2)
            self.assertEqual(rows(s.compile_window(g, restored, 0, 3)), [("A", 0, 3, 0, 3, 2)])
            full = s.correct_fluxes(g, [record(g, "F", -1, 4, 8)], base_revision=r2)
            self.assertEqual(rows(s.compile_window(g, full, 0, 3)), [("F", 0, 3, -1, 4, 8)])
            # A's key is now absent from effective membership; ordinary import adds a new key.
            ordinary = s.put_observations(g, fluxes=[record(g, "C", 0, 3, 4)], base_revision=full)
            with self.assertRaises(ValueError):
                s.compile_window(g, ordinary, 0, 3)

    def test_new_key_does_not_cover_and_outside_overlap_survives(self):
        with LedgerService() as s:
            g, r = seed(s)
            ordinary = s.put_observations(g, fluxes=[record(g, "D", 1, 2, 5)], base_revision=r)
            with self.assertRaises(ValueError):
                s.compile_window(g, ordinary, 0, 3)
            r2 = s.correct_fluxes(g, [record(g, "B", 2, 3, 7)], base_revision=ordinary)
            with self.assertRaises(ValueError):
                s.compile_window(g, r2, 0, 3)

    def test_internal_segmentwise_accounting(self):
        for bad in (False, True):
            with self.subTest(bad=bad), LedgerService() as s:
                g, r = seed(s, shape=(2, 1))
                right = ([record(g, "bad-right", 0, 1, -5, (1, 0), "west")] if bad else [
                    record(g, "right-a", 1, F(3, 2), -5, (1, 0), "west"),
                    record(g, "right-b", F(3, 2), 2, -5, (1, 0), "west")])
                r2 = s.correct_fluxes(g, [record(g, "B", 1, 2, 5)] + right, base_revision=r)
                p = s.compile_window(g, r2, 0, 3)
                self.assertEqual([sum(c.integral for c in p.face_contributions(cell, side))
                                  for cell, side in (((0, 0), "east"), ((1, 0), "west"))], [9, -9])
                if bad:
                    before = counts(s)
                    with self.assertRaises(ValueError):
                        s.audit(p)
                    self.assertEqual(counts(s), before)
                else:
                    report = s.read_result(s.audit(p))
                    self.assertEqual([c["residual"] for c in report["cells"]], [3, -3])
                    self.assertEqual(report["boundary"]["total_residual"], 0)

    def test_failures_are_atomic(self):
        with LedgerService() as s:
            g, r = seed(s)
            other = s.put_grid("other", (1, 1))
            cases = [
                ([record(g, "B", 1, 2, 5), record(g, "C", F(3, 2), 3, 7)], r, ValueError),
                ([record(g, "A", 0, 3, 9)], r, ValueError),
                ([record(g, "B", 0, 1, 2, side="up")], r, KeyError),
                ([record(other, "B", 0, 1, 2)], r, KeyError),
                ([replace(record(g, "B", 0, 1, 2), unit="mass")], r, ValueError),
                ([record(g, "B", 1, 1, 2)], r, ValueError),
                ([object()], r, ValueError), ([], None, ValueError), ([], True, ValueError),
                ([], 99999, KeyError),
            ]
            for patches, base, error in cases:
                before = counts(s)
                with self.subTest(base=base, error=error), self.assertRaises(error):
                    s.correct_fluxes(g, patches, base_revision=base)
                self.assertEqual(counts(s), before)
            with self.assertRaises(ValueError):
                s.correct_fluxes(other, [], base_revision=r)
            before = counts(s)
            s.connection.execute("CREATE TRIGGER reject_correction BEFORE INSERT ON sources "
                                 "WHEN NEW.source_id='reject' BEGIN SELECT RAISE(ABORT,'correction-write'); END")
            try:
                with self.assertRaises(sqlite3.IntegrityError):
                    s.correct_fluxes(g, [record(g, "accepted-first", 0, 1, 3),
                                         record(g, "reject", 1, 2, 5)], base_revision=r)
            finally:
                s.connection.execute("DROP TRIGGER reject_correction")
            self.assertEqual(counts(s), before)
            self.assertFalse(s.connection.in_transaction)
            # A failed correction must not change which input the ordinary default inherits.
            inherited = s.put_observations(g)
            self.assertEqual(rows(s.compile_window(g, inherited, 0, 3)), [("A", 0, 3, 0, 3, 2)])

    def test_branch_reopen_and_detached_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            with LedgerService(path) as s:
                g, r = seed(s)
                old_id = s.audit(s.compile_window(g, r, 0, 3))
                r2 = s.correct_fluxes(g, [record(g, "B", 1, 2, 5)], base_revision=r)
                p2 = s.compile_window(g, r2, 0, 3)
                new_id = s.audit(p2)
                branch = s.correct_fluxes(g, [record(g, "D", 0, 1, 7)], base_revision=r)
                branch_id = s.audit(s.compile_window(g, branch, 0, 3))
                ids = [old_id, new_id, branch_id]
                texts = [exported(s, rid) for rid in ids]
                self.assertEqual([s.read_result(rid)["cells"][0]["outflow"] for rid in ids], [6, 9, 11])
                altered = s.read_result(new_id)
                altered["sources"].clear()
                altered["cells"][0]["outflow"] = 999
                self.assertEqual([exported(s, rid) for rid in ids], texts)
            with LedgerService(path) as s:
                self.assertEqual([exported(s, rid) for rid in ids], texts)
                self.assertEqual(exported(s, s.audit(p2.id)), texts[1])
                child = s.put_observations(g, fluxes=[record(g, "C", 0, 3, 4)], base_revision=r2)
                self.assertEqual(s.read_result(s.audit(s.compile_window(g, child, 0, 3)))["cells"][0]["outflow"], 13)
                self.assertEqual([exported(s, rid) for rid in ids], texts)


def baseline():
    with LedgerService() as s:
        g, r = seed(s)
        plan = s.compile_window(g, r, 0, 3)
        rid = s.audit(plan)
        report = s.read_result(rid)
        if (report["cells"][0]["outflow"], report["cells"][0]["residual"]) != (6, 0):
            raise AssertionError(report)
        # This is the unchanged V1 behavior, not a defect reproduction.
        added = s.put_observations(g, fluxes=[record(g, "B", 1, 2, 5)], base_revision=r)
        try:
            s.compile_window(g, added, 0, 3)
        except ValueError:
            pass
        else:
            raise AssertionError("ordinary import must not silently cover")
        print("V1_FIXTURE " + canonical_json({"outflow": F(6), "residual": F(0),
                                             "ordinary_overlap": "rejected"}))


def demo():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "ledger.sqlite"
        with LedgerService(path) as s:
            g, r = seed(s)
            old_id = s.audit(s.compile_window(g, r, 0, 3))
            corrected = s.correct_fluxes(g, [record(g, "B", 1, 2, 5)], base_revision=r)
            rid = s.audit(s.compile_window(g, corrected, 0, 3))
            replaced = s.put_observations(g, fluxes=[record(g, "C", 0, 3, 4)], base_revision=corrected)
            replaced_id = s.audit(s.compile_window(g, replaced, 0, 3))
            ids = [old_id, rid, replaced_id]
            texts = [exported(s, n) for n in ids]
        with LedgerService(path) as s:
            actual = [s.read_result(n)["cells"][0]["outflow"] for n in ids]
            if actual != [6, 9, 13] or [exported(s, n) for n in ids] != texts:
                raise AssertionError(actual)
            print("CORRECTION_SCENARIO " + canonical_json({"expected": [6, 9, 13], "actual": actual,
                                                         "reopened": True}))
            for text in texts:
                print(text, end="")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--baseline", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.baseline:
        baseline()
    elif args.demo:
        demo()
    else:
        suite = unittest.TestSuite((unittest.defaultTestLoader.discover("tests"),
                                   unittest.defaultTestLoader.loadTestsFromTestCase(CorrectionCases)))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        raise SystemExit(not result.wasSuccessful())


if __name__ == "__main__":
    main()
