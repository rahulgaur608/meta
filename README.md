---
title: SQL Query Optimization Environment
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# SQL Query Optimization Environment

An OpenEnv-compliant environment for training and evaluating AI agents that write correct, efficient SQL queries.

Agents receive a database schema, sample data, and a natural-language objective. They must produce SQL `SELECT` queries that satisfy the objective. Rewards are based on **data correctness** (validated against reference answers), result structure, ordering, filter accuracy, and query efficiency.

---

## Real-World Utility

SQL query writing and optimization is one of the most common tasks in data engineering, analytics, and backend development. Evaluating how well an agent can translate natural-language requirements into correct, efficient SQL — across a range of complexity — is directly useful for:

- Training coding agents on structured data tasks
- Benchmarking LLMs on multi-table query reasoning
- Evaluating query optimization understanding (index use, join strategy)
- Testing compositional SQL skills (CTEs, window functions, CASE expressions)

---

## Tasks (5 total)

| Task ID | Name | Difficulty | Tables | Total Rows |
|---|---|---|---|---|
| `task_salary_agg` | Department Salary Aggregation | Easy | 1 | 500 |
| `task_top_customers` | Top Customers by Revenue | Medium | 2 | 2,300 |
| `task_inventory_stock` | Inventory Stock Calculation | Medium | 3 | 1,205 |
| `task_user_retention` | High-Value User Retention | Hard | 3 | 5,600 |
| `task_sales_pipeline` | Sales Pipeline Performance | Hard | 3 | 3,230 |

### Task 1 — Easy: Department Salary Aggregation

Write an aggregate query over an `employees` table. Filter for active employees (`is_active = 1`), group by department, compute average salary and headcount, order descending by salary.

**Required columns:** `department`, `avg_salary`, `headcount`

### Task 2 — Medium: Top Customers by Revenue

JOIN `customers` and `orders`. Filter for completed orders only. Aggregate total revenue per customer. Return the top 10 by revenue.

**Required columns:** `customer_id`, `customer_name`, `country`, `total_revenue`, `order_count`

### Task 3 — Medium: Inventory Stock Calculation

JOIN `products` with `inventory_movements` across 5 warehouses. Calculate net stock (sum of all quantity movements) for non-discontinued products. Order by lowest stock first to identify at-risk items.

**Required columns:** `product_id`, `sku`, `product_name`, `category`, `net_stock`, `total_movements`

### Task 4 — Hard: High-Value User Retention Report

Three-table CTE query across `users`, `event_logs`, and `sessions`. Find users with ≥5 events, ≥1 purchase event, and average session duration >300 seconds. Requires multi-CTE or subquery structure.

**Required columns:** `user_id`, `username`, `plan`, `event_count`, `purchase_count`, `avg_session_duration_s`

### Task 5 — Hard: Sales Pipeline Performance Analysis

Three-table CTE analysis across `sales_reps`, `deals`, and `activities`. Calculate won revenue, win rate, average activities per deal, and quota attainment per rep. Requires CASE expressions, multiple CTEs, and percentage calculations.

**Required columns:** `rep_id`, `rep_name`, `region`, `won_revenue`, `win_rate`, `avg_activities_per_deal`, `quota_attainment`

---

## Action Space

```json
{
  "sql": "SELECT ...",
  "explanation": "(optional) Why this approach was chosen"
}
```

Only `SELECT` and `WITH` (CTE) queries are accepted. DML is blocked.

## Observation Space

```json
{
  "task_id": "task_salary_agg",
  "task_name": "Department Salary Aggregation",
  "difficulty": "easy",
  "description": "...",
  "schema": [{ "name": "employees", "columns": [...], "row_count": 500 }],
  "sample_data": { "employees": [{"id": 1, "name": "...", ...}] },
  "objective": "Write a SQL query that returns ...",
  "constraints": ["Only active employees (is_active = 1) ..."],
  "hints": ["Use GROUP BY department with WHERE is_active = 1."],
  "step_count": 1,
  "max_steps": 10,
  "last_sql": "SELECT ...",
  "last_result": { "columns": [...], "rows": [...], "row_count": 6 },
  "last_plan": { "estimated_cost": 0.5, "seq_scans": 0, "index_scans": 1, ... },
  "last_reward": 0.75,
  "done": false
}
```

## Reward Function

Rewards are continuous in `[0.0, 1.0]` with partial credit across multiple dimensions:

| Component | Weight | Description |
|---|---|---|
| Column presence | 15–20% | Are all required columns present and correctly named? |
| **Data correctness** | **35–45%** | Row-by-row comparison against reference SQL output |
| Result structure | 10–20% | Row count, data types, filter correctness |
| Ordering | 10% | Is the result ordered correctly? |
| Efficiency bonus | up to 15% | Does the query use indexes (from SQLite EXPLAIN QUERY PLAN)? |

Graders are **deterministic**: same SQL + same seed → same score, always.

The **data correctness** component is the key differentiator — it runs the reference SQL against the same database and compares results row-by-row with numeric tolerance.

---

## Setup

### Local

```bash
git clone https://github.com/rahulgaur608/meta.git
cd meta
pip install -r requirements.txt

# Run the API server
uvicorn app:app --host 0.0.0.0 --port 7860

# Run tests
python tests/test_env.py

# Run baseline inference (requires API credentials)
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Llama-3.3-70B-Instruct"
export HF_TOKEN="hf_..."
python inference.py
```

### Docker

```bash
docker build -t sql-query-env .
docker run -p 7860:7860 \
  -e API_BASE_URL="https://router.huggingface.co/v1" \
  -e MODEL_NAME="meta-llama/Llama-3.3-70B-Instruct" \
  -e HF_TOKEN="hf_..." \
  sql-query-env
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |
| `GET` | `/tasks` | List all 5 tasks with metadata |
| `POST` | `/reset` | Start a new episode for a task |
| `POST` | `/step` | Submit a SQL query for grading |
| `GET` | `/state` | Get current state without advancing |
| `DELETE` | `/session/{id}` | Clean up session |

### Example interaction

```bash
# Start episode
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "task_salary_agg"}'

# Submit query (use session_id from reset response)
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<from reset>",
    "sql": "SELECT department, ROUND(AVG(salary), 2) as avg_salary, COUNT(*) as headcount FROM employees WHERE is_active = 1 GROUP BY department ORDER BY avg_salary DESC"
  }'
```

---

## Project Structure

```
meta/
├── app.py              # FastAPI server (OpenEnv HTTP API)
├── inference.py        # Baseline LLM agent using OpenAI client
├── openenv.yaml        # OpenEnv spec (5 tasks)
├── Dockerfile          # HF Spaces deployment
├── pyproject.toml      # Dependencies
├── server/
│   └── app.py          # Multi-mode deployment wrapper
├── env/
│   ├── models.py       # Typed data models (dataclass + model_dump())
│   ├── database.py     # SQLite in-memory engine with EXPLAIN analysis
│   └── environment.py  # SQLQueryEnv: reset() / step() / state()
├── tasks/
│   ├── registry.py     # 5 task schemas, seed data, objectives, reference SQL
│   └── graders.py      # Deterministic 0.0–1.0 graders with data validation
└── tests/
    └── test_env.py     # Environment unit tests
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `API_BASE_URL` | LLM API endpoint (e.g. `https://router.huggingface.co/v1`) |
| `MODEL_NAME` | Model identifier (e.g. `meta-llama/Llama-3.3-70B-Instruct`) |
| `HF_TOKEN` | HuggingFace API key |

---

## Baseline Scores (reference)

Scores from the reference SQL solutions:

| Task | Difficulty | Reference Score |
|---|---|---|
| `task_salary_agg` | Easy | 1.0000 |
| `task_top_customers` | Medium | 1.0000 |
| `task_inventory_stock` | Medium | 1.0000 |
| `task_user_retention` | Hard | 1.0000 |
| `task_sales_pipeline` | Hard | 1.0000 |

LLM agents (frontier models) typically score 0.5–0.8 on hard tasks on first attempt, with improvement across steps.
