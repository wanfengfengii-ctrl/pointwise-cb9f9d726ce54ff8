import sqlite3
import unittest
from gridledger.delivery.service import LedgerService
from tests.test_balance import seed_two, counts

class TestPublication(unittest.TestCase):
    def test_transaction_failure(self):
        with LedgerService() as service:
            g, r = seed_two(service)
            p = service.compile_window(g, r, 0, 1)
            old_id = service.audit(p)
            old = service.read_result(old_id)
            before = counts(service)
            for table in ("result_cells", "result_faces", "result_sources"):
                with self.subTest(table=table):
                    service.connection.execute("CREATE TRIGGER reject_publication BEFORE INSERT ON " + table +
                                               " BEGIN SELECT RAISE(ABORT,'blocked publication'); END")
                    try:
                        with self.assertRaises(sqlite3.IntegrityError) as caught:
                            service.audit(p)
                        self.assertEqual(str(caught.exception), "blocked publication")
                        self.assertEqual(counts(service), before)
                        self.assertEqual(service.read_result(old_id), old)
                        self.assertFalse(service.connection.in_transaction)
                    finally:
                        service.connection.execute("DROP TRIGGER reject_publication")
            new_id = service.audit(p)
            self.assertNotEqual(new_id, old_id)
            self.assertEqual(service.read_result(new_id), old)
            self.assertEqual(counts(service)["results"], before["results"] + 1)
            for table in ("result_cells", "result_faces", "result_sources"):
                self.assertEqual(counts(service)[table], 2 * before[table])
