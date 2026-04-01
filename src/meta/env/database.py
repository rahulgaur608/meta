"""
Database engine simulation using SQLite in-memory.
Provides realistic SQL execution with execution plan analysis.
"""
from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.env.models import ColumnDef, ExecutionPlan, QueryResult, TableSchema


def _sqlite_type(col_type: str) -> str:
    mapping = {
        "integer": "INTEGER",
        "text": "TEXT",
        "float": "REAL",
        "boolean": "INTEGER",
        "timestamp": "TEXT",
    }
    return mapping.get(col_type.lower(), "TEXT")


class DatabaseEngine:
    """
    In-memory SQLite engine that simulates a real OLAP/OLTP database.
    Tracks query costs, index usage, and execution metrics.
    """

    def __init__(self) -> None:
        self.conn: Optional[sqlite3.Connection] = None
        self.schema: List[TableSchema] = []
        self._query_log: List[Dict[str, Any]] = []

    def setup(self, schema: List[TableSchema], seed_data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Initialize the database with schema and data."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.schema = schema
        self._query_log = []

        for table in schema:
            self._create_table(table)
            if table.name in seed_data:
                self._insert_rows(table, seed_data[table.name])
            # Create declared indexes
            for col in table.columns:
                if col.index and not col.primary_key:
                    idx_name = f"idx_{table.name}_{col.name}"
                    self.conn.execute(
                        f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table.name}({col.name})"
                    )

        self.conn.commit()

    def _create_table(self, table: TableSchema) -> None:
        col_defs = []
        for col in table.columns:
            sql_type = _sqlite_type(col.type)
            parts = [f'"{col.name}" {sql_type}']
            if col.primary_key:
                parts.append("PRIMARY KEY")
            if not col.nullable and not col.primary_key:
                parts.append("NOT NULL")
            col_defs.append(" ".join(parts))

        # Add FK constraints after all columns
        fk_constraints = []
        for col in table.columns:
            if col.foreign_key:
                ref_table, ref_col = col.foreign_key.split(".")
                fk_constraints.append(
                    f'FOREIGN KEY ("{col.name}") REFERENCES "{ref_table}"("{ref_col}")'
                )

        all_defs = col_defs + fk_constraints
        ddl = f'CREATE TABLE IF NOT EXISTS "{table.name}" ({", ".join(all_defs)})'
        self.conn.execute(ddl)

    def _insert_rows(self, table: TableSchema, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        col_names = [col.name for col in table.columns]
        placeholders = ", ".join(["?"] * len(col_names))
        col_list = ", ".join([f'"{c}"' for c in col_names])
        sql = f'INSERT OR IGNORE INTO "{table.name}" ({col_list}) VALUES ({placeholders})'
        for row in rows:
            values = [row.get(c) for c in col_names]
            try:
                self.conn.execute(sql, values)
            except sqlite3.Error:
                pass
        self.conn.commit()

    def execute_query(self, sql: str) -> Tuple[QueryResult, float]:
        """Execute SQL and return (result, elapsed_ms)."""
        if self.conn is None:
            return QueryResult(columns=[], rows=[], row_count=0, error="Database not initialized"), 0.0

        start = time.perf_counter()
        try:
            # Restrict to SELECT only for safety
            normalized = sql.strip().upper()
            if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
                return (
                    QueryResult(
                        columns=[], rows=[], row_count=0,
                        error="Only SELECT/WITH queries are allowed."
                    ),
                    0.0,
                )

            cursor = self.conn.execute(sql)
            col_names = [d[0] for d in cursor.description] if cursor.description else []
            rows = [list(r) for r in cursor.fetchall()]
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            result = QueryResult(columns=col_names, rows=rows, row_count=len(rows))
        except sqlite3.Error as e:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            result = QueryResult(columns=[], rows=[], row_count=0, error=str(e))

        self._query_log.append({"sql": sql, "elapsed_ms": elapsed_ms, "error": result.error})
        return result, elapsed_ms

    def get_execution_plan(self, sql: str) -> ExecutionPlan:
        """
        Analyze query via EXPLAIN QUERY PLAN and return a cost model.
        SQLite's output is parsed to produce a richer cost estimate.
        """
        if self.conn is None:
            return ExecutionPlan(
                estimated_cost=999.0, seq_scans=0, index_scans=0,
                joins=0, sort_operations=0, estimated_rows=0,
            )

        try:
            plan_rows = self.conn.execute(f"EXPLAIN QUERY PLAN {sql}").fetchall()
        except sqlite3.Error:
            return ExecutionPlan(
                estimated_cost=999.0, seq_scans=0, index_scans=0,
                joins=0, sort_operations=0, estimated_rows=0,
            )

        seq_scans = 0
        index_scans = 0
        joins = 0
        sort_ops = 0
        total_tables = 0

        for row in plan_rows:
            detail = str(row[3]).upper() if len(row) > 3 else ""
            if "SCAN" in detail and "INDEX" not in detail:
                seq_scans += 1
                total_tables += 1
            elif "SEARCH" in detail or "INDEX" in detail:
                index_scans += 1
                total_tables += 1
            if "USING TEMP B-TREE" in detail or "ORDER BY" in detail:
                sort_ops += 1
            if "NESTED LOOP" in detail or "HASH JOIN" in detail or total_tables > 1:
                pass  # counted per table

        # Joins = tables - 1 if more than one table accessed
        joins = max(0, total_tables - 1)

        # Rough cost model: seq scan on large table is expensive
        table_sizes = {t.name: t.row_count for t in self.schema}
        avg_rows = sum(table_sizes.values()) / max(1, len(table_sizes))
        cost = (seq_scans * avg_rows * 0.01) + (index_scans * avg_rows * 0.001) + (sort_ops * 2.0)

        return ExecutionPlan(
            estimated_cost=round(cost, 2),
            seq_scans=seq_scans,
            index_scans=index_scans,
            joins=joins,
            sort_operations=sort_ops,
            estimated_rows=int(avg_rows),
        )

    def add_index(self, table: str, column: str) -> Optional[str]:
        """Dynamically add an index. Returns error string or None."""
        if self.conn is None:
            return "Database not initialized"
        idx_name = f"idx_{table}_{column}_agent"
        try:
            self.conn.execute(f'CREATE INDEX IF NOT EXISTS {idx_name} ON "{table}"("{column}")')
            self.conn.commit()
            return None
        except sqlite3.Error as e:
            return str(e)

    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Return row count and column cardinality estimates."""
        if self.conn is None:
            return {}
        try:
            count = self.conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            return {"row_count": count}
        except sqlite3.Error:
            return {}

    def teardown(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
