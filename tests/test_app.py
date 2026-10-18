import os
import tempfile
import unittest
from pathlib import Path

# Set a temporary database before importing the app module.
_TEMP_DIR = tempfile.TemporaryDirectory()
os.environ["FINSIGHT_DATABASE"] = str(Path(_TEMP_DIR.name) / "test.db")

import app as finsight_app


class FinSightTests(unittest.TestCase):
    def setUp(self):
        finsight_app.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key",
        )
        self.client = finsight_app.app.test_client()

        # Reset the database tables for each test.
        with finsight_app.app.app_context():
            db = finsight_app.get_db()
            db.execute("DELETE FROM transactions")
            db.execute("DELETE FROM budgets")
            db.commit()

    def post_with_csrf(self, url, data):
        with self.client.session_transaction() as session:
            token = session.get("_csrf_token")
        if not token:
            self.client.get("/transactions/add")
            with self.client.session_transaction() as session:
                token = session.get("_csrf_token")
        data["_csrf_token"] = token
        return self.client.post(url, data=data, follow_redirects=True)

    def test_dashboard_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Financial overview", response.data)

    def test_add_transaction_and_persist(self):
        response = self.post_with_csrf("/transactions/add", {
            "transaction_type": "income",
            "category": "Salary",
            "amount": "10000.00",
            "transaction_date": "2026-10-18",
            "description": "Test salary",
        })
        self.assertEqual(response.status_code, 200)
        with finsight_app.app.app_context():
            rows = finsight_app.fetch_transactions(month="2026-10")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["amount_cents"], 1000000)

    def test_invalid_amount_is_rejected(self):
        response = self.post_with_csrf("/transactions/add", {
            "transaction_type": "expense",
            "category": "Food",
            "amount": "-10",
            "transaction_date": "2026-10-18",
            "description": "Invalid",
        })
        self.assertEqual(response.status_code, 400)

    def test_csv_export(self):
        response = self.client.get("/export.csv?month=2026-10")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Date,Type,Category,Amount INR,Description", response.data)


if __name__ == "__main__":
    unittest.main()
