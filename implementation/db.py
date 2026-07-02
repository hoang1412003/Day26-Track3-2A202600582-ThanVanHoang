from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when a database request cannot be safely executed."""


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SUPPORTED_OPERATORS = {
    "eq": "=",
    "=": "=",
    "ne": "!=",
    "!=": "!=",
    "gt": ">",
    ">": ">",
    "gte": ">=",
    ">=": ">=",
    "lt": "<",
    "<": "<",
    "lte": "<=",
    "<=": "<=",
    "like": "LIKE",
    "in": "IN",
}
AGGREGATES = {"count", "avg", "sum", "min", "max"}


class SQLiteAdapter:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        self._validate_table(table)
        quoted_table = self._quote_identifier(table)
        with closing(self.connect()) as conn:
            rows = conn.execute(f"PRAGMA table_info({quoted_table})").fetchall()
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list({quoted_table})").fetchall()
        return {
            "table": table,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "nullable": not bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ],
            "foreign_keys": [
                {
                    "column": row["from"],
                    "references_table": row["table"],
                    "references_column": row["to"],
                }
                for row in foreign_keys
            ],
        }

    def database_schema(self) -> dict[str, Any]:
        return {"tables": [self.get_table_schema(table) for table in self.list_tables()]}

    def search(
        self,
        table: str,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._validate_table(table)
        selected = columns or self._column_names(table)
        self._validate_columns(table, selected)
        limit = self._validate_non_negative_int(limit, "limit", maximum=100)
        offset = self._validate_non_negative_int(offset, "offset")

        where_sql, params = self._build_where(table, filters)
        order_sql = ""
        if order_by:
            self._validate_column(table, order_by)
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {self._quote_identifier(order_by)} {direction}"

        quoted_table = self._quote_identifier(table)
        selected_sql = ", ".join(self._quote_identifier(column) for column in selected)
        sql = f"SELECT {selected_sql} FROM {quoted_table}{where_sql}{order_sql} LIMIT ? OFFSET ?"
        with closing(self.connect()) as conn:
            rows = conn.execute(sql, [*params, limit, offset]).fetchall()
            total = conn.execute(f"SELECT COUNT(*) AS count FROM {quoted_table}{where_sql}", params).fetchone()[
                "count"
            ]
        return {
            "table": table,
            "columns": selected,
            "rows": [dict(row) for row in rows],
            "limit": limit,
            "offset": offset,
            "total_matching_rows": total,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._validate_table(table)
        if not values:
            raise ValidationError("insert values must not be empty")
        self._validate_columns(table, values.keys())

        columns = list(values.keys())
        quoted_columns = ", ".join(self._quote_identifier(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {self._quote_identifier(table)} ({quoted_columns}) VALUES ({placeholders})"
        with closing(self.connect()) as conn:
            cursor = conn.execute(sql, [values[column] for column in columns])
            conn.commit()
            row = conn.execute(
                f"SELECT * FROM {self._quote_identifier(table)} WHERE rowid = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return {"table": table, "inserted": dict(row) if row else dict(values)}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        self._validate_table(table)
        metric = metric.lower()
        if metric not in AGGREGATES:
            raise ValidationError(f"unsupported aggregate metric '{metric}'")
        if metric == "count" and column is None:
            aggregate_expr = "COUNT(*)"
        else:
            if column is None:
                raise ValidationError(f"aggregate metric '{metric}' requires a column")
            self._validate_column(table, column)
            aggregate_expr = f"{metric.upper()}({self._quote_identifier(column)})"

        groups = self._normalize_group_by(group_by)
        self._validate_columns(table, groups)
        select_parts = [self._quote_identifier(column_name) for column_name in groups]
        select_parts.append(f"{aggregate_expr} AS value")
        where_sql, params = self._build_where(table, filters)
        group_sql = ""
        if groups:
            group_sql = " GROUP BY " + ", ".join(self._quote_identifier(column_name) for column_name in groups)

        sql = f"SELECT {', '.join(select_parts)} FROM {self._quote_identifier(table)}{where_sql}{group_sql}"
        with closing(self.connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": groups,
            "rows": [dict(row) for row in rows],
        }

    def schema_as_json(self, table: str | None = None) -> str:
        payload = self.get_table_schema(table) if table else self.database_schema()
        return json.dumps(payload, indent=2)

    def _build_where(
        self, table: str, filters: dict[str, Any] | list[dict[str, Any]] | None
    ) -> tuple[str, list[Any]]:
        if not filters:
            return "", []

        if isinstance(filters, dict):
            normalized = [{"column": key, "op": "eq", "value": value} for key, value in filters.items()]
        elif isinstance(filters, list):
            normalized = filters
        else:
            raise ValidationError("filters must be a dictionary or a list of filter objects")

        clauses: list[str] = []
        params: list[Any] = []
        for item in normalized:
            if not isinstance(item, dict):
                raise ValidationError("each filter must be an object")
            column = item.get("column")
            operator = str(item.get("op", "eq")).lower()
            value = item.get("value")
            if not column:
                raise ValidationError("each filter requires a column")
            self._validate_column(table, str(column))
            if operator not in SUPPORTED_OPERATORS:
                raise ValidationError(f"unsupported filter operator '{operator}'")

            sql_operator = SUPPORTED_OPERATORS[operator]
            if operator == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("IN filters require a non-empty list value")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{self._quote_identifier(str(column))} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{self._quote_identifier(str(column))} {sql_operator} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    def _normalize_group_by(self, group_by: str | list[str] | None) -> list[str]:
        if group_by is None:
            return []
        if isinstance(group_by, str):
            return [group_by]
        if isinstance(group_by, list) and all(isinstance(column, str) for column in group_by):
            return group_by
        raise ValidationError("group_by must be a column name or a list of column names")

    def _validate_table(self, table: str) -> None:
        if not table or not IDENTIFIER_RE.match(table):
            raise ValidationError(f"invalid table name '{table}'")
        if table not in self.list_tables():
            raise ValidationError(f"unknown table '{table}'")

    def _validate_columns(self, table: str, columns: Any) -> None:
        for column in columns:
            self._validate_column(table, column)

    def _validate_column(self, table: str, column: str) -> None:
        if not column or not IDENTIFIER_RE.match(column):
            raise ValidationError(f"invalid column name '{column}'")
        if column not in self._column_names(table):
            raise ValidationError(f"unknown column '{column}' for table '{table}'")

    def _column_names(self, table: str) -> list[str]:
        with closing(self.connect()) as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return [row["name"] for row in rows]

    def _validate_non_negative_int(self, value: int, name: str, maximum: int | None = None) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{name} must be an integer") from exc
        if parsed < 0:
            raise ValidationError(f"{name} must be non-negative")
        if maximum is not None and parsed > maximum:
            raise ValidationError(f"{name} must be at most {maximum}")
        return parsed

    def _quote_identifier(self, identifier: str) -> str:
        if not IDENTIFIER_RE.match(identifier):
            raise ValidationError(f"invalid SQL identifier '{identifier}'")
        return f'"{identifier}"'
