"""
Task registry for the SQL Query Optimization environment.
Five tasks covering easy → medium → hard difficulty.
Each task specifies schema, seed data, expected answer, reference SQL, and grader logic.
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


def _gen_products_inventory(n_products: int = 200, n_inventory: int = 1000, seed: int = 42) -> tuple[List, List, List]:
    """Generate products, inventory movements, and warehouses for Task 4."""
    rng = random.Random(seed)
    categories = ["Electronics", "Clothing", "Food", "Tools", "Furniture", "Sports"]
    warehouses = [
        {"id": i, "name": f"Warehouse {chr(64+i)}", "city": rng.choice(["NYC", "LA", "CHI", "HOU", "PHX"])}
        for i in range(1, 6)
    ]

    products = []
    for i in range(1, n_products + 1):
        products.append({
            "id": i,
            "sku": f"SKU-{i:04d}",
            "name": f"Product {i}",
            "category": rng.choice(categories),
            "unit_price": round(rng.uniform(5, 500), 2),
            "weight_kg": round(rng.uniform(0.1, 50), 1),
            "is_discontinued": 1 if rng.random() < 0.15 else 0,
        })

    inventory = []
    for i in range(1, n_inventory + 1):
        inventory.append({
            "id": i,
            "product_id": rng.randint(1, n_products),
            "warehouse_id": rng.randint(1, 5),
            "quantity": rng.randint(-50, 200),  # negative = outbound
            "movement_type": rng.choice(["inbound", "outbound", "adjustment", "return"]),
            "movement_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        })

    return products, inventory, warehouses


def _gen_sales_pipeline(n_deals: int = 800, n_reps: int = 30, seed: int = 42) -> tuple[List, List, List]:
    """Generate sales reps, deals, and activities for Task 5."""
    rng = random.Random(seed)
    regions = ["North", "South", "East", "West"]
    rep_names = ["Alex", "Blake", "Casey", "Dana", "Ellis", "Fran", "Glen", "Harper",
                 "Ira", "Jules", "Kelly", "Lane", "Morgan", "Noel", "Pat", "Quinn"]

    reps = []
    for i in range(1, n_reps + 1):
        reps.append({
            "id": i,
            "name": f"{rng.choice(rep_names)} {chr(64 + (i % 26) + 1)}.",
            "region": rng.choice(regions),
            "hire_date": f"202{rng.randint(0,2)}-{rng.randint(1,12):02d}-01",
            "quota": round(rng.uniform(50000, 500000), 2),
        })

    stages = ["prospect", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"]
    deals = []
    for i in range(1, n_deals + 1):
        stage = rng.choice(stages)
        deals.append({
            "id": i,
            "rep_id": rng.randint(1, n_reps),
            "company_name": f"Company {rng.randint(1, 200)}",
            "deal_value": round(rng.uniform(1000, 100000), 2),
            "stage": stage,
            "created_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "close_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}" if stage.startswith("closed") else None,
            "probability": {"prospect": 10, "qualified": 25, "proposal": 50, "negotiation": 75, "closed_won": 100, "closed_lost": 0}[stage],
        })

    activity_types = ["call", "email", "meeting", "demo", "follow_up"]
    activities = []
    for i in range(1, n_deals * 3 + 1):
        activities.append({
            "id": i,
            "deal_id": rng.randint(1, n_deals),
            "activity_type": rng.choice(activity_types),
            "activity_date": f"2023-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "notes": f"Activity note {i}",
            "duration_min": rng.randint(5, 120),
        })

    return reps, deals, activities


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

TASK_EASY_REFERENCE_SQL = """
SELECT department,
       ROUND(AVG(salary), 2) AS avg_salary,
       COUNT(*) AS headcount
FROM employees
WHERE is_active = 1
GROUP BY department
ORDER BY avg_salary DESC
"""


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

TASK_MEDIUM_REFERENCE_SQL = """
SELECT c.id AS customer_id,
       c.name AS customer_name,
       c.country,
       ROUND(SUM(o.amount), 2) AS total_revenue,
       COUNT(o.id) AS order_count
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'completed'
GROUP BY c.id, c.name, c.country
ORDER BY total_revenue DESC
LIMIT 10
"""


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

TASK_HARD_REFERENCE_SQL = """
WITH user_events AS (
    SELECT user_id,
           COUNT(*) AS event_count,
           SUM(CASE WHEN event = 'purchase' THEN 1 ELSE 0 END) AS purchase_count
    FROM event_logs
    GROUP BY user_id
    HAVING event_count >= 5 AND purchase_count >= 1
),
user_sessions AS (
    SELECT user_id,
           ROUND(AVG(duration_s), 1) AS avg_session_duration_s
    FROM sessions
    GROUP BY user_id
    HAVING avg_session_duration_s > 300
)
SELECT u.id AS user_id,
       u.username,
       u.plan,
       ue.event_count,
       ue.purchase_count,
       us.avg_session_duration_s
FROM users u
JOIN user_events ue ON u.id = ue.user_id
JOIN user_sessions us ON u.id = us.user_id
ORDER BY ue.event_count DESC
"""


# ---------------------------------------------------------------------------
# Task 4 — Medium: Inventory Stock Calculation (NEW)
# ---------------------------------------------------------------------------

TASK_INVENTORY_ID = "task_inventory_stock"

def get_task_inventory_schema() -> List[TableSchema]:
    return [
        TableSchema(
            name="products",
            row_count=200,
            description="Product catalog",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="sku", type="text", nullable=False),
                ColumnDef(name="name", type="text", nullable=False),
                ColumnDef(name="category", type="text", nullable=False, index=True),
                ColumnDef(name="unit_price", type="float", nullable=False),
                ColumnDef(name="weight_kg", type="float"),
                ColumnDef(name="is_discontinued", type="integer", nullable=False, index=True),
            ],
        ),
        TableSchema(
            name="inventory_movements",
            row_count=1000,
            description="Stock movements (inbound/outbound/returns/adjustments)",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="product_id", type="integer", nullable=False, foreign_key="products.id", index=True),
                ColumnDef(name="warehouse_id", type="integer", nullable=False, foreign_key="warehouses.id", index=True),
                ColumnDef(name="quantity", type="integer", nullable=False),
                ColumnDef(name="movement_type", type="text", nullable=False, index=True),
                ColumnDef(name="movement_date", type="timestamp", index=True),
            ],
        ),
        TableSchema(
            name="warehouses",
            row_count=5,
            description="Warehouse locations",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="name", type="text", nullable=False),
                ColumnDef(name="city", type="text", nullable=False),
            ],
        ),
    ]

def get_task_inventory_data() -> Dict[str, List[Dict[str, Any]]]:
    products, inventory, warehouses = _gen_products_inventory()
    return {"products": products, "inventory_movements": inventory, "warehouses": warehouses}

TASK_INVENTORY_OBJECTIVE = (
    "Calculate the current net stock for each ACTIVE (non-discontinued) product across ALL warehouses. "
    "Net stock = SUM of all inventory movement quantities (positive = inbound, negative = outbound). "
    "Only include products that have at least one movement. "
    "Return: product_id, sku, product_name, category, net_stock, total_movements. "
    "Order by net_stock ascending (lowest stock first) to identify products at risk."
)

TASK_INVENTORY_EXPECTED_COLUMNS = {
    "product_id", "sku", "product_name", "category", "net_stock", "total_movements"
}

TASK_INVENTORY_REFERENCE_SQL = """
SELECT p.id AS product_id,
       p.sku,
       p.name AS product_name,
       p.category,
       SUM(im.quantity) AS net_stock,
       COUNT(im.id) AS total_movements
FROM products p
JOIN inventory_movements im ON im.product_id = p.id
WHERE p.is_discontinued = 0
GROUP BY p.id, p.sku, p.name, p.category
ORDER BY net_stock ASC
"""


# ---------------------------------------------------------------------------
# Task 5 — Hard: Sales Pipeline Analysis with Ranking (NEW)
# ---------------------------------------------------------------------------

TASK_PIPELINE_ID = "task_sales_pipeline"

def get_task_pipeline_schema() -> List[TableSchema]:
    return [
        TableSchema(
            name="sales_reps",
            row_count=30,
            description="Sales team members with quotas",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="name", type="text", nullable=False),
                ColumnDef(name="region", type="text", nullable=False, index=True),
                ColumnDef(name="hire_date", type="timestamp"),
                ColumnDef(name="quota", type="float", nullable=False),
            ],
        ),
        TableSchema(
            name="deals",
            row_count=800,
            description="Sales opportunities with stage tracking",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="rep_id", type="integer", nullable=False, foreign_key="sales_reps.id", index=True),
                ColumnDef(name="company_name", type="text", nullable=False),
                ColumnDef(name="deal_value", type="float", nullable=False),
                ColumnDef(name="stage", type="text", nullable=False, index=True),
                ColumnDef(name="created_date", type="timestamp", index=True),
                ColumnDef(name="close_date", type="timestamp"),
                ColumnDef(name="probability", type="integer", nullable=False),
            ],
        ),
        TableSchema(
            name="activities",
            row_count=2400,
            description="Sales activities linked to deals",
            columns=[
                ColumnDef(name="id", type="integer", primary_key=True, nullable=False),
                ColumnDef(name="deal_id", type="integer", nullable=False, foreign_key="deals.id", index=True),
                ColumnDef(name="activity_type", type="text", nullable=False, index=True),
                ColumnDef(name="activity_date", type="timestamp", index=True),
                ColumnDef(name="notes", type="text"),
                ColumnDef(name="duration_min", type="integer"),
            ],
        ),
    ]

def get_task_pipeline_data() -> Dict[str, List[Dict[str, Any]]]:
    reps, deals, activities = _gen_sales_pipeline()
    return {"sales_reps": reps, "deals": deals, "activities": activities}

TASK_PIPELINE_OBJECTIVE = (
    "For each sales rep, calculate their pipeline performance: "
    "(1) Total won revenue (sum of deal_value where stage = 'closed_won'), "
    "(2) Win rate (closed_won deals / total closed deals * 100, rounded to 1dp), "
    "(3) Average activities per deal (total activities / total deals, rounded to 1dp), "
    "(4) Quota attainment percentage (won_revenue / quota * 100, rounded to 1dp). "
    "Only include reps who have at least 1 closed_won deal. "
    "Return: rep_id, rep_name, region, won_revenue (rounded 2dp), win_rate, avg_activities_per_deal, quota_attainment. "
    "Order by quota_attainment descending."
)

TASK_PIPELINE_EXPECTED_COLUMNS = {
    "rep_id", "rep_name", "region", "won_revenue", "win_rate",
    "avg_activities_per_deal", "quota_attainment"
}

TASK_PIPELINE_REFERENCE_SQL = """
WITH rep_deals AS (
    SELECT d.rep_id,
           COUNT(*) AS total_deals,
           SUM(CASE WHEN d.stage = 'closed_won' THEN 1 ELSE 0 END) AS won_deals,
           SUM(CASE WHEN d.stage IN ('closed_won', 'closed_lost') THEN 1 ELSE 0 END) AS closed_deals,
           SUM(CASE WHEN d.stage = 'closed_won' THEN d.deal_value ELSE 0 END) AS won_revenue
    FROM deals d
    GROUP BY d.rep_id
    HAVING won_deals >= 1
),
rep_activities AS (
    SELECT d.rep_id,
           COUNT(a.id) AS total_activities
    FROM deals d
    JOIN activities a ON a.deal_id = d.id
    GROUP BY d.rep_id
)
SELECT sr.id AS rep_id,
       sr.name AS rep_name,
       sr.region,
       ROUND(rd.won_revenue, 2) AS won_revenue,
       ROUND(rd.won_deals * 100.0 / rd.closed_deals, 1) AS win_rate,
       ROUND(COALESCE(ra.total_activities, 0) * 1.0 / rd.total_deals, 1) AS avg_activities_per_deal,
       ROUND(rd.won_revenue * 100.0 / sr.quota, 1) AS quota_attainment
FROM sales_reps sr
JOIN rep_deals rd ON sr.id = rd.rep_id
LEFT JOIN rep_activities ra ON sr.id = ra.rep_id
ORDER BY quota_attainment DESC
"""


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
        "reference_sql": TASK_EASY_REFERENCE_SQL,
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
        "reference_sql": TASK_MEDIUM_REFERENCE_SQL,
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
        "reference_sql": TASK_HARD_REFERENCE_SQL,
    },
    TASK_INVENTORY_ID: {
        "schema_fn": get_task_inventory_schema,
        "data_fn": get_task_inventory_data,
        "objective": TASK_INVENTORY_OBJECTIVE,
        "difficulty": DifficultyLevel.medium,
        "name": "Inventory Stock Calculation",
        "description": "Calculate net stock per product by aggregating inventory movements across warehouses.",
        "constraints": [
            "Only non-discontinued products (is_discontinued = 0).",
            "Products must have at least one inventory movement.",
            "Net stock = SUM(quantity) across all warehouses.",
            "Columns: product_id, sku, product_name, category, net_stock, total_movements.",
            "Order by net_stock ascending.",
        ],
        "hints": [
            "JOIN products with inventory_movements on product_id.",
            "WHERE is_discontinued = 0 filters active products.",
            "SUM(quantity) gives net stock (positive + negative movements).",
            "COUNT(im.id) gives total movement count.",
        ],
        "expected_columns": TASK_INVENTORY_EXPECTED_COLUMNS,
        "reference_sql": TASK_INVENTORY_REFERENCE_SQL,
    },
    TASK_PIPELINE_ID: {
        "schema_fn": get_task_pipeline_schema,
        "data_fn": get_task_pipeline_data,
        "objective": TASK_PIPELINE_OBJECTIVE,
        "difficulty": DifficultyLevel.hard,
        "name": "Sales Pipeline Performance Analysis",
        "description": "Multi-CTE analysis of sales reps, deals, and activities with quota attainment.",
        "constraints": [
            "Only include reps with at least 1 closed_won deal.",
            "Win rate = closed_won / total closed deals * 100.",
            "Avg activities per deal = total activities / total deals.",
            "Quota attainment = won_revenue / quota * 100.",
            "Columns: rep_id, rep_name, region, won_revenue, win_rate, avg_activities_per_deal, quota_attainment.",
            "All percentages rounded to 1dp, revenue to 2dp.",
            "Order by quota_attainment descending.",
        ],
        "hints": [
            "Use a CTE for deal-level aggregation per rep.",
            "Use a second CTE for activity counts per rep.",
            "JOIN both CTEs with sales_reps for the final output.",
            "CASE WHEN stage = 'closed_won' for filtering won deals.",
        ],
        "expected_columns": TASK_PIPELINE_EXPECTED_COLUMNS,
        "reference_sql": TASK_PIPELINE_REFERENCE_SQL,
    },
}
