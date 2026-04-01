"""
SQLQueryEnv — OpenEnv-compliant environment for SQL query optimization.
Implements step(), reset(), state(), and list_tasks().
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meta.env.database import DatabaseEngine
from meta.env.models import (
    DatabaseState,
    DifficultyLevel,
    QueryResult,
    SQLAction,
    StepResult,
    TableSchema,
    TaskInfo,
)
from meta.tasks.graders import GRADER_MAP
from meta.tasks.registry import TASK_REGISTRY


class SQLQueryEnv:
    """
    Real-world SQL Query Optimization Environment.

    An agent receives a database schema, sample data, and a natural-language
    objective. It must write a SQL SELECT query that correctly answers the
    objective. Rewards are based on correctness, ordering, filter accuracy,
    and query efficiency (use of indexes vs sequential scans).

    Compatible with the OpenEnv step()/reset()/state() API.
    """

    MAX_STEPS_PER_TASK = 10

    def __init__(self) -> None:
        self._db = DatabaseEngine()
        self._current_task_id: Optional[str] = None
        self._state: Optional[DatabaseState] = None
        self._step_count: int = 0

    # ------------------------------------------------------------------
    # OpenEnv API
    # ------------------------------------------------------------------

    def list_tasks(self) -> List[TaskInfo]:
        """Return metadata for all available tasks."""
        tasks = []
        for task_id, cfg in TASK_REGISTRY.items():
            tasks.append(
                TaskInfo(
                    task_id=task_id,
                    name=cfg["name"],
                    difficulty=cfg["difficulty"],
                    description=cfg["description"],
                    objective=cfg["objective"],
                )
            )
        return tasks

    def reset(self, task_id: str, seed: Optional[int] = None) -> DatabaseState:
        """
        Initialize the environment for the given task.
        Tears down any previous session, re-seeds the database, and returns
        the initial observation (DatabaseState).
        """
        if task_id not in TASK_REGISTRY:
            raise ValueError(f"Unknown task_id: {task_id!r}. Available: {list(TASK_REGISTRY)}")

        self._db.teardown()
        cfg = TASK_REGISTRY[task_id]

        schema: List[TableSchema] = cfg["schema_fn"]()
        seed_data: Dict[str, Any] = cfg["data_fn"]()
        self._db.setup(schema, seed_data)

        self._current_task_id = task_id
        self._step_count = 0

        # Build sample data for the observation (first 5 rows per table)
        sample: Dict[str, List[Dict[str, Any]]] = {}
        for table in schema:
            result, _ = self._db.execute_query(f'SELECT * FROM "{table.name}" LIMIT 5')
            if not result.error:
                sample[table.name] = [
                    dict(zip(result.columns, row)) for row in result.rows
                ]

        self._state = DatabaseState(
            task_id=task_id,
            task_name=cfg["name"],
            difficulty=cfg["difficulty"],
            description=cfg["description"],
            schema=schema,
            sample_data=sample,
            objective=cfg["objective"],
            constraints=cfg["constraints"],
            hints=cfg["hints"],
            step_count=0,
            max_steps=self.MAX_STEPS_PER_TASK,
            done=False,
        )
        return self._state

    def step(self, action: SQLAction) -> StepResult:
        """
        Execute a SQL query and return the graded result.

        Args:
            action: SQLAction with the SQL string to execute.

        Returns:
            StepResult with observation, reward (0.0–1.0), done flag, and info.
        """
        if self._state is None or self._current_task_id is None:
            raise RuntimeError("Call reset() before step().")

        self._step_count += 1
        cfg = TASK_REGISTRY[self._current_task_id]
        grader = GRADER_MAP[self._current_task_id]

        # Execute the query
        result, elapsed_ms = self._db.execute_query(action.sql)
        plan = self._db.get_execution_plan(action.sql)

        # Grade the result
        grade = grader(result, plan, action.sql, cfg["expected_columns"])
        reward: float = grade["score"]

        # Episode ends if: max steps reached OR perfect score
        done = self._step_count >= self.MAX_STEPS_PER_TASK or reward >= 1.0

        # Update state
        self._state = DatabaseState(
            task_id=self._state.task_id,
            task_name=self._state.task_name,
            difficulty=self._state.difficulty,
            description=self._state.description,
            schema=self._state.schema,
            sample_data=self._state.sample_data,
            objective=self._state.objective,
            constraints=self._state.constraints,
            hints=self._state.hints,
            step_count=self._step_count,
            max_steps=self.MAX_STEPS_PER_TASK,
            last_sql=action.sql,
            last_result=result,
            last_plan=plan,
            last_reward=reward,
            done=done,
        )

        info: Dict[str, Any] = {
            "elapsed_ms": round(elapsed_ms, 2),
            "grade_detail": grade,
            "explanation": action.explanation,
        }

        return StepResult(
            observation=self._state,
            reward=reward,
            done=done,
            info=info,
        )

    def state(self) -> Optional[DatabaseState]:
        """Return current environment state without advancing the episode."""
        return self._state

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def teardown(self) -> None:
        """Release all resources."""
        self._db.teardown()
        self._state = None
        self._current_task_id = None
