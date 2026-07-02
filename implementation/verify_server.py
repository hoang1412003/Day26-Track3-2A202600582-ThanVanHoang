from __future__ import annotations

import json

from db import SQLiteAdapter, ValidationError
from init_db import DB_PATH, create_database


def show(title: str, payload: object) -> None:
    print(f"\n## {title}")
    print(json.dumps(payload, indent=2))


def main() -> None:
    create_database(DB_PATH)
    adapter = SQLiteAdapter(DB_PATH)

    show("schema resource payload", adapter.database_schema())
    show(
        "search students in cohort A1",
        adapter.search(
            "students",
            filters={"cohort": "A1"},
            columns=["id", "name", "cohort", "score"],
            order_by="score",
            descending=True,
        ),
    )
    show(
        "insert a new student",
        adapter.insert(
            "students",
            {"name": "Than Van Hoang", "cohort": "A1", "email": "van.hoang@example.edu", "score": 93.5},
        ),
    )
    show("count students", adapter.aggregate("students", "count"))
    show("average score by cohort", adapter.aggregate("students", "avg", "score", group_by="cohort"))

    try:
        adapter.search("missing_table")
    except ValidationError as exc:
        show("expected invalid request error", {"error": str(exc)})


if __name__ == "__main__":
    main()
