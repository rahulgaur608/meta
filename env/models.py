"""
Typed models for the SQL Query Optimization Environment.
Uses dataclasses with a Pydantic-compatible .model_dump() shim so the same
code works both locally (no pydantic) and in the deployed container (pydantic v2).
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional


def _dc_dump(obj) -> Any:
    """Recursively convert a dataclass (or list/dict/enum) to plain Python."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dc_dump(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_dc_dump(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _dc_dump(v) for k, v in obj.items()}
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _model(cls):
    """Decorator: wraps a dataclass with a .model_dump() method."""
    cls = dataclasses.dataclass(cls)
    cls.model_dump = lambda self: _dc_dump(self)
    return cls


class DifficultyLevel(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


@_model
class ColumnDef:
    name: str
    type: str  # "integer", "text", "float", "boolean", "timestamp"
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = None  # "table.column"
    index: bool = False
    description: str = ""


@_model
class TableSchema:
    name: str
    columns: List[ColumnDef]
    row_count: int
    description: str = ""


@_model
class QueryResult:
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    error: Optional[str] = None


@_model
class ExecutionPlan:
    estimated_cost: float
    seq_scans: int
    index_scans: int
    joins: int
    sort_operations: int
    estimated_rows: int


@_model
class SQLAction:
    sql: str
    explanation: Optional[str] = None


@_model
class DatabaseState:
    task_id: str
    task_name: str
    difficulty: DifficultyLevel
    description: str
    schema: List[TableSchema]
    sample_data: Dict[str, List[Dict[str, Any]]]
    objective: str
    constraints: List[str]
    hints: List[str]
    step_count: int
    max_steps: int
    last_sql: Optional[str] = None
    last_result: Optional[QueryResult] = None
    last_plan: Optional[ExecutionPlan] = None
    last_reward: float = 0.0
    done: bool = False


@_model
class StepResult:
    observation: DatabaseState
    reward: float
    done: bool
    info: Dict[str, Any]


@_model
class TaskInfo:
    task_id: str
    name: str
    difficulty: DifficultyLevel
    description: str
    objective: str
