"""
Inference Script — SQL Query Optimization Environment
=====================================================
Runs an LLM agent against all three tasks using the OpenAI client.

Required environment variables:
    API_BASE_URL   The API endpoint for the LLM (e.g. https://router.huggingface.co/v1)
    MODEL_NAME     The model identifier to use for inference
    HF_TOKEN       Your HuggingFace / API key

Usage:
    python inference.py
"""

import os
import sys
import json
import time
import textwrap
from typing import Any, Dict, List, Optional

from openai import OpenAI

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")

MAX_STEPS = 5
TEMPERATURE = 0.1
MAX_TOKENS = 800

# ---------------------------------------------------------------------------
# Import environment directly (works when run from project root)
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env.environment import SQLQueryEnv
from env.models import SQLAction, DatabaseState


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY or "EMPTY")


def call_llm(system: str, user: str) -> str:
    """Call the LLM and return the text response."""
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""
You are an expert SQL engineer. Your job is to write correct, efficient SQL SELECT queries.

Rules:
- Only write SELECT or WITH (CTE) queries — no INSERT, UPDATE, DELETE.
- Return ONLY the SQL query, nothing else. No markdown fences, no explanation.
- Use standard SQL compatible with SQLite.
- Always alias aggregate columns to the exact names specified in the objective.
- Use ROUND() for decimal precision where specified.
""").strip()


def build_user_prompt(state: DatabaseState, prev_error: Optional[str] = None) -> str:
    # Schema description
    schema_lines = []
    for table in state.schema:
        cols = ", ".join(
            f"{col.name} {col.type.upper()}"
            + (" PK" if col.primary_key else "")
            + (" FK→" + col.foreign_key if col.foreign_key else "")
            + (" IDX" if col.index else "")
            for col in table.columns
        )
        schema_lines.append(f"  Table {table.name} ({table.row_count} rows): {cols}")

    # Sample data
    sample_lines = []
    for table_name, rows in state.sample_data.items():
        if rows:
            sample_lines.append(f"  {table_name} sample: {json.dumps(rows[:2], default=str)}")

    prompt = f"""DATABASE SCHEMA:
{chr(10).join(schema_lines)}

SAMPLE DATA:
{chr(10).join(sample_lines)}

OBJECTIVE:
{state.objective}

CONSTRAINTS:
{chr(10).join('- ' + c for c in state.constraints)}
"""

    if prev_error:
        prompt += f"\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{prev_error}\nFix the SQL and try again.\n"

    prompt += "\nWrite the SQL query now:"
    return prompt


def build_refinement_prompt(state: DatabaseState) -> str:
    """Build a prompt when we have previous result to improve."""
    base = build_user_prompt(state)

    if state.last_result and not state.last_result.error:
        result_preview = {
            "columns": state.last_result.columns,
            "first_row": state.last_result.rows[0] if state.last_result.rows else [],
            "row_count": state.last_result.row_count,
        }
        base += f"\n\nYOUR PREVIOUS ATTEMPT scored {state.last_reward:.2f}/1.0\n"
        base += f"Result preview: {json.dumps(result_preview, default=str)}\n"
        base += "Improve the query based on this feedback. Write the improved SQL now:"
    return base


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_agent(env: SQLQueryEnv, task_id: str) -> Dict[str, Any]:
    """Run the agent on one task. Returns final result summary."""
    print(f"\n{'='*60}")
    print(f"Task: {task_id}")

    state = env.reset(task_id)
    print(f"  Difficulty: {state.difficulty.value}")
    print(f"  Objective: {state.objective[:80]}...")

    best_reward = 0.0
    best_sql = ""
    history: List[Dict[str, Any]] = []
    prev_error: Optional[str] = None

    for step_num in range(1, MAX_STEPS + 1):
        print(f"\n  Step {step_num}/{MAX_STEPS}")

        # Build prompt
        if step_num == 1 or prev_error:
            user_prompt = build_user_prompt(state, prev_error)
        else:
            user_prompt = build_refinement_prompt(state)

        # Call LLM
        try:
            sql = call_llm(SYSTEM_PROMPT, user_prompt)
            # Clean up any accidental markdown fences
            sql = sql.strip().strip("`")
            if sql.lower().startswith("sql"):
                sql = sql[3:].strip()
            print(f"  SQL: {sql[:120]}{'...' if len(sql) > 120 else ''}")
        except Exception as e:
            print(f"  LLM error: {e}")
            time.sleep(2)
            continue

        # Step the environment
        action = SQLAction(sql=sql)
        result = env.step(action)
        reward = result.reward
        state = result.observation

        prev_error = state.last_result.error if state.last_result else None
        if prev_error:
            print(f"  SQL error: {prev_error}")

        print(f"  Reward: {reward:.4f}")
        if result.info.get("grade_detail"):
            print(f"  Partial: {result.info['grade_detail'].get('partial', {})}")

        history.append({
            "step": step_num,
            "sql": sql,
            "reward": reward,
            "error": prev_error,
        })

        if reward > best_reward:
            best_reward = reward
            best_sql = sql

        if result.done:
            if reward >= 1.0:
                print(f"  ✓ Perfect score!")
            else:
                print(f"  Episode ended (max steps or done)")
            break

        time.sleep(0.5)

    return {
        "task_id": task_id,
        "best_reward": best_reward,
        "best_sql": best_sql,
        "steps": len(history),
        "history": history,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("SQL Query Optimization Environment — Inference Script")
    print(f"Model: {MODEL_NAME}")
    print(f"API:   {API_BASE_URL}")

    env = SQLQueryEnv()
    task_ids = [t.task_id for t in env.list_tasks()]
    env.teardown()

    results = []
    for task_id in task_ids:
        env = SQLQueryEnv()
        try:
            r = run_agent(env, task_id)
            results.append(r)
        except Exception as e:
            print(f"\nTask {task_id} failed: {e}")
            results.append({"task_id": task_id, "best_reward": 0.0, "error": str(e)})
        finally:
            env.teardown()
        time.sleep(1)

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    total = 0.0
    for r in results:
        score = r.get("best_reward", 0.0)
        total += score
        status = "✓" if score >= 0.8 else ("~" if score >= 0.4 else "✗")
        print(f"  {status} {r['task_id']}: {score:.4f}")

    avg = total / len(results) if results else 0.0
    print(f"\n  Average score: {avg:.4f}")
    print(f"  Tasks: {len(results)}")

    # Save results
    output_path = "inference_results.json"
    with open(output_path, "w") as f:
        json.dump({"results": results, "average": avg}, f, indent=2, default=str)
    print(f"\n  Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()
