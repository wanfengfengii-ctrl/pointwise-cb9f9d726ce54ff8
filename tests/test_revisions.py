from dataclasses import replace
from fractions import Fraction as F
import tempfile
from pathlib import Path
import unittest
from gridledger.delivery.service import LedgerService
from gridledger.archive.grid_store import load_grid_revision
from gridledger.archive.observation_store import load_observation_revision
from gridledger.archive.plan_store import load_plan
from gridledger.observations.model import MassRecord, FluxRecord
from tests.test_balance import seed_two, counts

class TestRevisionBinding(unittest.TestCase):
    def test_correction_keeps_old_plan(self):
        with LedgerService() as service:
            g, r = seed_two(service)
            old_plan = service.compile_window(g, r, 0, 1)
            correction = FluxRecord(g, (0, 0), "west", 0, 1, -2, "corrected-west")
            r2 = service.put_observations(g, fluxes=[correction])
            new_plan = service.compile_window(g, r2, 0, 1)
            old = service.read_result(service.audit(old_plan))
            new = service.read_result(service.audit(new_plan))
            self.assertEqual([c["residual"] for c in old["cells"]], [F(0), F(0)])
            self.assertEqual([c["residual"] for c in new["cells"]], [F(-1), F(0)])
            old_ids = [s["record"]["source_id"] for s in old["sources"]]
            new_ids = [s["record"]["source_id"] for s in new["sources"]]
            self.assertIn("(0, 0)-west-0", old_ids)
            self.assertNotIn("corrected-west", old_ids)
            self.assertIn("corrected-west", new_ids)
            self.assertNotIn("(0, 0)-west-0", new_ids)
            self.assertEqual(load_plan(service.connection, old_plan.id), old_plan)
            self.assertEqual(len(load_observation_revision(service.connection, r).fluxes), 8)
            self.assertEqual(len(load_observation_revision(service.connection, r2).fluxes), 8)

    def test_mass_correction_and_source_identity(self):
        with LedgerService() as service:
            g, r = seed_two(service)
            old_plan = service.compile_window(g, r, 0, 1)
            correction = MassRecord(g, (0, 0), 0, 9, "corrected-mass")
            r2 = service.put_observations(g, masses=[correction])
            new = service.read_result(service.audit(service.compile_window(g, r2, 0, 1)))
            old = service.read_result(service.audit(old_plan))
            self.assertEqual(new["cells"][0]["change"], F(-1))
            self.assertEqual(new["cells"][0]["residual"], F(1))
            self.assertEqual(old["cells"][0]["mass_start"], F(10))
            before = counts(service)
            with self.assertRaises(ValueError):
                service.put_observations(g, masses=[replace(correction, value=8)])
            self.assertEqual(counts(service), before)
            repeated = service.put_observations(g, masses=[correction])
            self.assertNotEqual(repeated, r2)
            self.assertEqual(counts(service)["sources"], before["sources"])
            branch = service.put_observations(g, base_revision=r)
            self.assertEqual(load_observation_revision(service.connection, branch).masses,
                             load_observation_revision(service.connection, r).masses)

    def test_old_plan_after_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite"
            with LedgerService(path) as service:
                g, r = seed_two(service)
                p = service.compile_window(g, r, 0, 1)
                old_id = service.audit(p)
                baseline = service.read_result(old_id)
                r2 = service.put_observations(g, fluxes=[
                    FluxRecord(g, (0, 0), "west", 0, 1, -2, "revised")])
                p2 = service.compile_window(g, r2, 0, 1)
            with LedgerService(path) as service:
                self.assertEqual(service.read_result(old_id), baseline)
                old_again = service.read_result(service.audit(p.id))
                self.assertEqual(old_again, baseline)
                new = service.read_result(service.audit(p2.id))
                self.assertEqual(new["cells"][0]["residual"], F(-1))
                self.assertEqual(load_grid_revision(service.connection, g).id, g)
