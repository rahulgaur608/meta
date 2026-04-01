"""
Agent graders for each task.
Each grader returns a float in [0.0, 1.0] with partial credit.
Graders are deterministic: same SQL + same DB → same score.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.env.models import ExecutionPlan, QueryResult


def _col_match(result_cols: list, expected_cols: Set[str], threshold: float = 0.5) -> float:
    """Returns fraction of expected columns present (case-insensitive)."""
    result_lower = {c.lower() for c in result_cols}
    expected_lower = {c.lower() for c in expected_cols}
    if not expected_lower:
        return 1.0
    matched = len(result_lower & expected_lower)
    return matched / len(expected_lower)


def _has_rows(result: QueryResult) -> bool:
    return result.row_count > 0


def _is_ordered_desc(result: QueryResult, col_name: str) -> bool:
    """Check if the target column is in descending order."""
    cols_lower = [c.lower() for c in result.columns]
    if col_name.lower() not in cols_lower:
        return False
    idx = cols_lower.index(col_name.lower())
    vals = []
    for row in result.rows:
        try:
            vals.append(float(row[idx]))
        except (TypeError, ValueError, IndexError):
            return False
    return all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))


def _reward_plan(plan: ExecutionPlan, n_tables: int = 1) -> float:
    """
    Partial reward for query efficiency.
    Better plans (more index scans, fewer seq scans) score higher.
    Returns 0.0–0.25 bonus.
    """
    if plan.seq_scans == 0 and plan.index_scans > 0:
        return 0.25
    if plan.seq_scans <= n_tables:
        return 0.10
    return 0.0


def grade_easy(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
) -> Dict[str, Any]:
    """
    Task 1 grader: department salary aggregation.
    Scoring:
      - Correct columns present: 0.30
      - Has rows (non-empty result): 0.10
      - avg_salary column contains floats: 0.10
      - headcount column contains integers: 0.10
      - Ordered by avg_salary desc: 0.15
      - No syntax error: required
      - Efficiency bonus (index used): 0.25
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.30, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.10
        score += 0.10

    cols_lower = [c.lower() for c in result.columns]

    # avg_salary is float
    if "avg_salary" in cols_lower:
        idx = cols_lower.index("avg_salary")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            partial["avg_salary_numeric"] = 0.10
            score += 0.10

    # headcount is int-like
    if "headcount" in cols_lower:
        idx = cols_lower.index("headcount")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals):
            partial["headcount_integer"] = 0.10
            score += 0.10

    # Ordered descending by avg_salary
    if _is_ordered_desc(result, "avg_salary"):
        partial["ordered_desc"] = 0.15
        score += 0.15

    # Efficiency bonus
    eff = _reward_plan(plan, n_tables=1)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


def grade_medium(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
) -> Dict[str, Any]:
    """
    Task 2 grader: top-10 customers by revenue.
    Scoring:
      - Correct columns: 0.25
      - Exactly 10 rows: 0.15
      - total_revenue is float: 0.10
      - order_count is integer: 0.05
      - Ordered by total_revenue desc: 0.15
      - All rows have status=completed logic (proxy: revenue > 0): 0.05
      - Efficiency bonus: 0.25
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.25, 3)
    score += partial["columns"]

    # Exactly 10 rows
    if result.row_count == 10:
        partial["row_count_10"] = 0.15
        score += 0.15
    elif 8 <= result.row_count <= 12:
        partial["row_count_near"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    if "total_revenue" in cols_lower:
        idx = cols_lower.index("total_revenue")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) and v > 0 for v in vals):
            partial["revenue_positive"] = 0.10
            score += 0.10

    if "order_count" in cols_lower:
        idx = cols_lower.index("order_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals):
            partial["order_count_integer"] = 0.05
            score += 0.05

    if _is_ordered_desc(result, "total_revenue"):
        partial["ordered_desc"] = 0.15
        score += 0.15

    eff = _reward_plan(plan, n_tables=2)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


def grade_hard(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
) -> Dict[str, Any]:
    """
    Task 3 grader: high-value user retention report.
    Scoring:
      - Correct columns: 0.25
      - Has rows: 0.05
      - All users have event_count >= 5: 0.15
      - All users have purchase_count >= 1: 0.10
      - avg_session_duration_s > 300 for all rows: 0.10
      - Ordered by event_count desc: 0.10
      - Uses CTE or subquery (syntax check): 0.0 (bonus intent, already in efficiency)
      - Efficiency bonus: 0.25
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.25, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    # event_count >= 5 for all rows
    if "event_count" in cols_lower:
        idx = cols_lower.index("event_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v >= 5 for v in vals):
            partial["event_count_filter"] = 0.15
            score += 0.15

    # purchase_count >= 1
    if "purchase_count" in cols_lower:
        idx = cols_lower.index("purchase_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v >= 1 for v in vals):
            partial["purchase_filter"] = 0.10
            score += 0.10

    # avg_session_duration_s > 300
    if "avg_session_duration_s" in cols_lower:
        idx = cols_lower.index("avg_session_duration_s")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v > 300 for v in vals):
            partial["session_duration_filter"] = 0.10
            score += 0.10

    # ordered by event_count desc
    if _is_ordered_desc(result, "event_count"):
        partial["ordered_desc"] = 0.10
        score += 0.10

    eff = _reward_plan(plan, n_tables=3)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


GRADER_MAP = {
    "task_salary_agg": grade_easy,
    "task_top_customers": grade_medium,
    "task_user_retention": grade_hard,
}
