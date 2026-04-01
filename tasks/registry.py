"""
Task registry for the SQL Query Optimization environment.
Three tasks covering easy → medium → hard difficulty.
Each task specifies schema, seed data, expected answer, and grader logic.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.models import ColumnDef, DifficultyLevel, TableSchema


# ---------------------------------------------------------------------------
# Seed data generators
# ---------------------------------------------------------------------------

def _gen_employees(n: int = 500, seed: int = 42) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    depts = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations"]
    names = [
        "Alice", "Bob", "Carol", "David", "Eve", "Frank", "Grace", "Hank",
        "Iris", "Jack", "Karen", "Leo", "Mona", "Ned", "Olivia", "Pete",
    ]
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": i,
            "name": f"{rng.choice(names)} {rng.choice(names)}{i}",
            "department": rng.choice(depts),
            "salary": round(rng.uniform(40000, 200000), 2),
            "hire_date": f"202{rng.randint(0,3)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "manager_id": rng.randint(1, max(1, i - 1)) if i > 1 else None,
            "is_active": 1 if rng.random() > 0.1 else 0,
        })
    return rows


def _gen_orders(n: int = 2000, n_customers: int = 300, seed: int = 42) -> tuple[List, List]:
    rng = random.Random(seed)
    countries = ["US", "UK", "DE", "FR", "JP", "CA", "AU", "BR"]
    customers = []
    for i in range(1, n_customers + 1):
        customers.append({
            "id": i,
            "name": f"Customer {i}",
            "country": rng.choice(countries),
            "email": f"cust{i}@example.com",
            "created_at": f"202{rng.randint(0,2)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        })

    products = ["Widget A", "Widget B", "Gadget X", "Gadget Y", "Tool Z", "Part Q"]
    orders = []
    for i in range(1, n + 1):
        orders.append({
            "id": i,
            "customer_id": rng.randint(1, n_customers),
            "product": rng.choice(products),
            "amount": round(rng.uniform(10, 5000), 2),
            "status": rng.choice(["completed", "pending", "refunded", "completed", "completed"]),
            "order_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "region": rng.choice(["AMER", "EMEA", "APAC"]),
        })
    return customers, orders


def _gen_logs(n: int = 5000, n_users: int = 100, seed: int = 42) -> tuple[List, List, List]:
    rng = random.Random(seed)
    users = [
        {
            "id": i,
            "username": f"user_{i}",
            "plan": rng.choice(["free", "pro", "enterprise"]),
            "signup_date": f"202{rng.randint(0,2)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        }
        for i in range(1, n_users + 1)
    ]

    events = ["page_view", "click", "purchase", "logout", "error", "api_call"]
    pages = ["/home", "/dashboard", "/settings", "/checkout", "/docs", "/pricing"]
    logs = []
    for i in range(1, n + 1):
        user_id = rng.randint(1, n_users)
        logs.append({
            "id": i,
            "user_id": user_id,
            "event": rng.choice(events),
            "page": rng.choice(pages),
            "duration_ms": rng.randint(50, 8000),
            "ts": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d} {rng.randint(0,23):02d}:{rng.randint(0,59):02d}:00",
            "session_id": f"sess_{rng.randint(1, n_users * 5)}",
        })

    sessions = []
    for i in range(1, n_users * 5 + 1):
        sessions.append({
            "id": f"sess_{i}",
            "user_id": rng.randint(1, n_users),
            "started_at": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d} {rng.randint(0,23):02d}:00:00",
            "duration_s": rng.randint(30, 3600),
            "device": rng.choice(["desktop", "mobile", "tablet"]),
        })

    return users, logs, sessions


# ---------------------------------------------------------------------------
# Task 1 — Easy: Aggregate Query
# ---------------------------------------------------------------------------

TASK_EASY_ID = "task_salary_agg"

def get_task_easy_schema() -> List[TableSchema]:
    return [
        TableSchema(
            name="employees",
            row_count=500,
            description="Employee records with salary and department info",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="name", type="text", nullable=False),
                ColumnDef(name="department", type="text", nullable=False, index=True),
                ColumnDef(name="salary", type="float", nullable=False),
                ColumnDef(name="hire_date", type="timestamp"),
                ColumnDef(name="manager_id", type="integer", foreign_key="employees.id"),
                ColumnDef(name="is_active", type="integer", nullable=False, index=True),
            ],
        )
    ]

def get_task_easy_data() -> Dict[str, List[Dict[str, Any]]]:
    return {"employees": _gen_employees(500)}

TASK_EASY_OBJECTIVE = (
    "Write a SQL query that returns each department's average salary and headcount, "
    "but ONLY for active employees (is_active = 1). "
    "Order by average salary descending. "
    "Columns: department, avg_salary (rounded to 2 decimal places), headcount."
)

TASK_EASY_EXPECTED_COLUMNS = {"department", "avg_salary", "headcount"}


# ---------------------------------------------------------------------------
# Task 2 — Medium: Multi-table JOIN with filtering
# ---------------------------------------------------------------------------

TASK_MEDIUM_ID = "task_top_customers"

def get_task_medium_schema() -> List[TableSchema]:
    return [
        TableSchema(
            name="customers",
            row_count=300,
            description="Customer master records",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="name", type="text", nullable=False),
                ColumnDef(name="country", type="text", nullable=False, index=True),
                ColumnDef(name="email", type="text"),
                ColumnDef(name="created_at", type="timestamp"),
            ],
        ),
        TableSchema(
            name="orders",
            row_count=2000,
            description="Order transactions",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="customer_id", type="integer", nullable=False, foreign_key="customers.id", index=True),
                ColumnDef(name="product", type="text"),
                ColumnDef(name="amount", type="float", nullable=False),
                ColumnDef(name="status", type="text", nullable=False, index=True),
                ColumnDef(name="order_date", type="timestamp", index=True),
                ColumnDef(name="region", type="text"),
            ],
        ),
    ]

def get_task_medium_data() -> Dict[str, List[Dict[str, Any]]]:
    customers, orders = _gen_orders()
    return {"customers": customers, "orders": orders}

TASK_MEDIUM_OBJECTIVE = (
    "Find the top 10 customers by total revenue from COMPLETED orders only. "
    "Join customers with orders, filter status = 'completed', "
    "group by customer, sum the amount, and return the top 10. "
    "Columns: customer_id, customer_name, country, total_revenue (rounded 2dp), order_count. "
    "Order by total_revenue descending."
)

TASK_MEDIUM_EXPECTED_COLUMNS = {
    "customer_id", "customer_name", "country", "total_revenue", "order_count"
}


# ---------------------------------------------------------------------------
# Task 3 — Hard: Window functions + CTE + subquery
# ---------------------------------------------------------------------------

TASK_HARD_ID = "task_user_retention"

def get_task_hard_schema() -> List[TableSchema]:
    return [
        TableSchema(
            name="users",
            row_count=100,
            description="Registered users",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="username", type="text", nullable=False),
                ColumnDef(name="plan", type="text", nullable=False, index=True),
                ColumnDef(name="signup_date", type="timestamp"),
            ],
        ),
        TableSchema(
            name="event_logs",
            row_count=5000,
            description="User activity event stream",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="user_id", type="integer", nullable=False, foreign_key="users.id", index=True),
                ColumnDef(name="event", type="text", nullable=False, index=True),
                ColumnDef(name="page", type="text"),
                ColumnDef(name="duration_ms", type="integer"),
                ColumnDef(name="ts", type="timestamp", nullable=False, index=True),
                ColumnDef(name="session_id", type="text", index=True),
            ],
        ),
        TableSchema(
            name="sessions",
            row_count=500,
            description="User sessions with device and duration info",
            columns=[
                ColumnDef(name="id", type="text", primary_key=True, nullable=False),
                ColumnDef(name="user_id", type="integer", nullable=False, foreign_key="users.id", index=True),
                ColumnDef(name="started_at", type="timestamp"),
                ColumnDef(name="duration_s", type="integer"),
                ColumnDef(name="device", type="text", index=True),
            ],
        ),
    ]

def get_task_hard_data() -> Dict[str, List[Dict[str, Any]]]:
    users, logs, sessions = _gen_logs()
    return {"users": users, "event_logs": logs, "sessions": sessions}

TASK_HARD_OBJECTIVE = (
    "Using a CTE or subquery, identify users who: "
    "(1) have at least 5 events in event_logs, "
    "(2) have at least 1 'purchase' event, "
    "and (3) whose average session duration (from sessions table) is above 300 seconds. "
    "For each qualifying user, return: user_id, username, plan, event_count, purchase_count, avg_session_duration_s (rounded to 1dp). "
    "Order by event_count descending."
)

TASK_HARD_EXPECTED_COLUMNS = {
    "user_id", "username", "plan", "event_count", "purchase_count", "avg_session_duration_s"
}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TASK_REGISTRY = {
    TASK_EASY_ID: {
        "schema_fn": get_task_easy_schema,
        "data_fn": get_task_easy_data,
        "objective": TASK_EASY_OBJECTIVE,
        "difficulty": DifficultyLevel.easy,
        "name": "Department Salary Aggregation",
        "description": "Write an aggregate query over an employees table.",
        "constraints": [
            "Only active employees (is_active = 1) should be included.",
            "Result must include: department, avg_salary, headcount.",
            "Order by avg_salary descending.",
            "avg_salary must be rounded to 2 decimal places.",
        ],
        "hints": [
            "Use GROUP BY department with WHERE is_active = 1.",
            "ROUND(AVG(salary), 2) gives 2dp precision.",
            "COUNT(*) gives headcount per group.",
        ],
        "expected_columns": TASK_EASY_EXPECTED_COLUMNS,
    },
    TASK_MEDIUM_ID: {
        "schema_fn": get_task_medium_schema,
        "data_fn": get_task_medium_data,
        "objective": TASK_MEDIUM_OBJECTIVE,
        "difficulty": DifficultyLevel.medium,
        "name": "Top Customers by Revenue",
        "description": "JOIN customers and orders to find top spenders.",
        "constraints": [
            "Only orders with status = 'completed' count toward revenue.",
            "Must return exactly 10 rows (LIMIT 10).",
            "Columns: customer_id, customer_name, country, total_revenue, order_count.",
            "Order by total_revenue descending.",
        ],
        "hints": [
            "JOIN customers c ON o.customer_id = c.id",
            "Filter: WHERE o.status = 'completed'",
            "SUM(o.amount) gives total revenue per customer.",
            "Use LIMIT 10 after ORDER BY.",
        ],
        "expected_columns": TASK_MEDIUM_EXPECTED_COLUMNS,
    },
    TASK_HARD_ID: {
        "schema_fn": get_task_hard_schema,
        "data_fn": get_task_hard_data,
        "objective": TASK_HARD_OBJECTIVE,
        "difficulty": DifficultyLevel.hard,
        "name": "High-Value User Retention Report",
        "description": "Multi-CTE query joining users, event_logs, and sessions with window functions.",
        "constraints": [
            "Users must have >= 5 events total.",
            "Users must have >= 1 'purchase' event.",
            "Users' avg session duration must exceed 300 seconds.",
            "Columns: user_id, username, plan, event_count, purchase_count, avg_session_duration_s.",
            "avg_session_duration_s rounded to 1dp.",
            "Order by event_count descending.",
        ],
        "hints": [
            "Use a CTE to compute per-user event stats from event_logs.",
            "Join with a second CTE or subquery for session stats.",
            "HAVING clause or WHERE on CTE column for the filters.",
            "AVG(s.duration_s) for session duration, joined on user_id.",
        ],
        "expected_columns": TASK_HARD_EXPECTED_COLUMNS,
    },
}
