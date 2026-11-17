from fractions import Fraction as F
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from gridledger.delivery.service import LedgerService
from gridledger.delivery.codec import decode_value
from gridledger.archive.schema import ensure_schema
from gridledger.archive.grid_store import load_grid_revision
from tests.test_balance import uniform_records, seed_two, counts

def exact_report(service):
    g = service.put_grid("exact", (1, 1))
    grid = load_grid_revision(service.connection, g)
    m, f = uniform_records(grid, rates={((0, 0), "east"): F(1, 3),
                                      ((0, 0), "west"): F(-2, 7)})
    r = service.put_observations(g, m, f)
    return service.audit(service.compile_window(g, r, 0, 1))

class TestResultDelivery(unittest.TestCase):
    def test_reopen_and_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            with LedgerService(path) as service:
                rid = exact_report(service)
                baseline = service.read_result(rid)
                self.assertEqual(baseline["cells"][0]["outflow"], F(1, 21))
                self.assertEqual(baseline["anomalous_cells"], [[0, 0]])
                altered = service.read_result(rid)
                altered["cells"][0]["residual"] = F(99)
                altered["cells"][0]["faces"][0]["integral"] = F(77)
                altered["sources"][0]["record"]["value"] = F(101)
                altered["sources"].clear()
                altered["anomalous_cells"].clear()
                self.assertEqual(service.read_result(rid), baseline)
                topology = load_grid_revision(service.connection, baseline["grid_id"])
                a, b = io.StringIO(), io.StringIO()
                service.export_result(rid, a)
                service.export_result(rid, b)
                self.assertEqual(a.getvalue(), b.getvalue())
                serialized = a.getvalue()
            with LedgerService(path) as service:
                self.assertEqual(service.read_result(rid), baseline)
                self.assertEqual(load_grid_revision(service.connection, baseline["grid_id"]), topology)
                target = io.StringIO()
                service.export_result(rid, target)
                self.assertEqual(target.getvalue(), serialized)
                decoded = decode_value(json.loads(serialized))
                self.assertEqual(decoded["cells"][0]["outflow"], F(1, 21))
                self.assertEqual(decoded["cells"][0]["mass_start"], F(0))
                self.assertCountEqual(decoded["sources"], baseline["sources"])
                flows = {s["record"]["side"]: s["record"]["rate"]
                         for s in decoded["sources"] if s["kind"] == "flux"}
                self.assertEqual(flows, {"east": F(1, 3), "west": F(-2, 7), "north": F(0), "south": F(0)})
                raw = json.loads(serialized)
                self.assertEqual(raw["cells"][0]["outflow"], {"$fraction": [1, 21]})

    def test_reinitialize(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            with LedgerService(path) as service:
                g, r = seed_two(service)
                from gridledger.observations.model import MassRecord
                r2 = service.put_observations(g, masses=[MassRecord(g, (0, 0), 0, 9, "new-mass")])
                rid = service.audit(service.compile_window(g, r2, 0, 1))
                baseline, before = service.read_result(rid), counts(service)
                service.connection.execute("CREATE UNIQUE INDEX user_grid_name_id ON grid_revisions(name,id)")
                service.connection.execute("CREATE TABLE user_notes(note TEXT)")
                service.connection.execute("CREATE INDEX user_note_idx ON user_notes(note)")
                service.connection.execute("CREATE TRIGGER user_note_trigger AFTER INSERT ON user_notes BEGIN SELECT 1; END")
                service.connection.execute("INSERT INTO user_notes VALUES ('preserve')")
                ensure_schema(service.connection)
                ensure_schema(service.connection)
                self.assertEqual(counts(service), before)
            with LedgerService(path) as service:
                self.assertEqual(counts(service), before)
                self.assertEqual(service.read_result(rid), baseline)
                self.assertEqual(service.connection.execute("SELECT note FROM user_notes").fetchall(), [("preserve",)])
                self.assertIsNotNone(service.connection.execute(
                    "SELECT name FROM sqlite_master WHERE name='user_grid_name_id'").fetchone())
                names = {r[0] for r in service.connection.execute(
                    "SELECT name FROM sqlite_master WHERE name LIKE 'user_note%'")}
                self.assertEqual(names, {"user_notes", "user_note_idx", "user_note_trigger"})

    def test_incompatible_schema_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.sqlite"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE grid_revisions(id TEXT PRIMARY KEY,name TEXT NOT NULL,spec TEXT NOT NULL)")
            connection.execute("INSERT INTO grid_revisions VALUES ('keep','user','content')")
            connection.commit()
            connection.close()
            with self.assertRaises(ValueError):
                LedgerService(path)
            connection = sqlite3.connect(path)
            try:
                self.assertEqual(connection.execute("SELECT * FROM grid_revisions").fetchall(),
                                 [("keep", "user", "content")])
                self.assertEqual(connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),
                                 [("grid_revisions",)])
            finally:
                connection.close()

    def test_export_write_failure(self):
        class DestinationFailure(Exception):
            pass
        failure = DestinationFailure("disk destination unavailable")
        class BrokenTarget:
            def write(self, text):
                raise failure
        with LedgerService() as service:
            rid = exact_report(service)
            baseline, before = service.read_result(rid), counts(service)
            with self.assertRaises(DestinationFailure) as caught:
                service.export_result(rid, BrokenTarget())
            self.assertIs(caught.exception, failure)
            self.assertEqual(service.read_result(rid), baseline)
            self.assertEqual(counts(service), before)
            with self.assertRaises(KeyError):
                service.read_result(rid + 100)
            with self.assertRaises(KeyError):
                service.export_result(rid + 100, io.StringIO())
            output = io.StringIO()
            service.export_result(rid, output)
            self.assertTrue(output.getvalue().endswith("\n"))

    def test_reinitialize_memory(self):
        with LedgerService() as service:
            rid = exact_report(service)
            baseline, before = service.read_result(rid), counts(service)
            service.connection.execute("CREATE UNIQUE INDEX user_grid_name_id ON grid_revisions(name,id)")
            service.connection.execute("CREATE TABLE user_notes(note TEXT)")
            service.connection.execute("INSERT INTO user_notes VALUES ('keep')")
            ensure_schema(service.connection)
            ensure_schema(service.connection)
            self.assertEqual(counts(service), before)
            self.assertEqual(service.read_result(rid), baseline)
            self.assertEqual(service.connection.execute("SELECT note FROM user_notes").fetchall(), [("keep",)])
