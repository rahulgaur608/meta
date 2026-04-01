"""
Agent graders for each task.
Each grader returns a float in [0.0, 1.0] with partial credit.
Graders are deterministic: same SQL + same DB → same score.

Key improvement: graders now compare agent results against reference SQL
output for data-level correctness, not just structural checks.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Set, List

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.models import ExecutionPlan, QueryResult


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

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


def _is_ordered_asc(result: QueryResult, col_name: str) -> bool:
    """Check if the target column is in ascending order."""
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
    return all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))


def _reward_plan(plan: ExecutionPlan, n_tables: int = 1) -> float:
    """
    Partial reward for query efficiency.
    Better plans (more index scans, fewer seq scans) score higher.
    Returns 0.0–0.15 bonus.
    """
    if plan.seq_scans == 0 and plan.index_scans > 0:
        return 0.15
    if plan.seq_scans <= n_tables:
        return 0.05
    return 0.0


def _data_match_score(
    result: QueryResult,
    ref_result: QueryResult,
    key_col: str,
    value_cols: List[str],
    tolerance: float = 0.01,
) -> float:
    """
    Compare agent result rows against reference result rows.
    Returns a score in [0.0, 1.0] based on how many rows match.

    Matching logic:
    - Find matching rows by key_col value
    - For each matched row, compare value_cols with tolerance for floats
    """
    if result.error or ref_result.error:
        return 0.0
    if result.row_count == 0 or ref_result.row_count == 0:
        return 0.0

    res_cols = [c.lower() for c in result.columns]
    ref_cols = [c.lower() for c in ref_result.columns]

    key_lower = key_col.lower()
    if key_lower not in res_cols or key_lower not in ref_cols:
        return 0.0

    res_key_idx = res_cols.index(key_lower)
    ref_key_idx = ref_cols.index(key_lower)

    # Build reference lookup: key -> {col: val}
    ref_lookup = {}
    for row in ref_result.rows:
        key = row[ref_key_idx]
        ref_lookup[key] = {}
        for vc in value_cols:
            vc_lower = vc.lower()
            if vc_lower in ref_cols:
                ref_lookup[key][vc_lower] = row[ref_cols.index(vc_lower)]

    matched_rows = 0
    total_ref = len(ref_result.rows)

    for row in result.rows:
        key = row[res_key_idx]
        if key not in ref_lookup:
            continue

        row_match = True
        for vc in value_cols:
            vc_lower = vc.lower()
            if vc_lower not in res_cols:
                row_match = False
                break
            res_val = row[res_cols.index(vc_lower)]
            ref_val = ref_lookup[key].get(vc_lower)
            if ref_val is None:
                continue
            # Compare with tolerance for numeric values
            try:
                if abs(float(res_val) - float(ref_val)) > tolerance:
                    row_match = False
                    break
            except (TypeError, ValueError):
                if str(res_val).lower() != str(ref_val).lower():
                    row_match = False
                    break

        if row_match:
            matched_rows += 1

    return matched_rows / max(1, total_ref)


# ---------------------------------------------------------------------------
# Task 1 — Easy: Department Salary Aggregation
# ---------------------------------------------------------------------------

def grade_easy(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
    ref_result: Optional[QueryResult] = None,
) -> Dict[str, Any]:
    """
    Task 1 grader: department salary aggregation.
    Scoring:
      - Correct columns present: 0.20
      - Has rows (non-empty result): 0.05
      - avg_salary column contains floats: 0.05
      - headcount column contains integers: 0.05
      - Ordered by avg_salary desc: 0.10
      - Data matches reference: 0.40
      - Efficiency bonus (index used): 0.15
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.20, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    if "avg_salary" in cols_lower:
        idx = cols_lower.index("avg_salary")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            partial["avg_salary_numeric"] = 0.05
            score += 0.05

    if "headcount" in cols_lower:
        idx = cols_lower.index("headcount")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals):
            partial["headcount_integer"] = 0.05
            score += 0.05

    if _is_ordered_desc(result, "avg_salary"):
        partial["ordered_desc"] = 0.10
        score += 0.10

    # Data-level validation against reference
    if ref_result and not ref_result.error:
        data_score = _data_match_score(result, ref_result, "department", ["avg_salary", "headcount"], tolerance=0.05)
        partial["data_correctness"] = round(data_score * 0.40, 3)
        score += partial["data_correctness"]

    eff = _reward_plan(plan, n_tables=1)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


# ---------------------------------------------------------------------------
# Task 2 — Medium: Top Customers by Revenue
# ---------------------------------------------------------------------------

def grade_medium(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
    ref_result: Optional[QueryResult] = None,
) -> Dict[str, Any]:
    """
    Task 2 grader: top-10 customers by revenue.
    Scoring:
      - Correct columns: 0.15
      - Exactly 10 rows: 0.10
      - total_revenue is float: 0.05
      - order_count is integer: 0.05
      - Ordered by total_revenue desc: 0.10
      - Data matches reference: 0.40
      - Efficiency bonus: 0.15
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.15, 3)
    score += partial["columns"]

    if result.row_count == 10:
        partial["row_count_10"] = 0.10
        score += 0.10
    elif 8 <= result.row_count <= 12:
        partial["row_count_near"] = 0.03
        score += 0.03

    cols_lower = [c.lower() for c in result.columns]

    if "total_revenue" in cols_lower:
        idx = cols_lower.index("total_revenue")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) and v > 0 for v in vals):
            partial["revenue_positive"] = 0.05
            score += 0.05

    if "order_count" in cols_lower:
        idx = cols_lower.index("order_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals):
            partial["order_count_integer"] = 0.05
            score += 0.05

    if _is_ordered_desc(result, "total_revenue"):
        partial["ordered_desc"] = 0.10
        score += 0.10

    if ref_result and not ref_result.error:
        data_score = _data_match_score(result, ref_result, "customer_id", ["total_revenue", "order_count"], tolerance=0.05)
        partial["data_correctness"] = round(data_score * 0.40, 3)
        score += partial["data_correctness"]

    eff = _reward_plan(plan, n_tables=2)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


# ---------------------------------------------------------------------------
# Task 3 — Hard: High-Value User Retention Report
# ---------------------------------------------------------------------------

def grade_hard(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
    ref_result: Optional[QueryResult] = None,
) -> Dict[str, Any]:
    """
    Task 3 grader: high-value user retention report.
    Scoring:
      - Correct columns: 0.15
      - Has rows: 0.05
      - All users have event_count >= 5: 0.10
      - All users have purchase_count >= 1: 0.05
      - avg_session_duration_s > 300 for all rows: 0.05
      - Ordered by event_count desc: 0.10
      - Data matches reference: 0.35
      - Efficiency bonus: 0.15
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.15, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    if "event_count" in cols_lower:
        idx = cols_lower.index("event_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v >= 5 for v in vals):
            partial["event_count_filter"] = 0.10
            score += 0.10

    if "purchase_count" in cols_lower:
        idx = cols_lower.index("purchase_count")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v >= 1 for v in vals):
            partial["purchase_filter"] = 0.05
            score += 0.05

    if "avg_session_duration_s" in cols_lower:
        idx = cols_lower.index("avg_session_duration_s")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(v > 300 for v in vals):
            partial["session_duration_filter"] = 0.05
            score += 0.05

    if _is_ordered_desc(result, "event_count"):
        partial["ordered_desc"] = 0.10
        score += 0.10

    if ref_result and not ref_result.error:
        data_score = _data_match_score(result, ref_result, "user_id", ["event_count", "purchase_count", "avg_session_duration_s"], tolerance=0.5)
        partial["data_correctness"] = round(data_score * 0.35, 3)
        score += partial["data_correctness"]

    eff = _reward_plan(plan, n_tables=3)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


# ---------------------------------------------------------------------------
# Task 4 — Medium: Inventory Stock Calculation
# ---------------------------------------------------------------------------

def grade_inventory(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
    ref_result: Optional[QueryResult] = None,
) -> Dict[str, Any]:
    """
    Task 4 grader: inventory stock calculation.
    Scoring:
      - Correct columns: 0.15
      - Has rows: 0.05
      - net_stock is numeric: 0.05
      - total_movements is integer: 0.05
      - Ordered by net_stock ascending: 0.10
      - Data matches reference: 0.45
      - Efficiency bonus: 0.15
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.15, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    if "net_stock" in cols_lower:
        idx = cols_lower.index("net_stock")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            partial["net_stock_numeric"] = 0.05
            score += 0.05

    if "total_movements" in cols_lower:
        idx = cols_lower.index("total_movements")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in vals):
            partial["total_movements_integer"] = 0.05
            score += 0.05

    if _is_ordered_asc(result, "net_stock"):
        partial["ordered_asc"] = 0.10
        score += 0.10

    if ref_result and not ref_result.error:
        data_score = _data_match_score(result, ref_result, "product_id", ["net_stock", "total_movements"], tolerance=0.5)
        partial["data_correctness"] = round(data_score * 0.45, 3)
        score += partial["data_correctness"]

    eff = _reward_plan(plan, n_tables=2)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


# ---------------------------------------------------------------------------
# Task 5 — Hard: Sales Pipeline Performance
# ---------------------------------------------------------------------------

def grade_pipeline(
    result: QueryResult,
    plan: ExecutionPlan,
    sql: str,
    expected_cols: Set[str],
    ref_result: Optional[QueryResult] = None,
) -> Dict[str, Any]:
    """
    Task 5 grader: sales pipeline performance analysis.
    Scoring:
      - Correct columns: 0.15
      - Has rows: 0.05
      - win_rate in valid range (0-100): 0.05
      - quota_attainment is numeric: 0.05
      - Ordered by quota_attainment desc: 0.10
      - Data matches reference: 0.45
      - Efficiency bonus: 0.15
    """
    if result.error:
        return {"score": 0.0, "reason": f"SQL error: {result.error}", "partial": {}}

    score = 0.0
    partial: Dict[str, float] = {}

    col_score = _col_match(result.columns, expected_cols)
    partial["columns"] = round(col_score * 0.15, 3)
    score += partial["columns"]

    if _has_rows(result):
        partial["has_rows"] = 0.05
        score += 0.05

    cols_lower = [c.lower() for c in result.columns]

    if "win_rate" in cols_lower:
        idx = cols_lower.index("win_rate")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in vals):
            partial["win_rate_valid"] = 0.05
            score += 0.05

    if "quota_attainment" in cols_lower:
        idx = cols_lower.index("quota_attainment")
        vals = [row[idx] for row in result.rows if row[idx] is not None]
        if vals and all(isinstance(v, (int, float)) for v in vals):
            partial["quota_attainment_numeric"] = 0.05
            score += 0.05

    if _is_ordered_desc(result, "quota_attainment"):
        partial["ordered_desc"] = 0.10
        score += 0.10

    if ref_result and not ref_result.error:
        data_score = _data_match_score(result, ref_result, "rep_id", ["won_revenue", "win_rate", "quota_attainment"], tolerance=1.0)
        partial["data_correctness"] = round(data_score * 0.45, 3)
        score += partial["data_correctness"]

    eff = _reward_plan(plan, n_tables=3)
    partial["efficiency"] = eff
    score += eff

    return {"score": min(1.0, round(score, 4)), "reason": "OK", "partial": partial}


# ---------------------------------------------------------------------------
# Grader Map
# ---------------------------------------------------------------------------

GRADER_MAP = {
    "task_salary_agg": grade_easy,
    "task_top_customers": grade_medium,
    "task_user_retention": grade_hard,
    "task_inventory_stock": grade_inventory,
    "task_sales_pipeline": grade_pipeline,
}
