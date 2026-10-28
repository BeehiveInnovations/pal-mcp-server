"""
Stateful Orchestrator and Advanced Task Dependency Graph for PAL MCP Server

This module implements:
1. Layered Context & Memory (Session State, Working Memory, Long-Term Memory, Task State Graph, Evidence Store).
2. Task Dependency Graph (DAG) with dynamic task insertion, prerequisites, and status tracking.
3. Evidence-Aware Validation (Hypothesis -> Investigation -> Evidence -> Validation -> Confirmed/Rejected/Inconclusive).
4. Autonomous Orchestrator Supervisor for continuous re-planning, model collaboration, and failure recovery.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskNode(BaseModel):
    """Represents a discrete task in the investigation dependency graph"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    status: Literal["pending", "running", "completed", "blocked", "failed"] = "pending"
    prerequisites: list[str] = Field(default_factory=list)  # task_ids that must complete first
    assigned_model: Optional[str] = None
    fallback_model: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    result_summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvidenceItem(BaseModel):
    """Represents a verified or hypothesized piece of evidence distinct from model claims"""
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    claim: str
    source_tool: str
    validation_state: Literal["hypothesis", "investigation", "evidence_collected", "validation", "confirmed", "rejected", "inconclusive"] = "hypothesis"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    raw_data: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class InvestigationSession(BaseModel):
    """Persistent stateful session container for multi-query investigations"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    objective: str
    status: Literal["active", "paused", "completed", "failed"] = "active"
    tasks: dict[str, TaskNode] = Field(default_factory=dict)
    evidence_store: dict[str, EvidenceItem] = Field(default_factory=dict)
    long_term_memory: dict[str, Any] = Field(default_factory=dict)  # findings, decisions, artifacts
    working_memory: list[dict[str, Any]] = Field(default_factory=list)  # recent interactions
    summaries: list[str] = Field(default_factory=list)  # semantic compaction summaries
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def add_task(self, title: str, description: str, prerequisites: Optional[list[str]] = None, assigned_model: Optional[str] = None) -> TaskNode:
        task = TaskNode(
            title=title,
            description=description,
            prerequisites=prerequisites or [],
            assigned_model=assigned_model
        )
        self.tasks[task.task_id] = task
        self.last_updated_at = datetime.now(timezone.utc).isoformat()
        return task

    def add_evidence(self, claim: str, source_tool: str, validation_state: str = "hypothesis", raw_data: Optional[str] = None) -> EvidenceItem:
        evidence = EvidenceItem(
            claim=claim,
            source_tool=source_tool,
            validation_state=validation_state,
            raw_data=raw_data
        )
        self.evidence_store[evidence.evidence_id] = evidence
        self.last_updated_at = datetime.now(timezone.utc).isoformat()
        return evidence

    def get_next_runnable_tasks(self) -> list[TaskNode]:
        """Determine tasks whose prerequisites are fully completed"""
        runnable = []
        for task in self.tasks.values():
            if task.status == "pending":
                prereqs_met = all(
                    self.tasks.get(p_id) and self.tasks[p_id].status == "completed"
                    for p_id in task.prerequisites
                )
                if prereqs_met:
                    runnable.append(task)
        return runnable


class OrchestratorSupervisor:
    """Supervises investigation execution state, task graph evaluation, and re-planning"""

    def __init__(self, session: InvestigationSession):
        self.session = session

    def evaluate_progress(self) -> dict[str, Any]:
        """Evaluate current investigation state and suggest next actions"""
        total_tasks = len(self.session.tasks)
        completed_tasks = sum(1 for t in self.session.tasks.values() if t.status == "completed")
        failed_tasks = sum(1 for t in self.session.tasks.values() if t.status == "failed")
        runnable = self.session.get_next_runnable_tasks()

        status_summary = {
            "session_id": self.session.session_id,
            "objective": self.session.objective,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "runnable_tasks": len(runnable),
            "is_complete": total_tasks > 0 and completed_tasks == total_tasks,
            "next_runnable": [t.title for t in runnable]
        }
        return status_summary

    def check_replan_needed(self, task_id: str, outcome_data: str) -> bool:
        """Detects if task outcome contradicts assumptions or requires new tasks"""
        # Heuristic: check if outcome contains unexpected technical findings or blockages
        triggers = ["unexpected", "jwt", "auth bypass", "vulnerability", "error", "blocked", "schema mismatch"]
        lower_outcome = outcome_data.lower()
        return any(trig in lower_outcome for trig in triggers)

    def dynamic_replan(self, trigger_task_id: str, discovery_note: str) -> TaskNode:
        """Dynamically inserts a new analysis or validation task into the DAG"""
        new_task = self.session.add_task(
            title=f"Investigate Discovery: {discovery_note[:40]}...",
            description=f"Triggered by task {trigger_task_id}. Discovery: {discovery_note}",
            prerequisites=[trigger_task_id],
            assigned_model="gemini-3.1-pro-preview"
        )
        logger.info(f"Orchestrator Supervisor: Dynamically inserted task {new_task.task_id} due to discovery.")
        return new_task
