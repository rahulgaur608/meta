---
title: SQL Query Optimization Environment
emoji: 📊
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: app.py
pinned: false
---

# SQL Query Optimization Environment

An OpenEnv-compliant environment for training and evaluating AI agents that write correct, efficient SQL queries.

Agents receive a database schema, sample data, and a natural-language objective. They must produce SQL `SELECT` queries that satisfy the objective. Rewards are based on correctness, result structure, ordering, filter accuracy, and query efficiency.

---

## Real-World Utility

SQL query writing and optimization is one of the most common tasks in data engineering, analytics, and backend development. Evaluating how well an agent can translate natural-language requirements into correct, efficient SQL — across a range of complexity — is directly useful for:

- Training coding agents on structured data tasks
- Benchmarking LLMs on multi-table query reasoning
- Evaluating query optimization understanding (index use, join strategy)

---

## Tasks

| Task ID | Name | Difficulty | Tables | Rows |
|---|---|---|---|---|
| `task_salary_agg` | Department Salary Aggregation | Easy | 1 | 500 |
| `task_top_customers` | Top Customers by Revenue | Medium | 2 | 2,300 |
| `task_user_retention` | High-Value User Retention Report | Hard | 3 | 5,600 |

### Task 1 — Easy: Department Salary Aggregation

Write an aggregate query over an `employees` table. Filter for active employees (`is_active = 1`), group by department, compute average salary and headcount, order descending by salary.

**Required columns:** `department`, `avg_salary`, `headcount`

### Task 2 — Medium: Top Customers by Revenue

JOIN `customers` and `orders`. Filter for completed orders only. Aggregate total revenue per customer. Return the top 10 by revenue.

**Required columns:** `customer_id`, `customer_name`, `country`, `total_revenue`, `order_count`

### Task 3 — Hard: High-Value User Retention Report

Three-table CTE query across `users`, `event_logs`, and `sessions`. Find users with ≥5 events, ≥1 purchase event, and average session duration >300 seconds. Requires multi-CTE or subquery structure.

**Required columns:** `user_id`, `username`, `plan`, `event_count`, `purchase_count`, `avg_session_duration_s`

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
| Column presence | 25–30% | Are all required columns present and correctly named? |
| Result correctness | 25–40% | Row count, data types, positive values, filter correctness |
| Ordering | 10–15% | Is the result ordered correctly (e.g. DESC by revenue)? |
| Efficiency bonus | up to 25% | Does the query use indexes (from SQLite EXPLAIN QUERY PLAN)? |

Graders are **deterministic**: same SQL + same seed → same score, always.

---

## Setup

### Local

```bash
git clone <repo>
cd sql-query-env
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
| `GET` | `/tasks` | List all tasks |
| `POST` | `/reset` | Start a new episode |
| `POST` | `/step` | Submit a SQL query |
| `GET` | `/state` | Get current state |
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
sql-query-env/
├── app.py              # FastAPI server
├── inference.py        # Baseline LLM agent
├── openenv.yaml        # OpenEnv spec
├── Dockerfile
├── requirements.txt
├── env/
│   ├── models.py       # Typed data models (dataclass + model_dump())
│   ├── database.py     # SQLite in-memory engine with EXPLAIN analysis
│   └── environment.py  # SQLQueryEnv: reset() / step() / state()
└── tasks/
    ├── registry.py     # Task schemas, seed data, objectives
    └── graders.py      # Deterministic 0.0–1.0 graders
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

Scores from a correct reference solution:

| Task | Score |
|---|---|
| `task_salary_agg` (easy) | 1.0000 |
| `task_top_customers` (medium) | 0.9500 |
| `task_user_retention` (hard) | 0.8500 |

LLM agents (frontier models) typically score 0.5–0.8 on hard tasks on first attempt, with improvement across steps.
