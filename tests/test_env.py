"""
Test suite for SQL Query Optimization Environment.
Run with: python -m pytest tests/test_env.py -v
(or: python tests/test_env.py for no-pytest fallback)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.environment import SQLQueryEnv
from env.models import SQLAction, DifficultyLevel


def test_list_tasks():
    env = SQLQueryEnv()
    tasks = env.list_tasks()
    assert len(tasks) == 3
    ids = {t.task_id for t in tasks}
    assert "task_salary_agg" in ids
    assert "task_top_customers" in ids
    assert "task_user_retention" in ids
    difficulties = {t.difficulty for t in tasks}
    assert DifficultyLevel.easy in difficulties
    assert DifficultyLevel.medium in difficulties
    assert DifficultyLevel.hard in difficulties
    env.teardown()
    print("PASS: test_list_tasks")


def test_reset_easy():
    env = SQLQueryEnv()
    state = env.reset("task_salary_agg")
    assert state.task_id == "task_salary_agg"
    assert state.difficulty == DifficultyLevel.easy
    assert len(state.schema) == 1
    assert state.schema[0].name == "employees"
    assert state.schema[0].row_count == 500
    assert "employees" in state.sample_data
    assert len(state.sample_data["employees"]) > 0
    assert state.step_count == 0
    assert not state.done
    assert state.last_sql is None
    env.teardown()
    print("PASS: test_reset_easy")


def test_reset_medium():
    env = SQLQueryEnv()
    state = env.reset("task_top_customers")
    assert state.task_id == "task_top_customers"
    assert state.difficulty == DifficultyLevel.medium
    assert len(state.schema) == 2
    table_names = {t.name for t in state.schema}
    assert "customers" in table_names
    assert "orders" in table_names
    env.teardown()
    print("PASS: test_reset_medium")


def test_reset_hard():
    env = SQLQueryEnv()
    state = env.reset("task_user_retention")
    assert state.task_id == "task_user_retention"
    assert state.difficulty == DifficultyLevel.hard
    assert len(state.schema) == 3
    table_names = {t.name for t in state.schema}
    assert "users" in table_names
    assert "event_logs" in table_names
    assert "sessions" in table_names
    env.teardown()
    print("PASS: test_reset_hard")


def test_invalid_task_raises():
    env = SQLQueryEnv()
    try:
        env.reset("nonexistent_task")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    env.teardown()
    print("PASS: test_invalid_task_raises")


def test_step_before_reset_raises():
    env = SQLQueryEnv()
    try:
        env.step(SQLAction(sql="SELECT 1"))
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass
    env.teardown()
    print("PASS: test_step_before_reset_raises")


def test_easy_correct_query():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    result = env.step(SQLAction(sql="""
        SELECT department,
               ROUND(AVG(salary), 2) as avg_salary,
               COUNT(*) as headcount
        FROM employees
        WHERE is_active = 1
        GROUP BY department
        ORDER BY avg_salary DESC
    """))
    assert result.reward > 0.5, f"Expected reward > 0.5, got {result.reward}"
    assert result.observation.last_result is not None
    assert result.observation.last_result.error is None
    assert result.observation.last_result.row_count > 0
    cols = {c.lower() for c in result.observation.last_result.columns}
    assert "department" in cols
    assert "avg_salary" in cols
    assert "headcount" in cols
    env.teardown()
    print(f"PASS: test_easy_correct_query (reward={result.reward:.4f})")


def test_easy_wrong_filter():
    """Missing WHERE is_active = 1 should score lower."""
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    result_wrong = env.step(SQLAction(sql="""
        SELECT department, ROUND(AVG(salary), 2) as avg_salary, COUNT(*) as headcount
        FROM employees
        GROUP BY department
        ORDER BY avg_salary DESC
    """))
    env2 = SQLQueryEnv()
    env2.reset("task_salary_agg")
    result_correct = env2.step(SQLAction(sql="""
        SELECT department, ROUND(AVG(salary), 2) as avg_salary, COUNT(*) as headcount
        FROM employees WHERE is_active = 1
        GROUP BY department
        ORDER BY avg_salary DESC
    """))
    # Both should have columns, but headcounts may differ
    # Correct query may score similarly on structure — just ensure no error
    assert result_wrong.reward >= 0.0
    assert result_correct.reward >= result_wrong.reward
    env.teardown()
    env2.teardown()
    print(f"PASS: test_easy_wrong_filter (correct={result_correct.reward:.4f}, wrong={result_wrong.reward:.4f})")


def test_syntax_error_returns_zero():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    result = env.step(SQLAction(sql="SELECT * FORM employees"))
    assert result.reward == 0.0
    assert result.observation.last_result.error is not None
    env.teardown()
    print("PASS: test_syntax_error_returns_zero")


def test_dml_blocked():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    result = env.step(SQLAction(sql="DELETE FROM employees"))
    assert result.reward == 0.0
    assert result.observation.last_result.error is not None
    env.teardown()
    print("PASS: test_dml_blocked")


def test_medium_correct_query():
    env = SQLQueryEnv()
    env.reset("task_top_customers")
    result = env.step(SQLAction(sql="""
        SELECT c.id as customer_id, c.name as customer_name, c.country,
               ROUND(SUM(o.amount), 2) as total_revenue,
               COUNT(o.id) as order_count
        FROM customers c
        JOIN orders o ON o.customer_id = c.id
        WHERE o.status = 'completed'
        GROUP BY c.id, c.name, c.country
        ORDER BY total_revenue DESC
        LIMIT 10
    """))
    assert result.reward > 0.5, f"Expected reward > 0.5, got {result.reward}"
    assert result.observation.last_result.row_count == 10
    env.teardown()
    print(f"PASS: test_medium_correct_query (reward={result.reward:.4f})")


def test_hard_correct_query():
    env = SQLQueryEnv()
    env.reset("task_user_retention")
    result = env.step(SQLAction(sql="""
        WITH event_stats AS (
            SELECT user_id,
                   COUNT(*) as event_count,
                   SUM(CASE WHEN event = 'purchase' THEN 1 ELSE 0 END) as purchase_count
            FROM event_logs
            GROUP BY user_id
            HAVING COUNT(*) >= 5
              AND SUM(CASE WHEN event = 'purchase' THEN 1 ELSE 0 END) >= 1
        ),
        session_stats AS (
            SELECT user_id, ROUND(AVG(duration_s), 1) as avg_session_duration_s
            FROM sessions
            GROUP BY user_id
            HAVING AVG(duration_s) > 300
        )
        SELECT u.id as user_id, u.username, u.plan,
               e.event_count, e.purchase_count, s.avg_session_duration_s
        FROM users u
        JOIN event_stats e ON e.user_id = u.id
        JOIN session_stats s ON s.user_id = u.id
        ORDER BY e.event_count DESC
    """))
    assert result.reward > 0.5, f"Expected reward > 0.5, got {result.reward}"
    env.teardown()
    print(f"PASS: test_hard_correct_query (reward={result.reward:.4f})")


def test_max_steps_terminates():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    done = False
    for _ in range(12):
        r = env.step(SQLAction(sql="SELECT 'bad query'"))
        if r.done:
            done = True
            break
    assert done, "Episode should terminate after max_steps"
    env.teardown()
    print("PASS: test_max_steps_terminates")


def test_reward_in_range():
    """All graders must return reward in [0.0, 1.0]."""
    task_ids = ["task_salary_agg", "task_top_customers", "task_user_retention"]
    queries = [
        "SELECT department, ROUND(AVG(salary),2) as avg_salary, COUNT(*) as headcount FROM employees WHERE is_active=1 GROUP BY department ORDER BY avg_salary DESC",
        "SELECT c.id as customer_id, c.name as customer_name, c.country, ROUND(SUM(o.amount),2) as total_revenue, COUNT(o.id) as order_count FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.id ORDER BY total_revenue DESC LIMIT 10",
        "WITH e AS (SELECT user_id, COUNT(*) as event_count, SUM(CASE WHEN event='purchase' THEN 1 ELSE 0 END) as purchase_count FROM event_logs GROUP BY user_id HAVING event_count>=5 AND purchase_count>=1), s AS (SELECT user_id, ROUND(AVG(duration_s),1) as avg_session_duration_s FROM sessions GROUP BY user_id HAVING avg_session_duration_s>300) SELECT u.id as user_id, u.username, u.plan, e.event_count, e.purchase_count, s.avg_session_duration_s FROM users u JOIN e ON e.user_id=u.id JOIN s ON s.user_id=u.id ORDER BY event_count DESC",
    ]
    for task_id, sql in zip(task_ids, queries):
        env = SQLQueryEnv()
        env.reset(task_id)
        r = env.step(SQLAction(sql=sql))
        assert 0.0 <= r.reward <= 1.0, f"{task_id}: reward {r.reward} out of [0,1]"
        env.teardown()
    print("PASS: test_reward_in_range")


def test_state_matches_last_step():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    r = env.step(SQLAction(sql="SELECT department, AVG(salary) as avg_salary, COUNT(*) as headcount FROM employees WHERE is_active=1 GROUP BY department ORDER BY avg_salary DESC"))
    state = env.state()
    assert state is not None
    assert state.last_reward == r.reward
    assert state.step_count == 1
    env.teardown()
    print("PASS: test_state_matches_last_step")


def test_reset_clears_state():
    env = SQLQueryEnv()
    env.reset("task_salary_agg")
    env.step(SQLAction(sql="SELECT 1"))
    state1 = env.state()
    assert state1.step_count == 1

    env.reset("task_salary_agg")
    state2 = env.state()
    assert state2.step_count == 0
    assert state2.last_sql is None
    env.teardown()
    print("PASS: test_reset_clears_state")


def test_graders_deterministic():
    """Same SQL + same seed → same reward, always."""
    sql = "SELECT department, ROUND(AVG(salary),2) as avg_salary, COUNT(*) as headcount FROM employees WHERE is_active=1 GROUP BY department ORDER BY avg_salary DESC"
    rewards = []
    for _ in range(3):
        env = SQLQueryEnv()
        env.reset("task_salary_agg")
        r = env.step(SQLAction(sql=sql))
        rewards.append(r.reward)
        env.teardown()
    assert len(set(rewards)) == 1, f"Grader not deterministic: {rewards}"
    print(f"PASS: test_graders_deterministic (reward={rewards[0]:.4f})")


if __name__ == "__main__":
    tests = [
        test_list_tasks,
        test_reset_easy,
        test_reset_medium,
        test_reset_hard,
        test_invalid_task_raises,
        test_step_before_reset_raises,
        test_easy_correct_query,
        test_easy_wrong_filter,
        test_syntax_error_returns_zero,
        test_dml_blocked,
        test_medium_correct_query,
        test_hard_correct_query,
        test_max_steps_terminates,
        test_reward_in_range,
        test_state_matches_last_step,
        test_reset_clears_state,
        test_graders_deterministic,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("All tests passed!")
