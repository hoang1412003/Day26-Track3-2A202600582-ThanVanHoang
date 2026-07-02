import tempfile
import unittest
from pathlib import Path

from db import SQLiteAdapter, ValidationError
from init_db import create_database


class SQLiteAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "school.db"
        create_database(self.db_path)
        self.adapter = SQLiteAdapter(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_search_filters_ordering_and_pagination(self):
        result = self.adapter.search(
            "students",
            filters={"cohort": "A1"},
            columns=["name", "score"],
            order_by="score",
            descending=True,
            limit=1,
        )

        self.assertEqual(result["total_matching_rows"], 2)
        self.assertEqual(result["rows"], [{"name": "Binh Tran", "score": 91.0}])

    def test_insert_returns_inserted_payload(self):
        result = self.adapter.insert(
            "students",
            {"name": "Lan Do", "cohort": "C3", "email": "lan.do@example.edu", "score": 81.5},
        )

        self.assertEqual(result["inserted"]["name"], "Lan Do")
        self.assertIsInstance(result["inserted"]["id"], int)

    def test_aggregate_average_by_cohort(self):
        result = self.adapter.aggregate("students", "avg", "score", group_by="cohort")

        rows = {row["cohort"]: row["value"] for row in result["rows"]}
        self.assertAlmostEqual(rows["A1"], 89.75)
        self.assertAlmostEqual(rows["B2"], 80.25)

    def test_schema_contains_students_table(self):
        schema = self.adapter.database_schema()

        self.assertIn("students", [table["table"] for table in schema["tables"]])

    def test_invalid_table_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unknown table"):
            self.adapter.search("not_a_table")

    def test_invalid_column_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unknown column"):
            self.adapter.search("students", columns=["password"])

    def test_invalid_operator_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unsupported filter operator"):
            self.adapter.search("students", filters=[{"column": "score", "op": "contains", "value": 90}])

    def test_empty_insert_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "must not be empty"):
            self.adapter.insert("students", {})

    def test_invalid_aggregate_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "unsupported aggregate"):
            self.adapter.aggregate("students", "median", "score")


if __name__ == "__main__":
    unittest.main()
