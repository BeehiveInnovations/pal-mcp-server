#!/usr/bin/env python3
"""
Ralph Loop Utilities - Task management and state persistence for Ralph Loop.

This module provides utilities for managing the Ralph Loop workflow:
- PRD (Product Requirements Document) task management
- Progress tracking and learning records
- State persistence via JSON files

Zero-cost implementation using PAL MCP's CLI Provider for free model access.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A single task in the PRD."""

    id: int
    description: str
    status: TaskStatus = TaskStatus.PENDING
    success_criteria: str = ""
    files_to_modify: list[str] = field(default_factory=list)
    notes: str = ""
    attempts: int = 0
    last_error: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        result = asdict(self)
        result["status"] = self.status.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create task from dictionary."""
        data = data.copy()
        data["status"] = TaskStatus(data.get("status", "pending"))
        return cls(**data)


@dataclass
class PRD:
    """Product Requirements Document - the task list for Ralph Loop."""

    project_name: str
    description: str
    tasks: list[Task] = field(default_factory=list)
    passes: bool = False
    iteration: int = 0
    max_iterations: int = 100
    created_at: str = ""
    updated_at: str = ""
    learnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert PRD to dictionary."""
        return {
            "project_name": self.project_name,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
            "passes": self.passes,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "learnings": self.learnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PRD:
        """Create PRD from dictionary."""
        tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        return cls(
            project_name=data.get("project_name", ""),
            description=data.get("description", ""),
            tasks=tasks,
            passes=data.get("passes", False),
            iteration=data.get("iteration", 0),
            max_iterations=data.get("max_iterations", 100),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            learnings=data.get("learnings", []),
        )

    def get_next_task(self) -> Task | None:
        """Get the next pending or in-progress task."""
        # First, check for in-progress tasks
        for task in self.tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                return task
        # Then, get the first pending task
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                return task
        return None

    def get_task_by_id(self, task_id: int) -> Task | None:
        """Get a task by its ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def mark_task_in_progress(self, task_id: int) -> bool:
        """Mark a task as in progress."""
        task = self.get_task_by_id(task_id)
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.attempts += 1
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def mark_task_done(self, task_id: int, notes: str = "") -> bool:
        """Mark a task as done."""
        task = self.get_task_by_id(task_id)
        if task:
            task.status = TaskStatus.DONE
            task.completed_at = datetime.now().isoformat()
            if notes:
                task.notes = notes
            self.updated_at = datetime.now().isoformat()
            self._check_completion()
            return True
        return False

    def mark_task_failed(self, task_id: int, error: str = "") -> bool:
        """Mark a task as failed."""
        task = self.get_task_by_id(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.last_error = error
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def reset_task(self, task_id: int) -> bool:
        """Reset a task to pending status."""
        task = self.get_task_by_id(task_id)
        if task:
            task.status = TaskStatus.PENDING
            task.last_error = ""
            self.updated_at = datetime.now().isoformat()
            return True
        return False

    def add_learning(self, learning: str) -> None:
        """Add a learning from this iteration."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.learnings.append(f"[{timestamp}] {learning}")
        self.updated_at = datetime.now().isoformat()

    def _check_completion(self) -> None:
        """Check if all tasks are done and update passes flag."""
        if not self.tasks:
            return
        all_done = all(t.status == TaskStatus.DONE for t in self.tasks)
        self.passes = all_done

    def get_progress_summary(self) -> dict[str, Any]:
        """Get a summary of progress."""
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.status == TaskStatus.DONE)
        in_progress = sum(1 for t in self.tasks if t.status == TaskStatus.IN_PROGRESS)
        failed = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
        pending = sum(1 for t in self.tasks if t.status == TaskStatus.PENDING)

        return {
            "total": total,
            "done": done,
            "in_progress": in_progress,
            "failed": failed,
            "pending": pending,
            "progress_percent": round(done / total * 100, 1) if total > 0 else 0,
            "iteration": self.iteration,
            "passes": self.passes,
        }


class RalphManager:
    """Manager for Ralph Loop state and operations."""

    def __init__(
        self,
        prd_path: str = "prd.json",
        progress_path: str = "progress.txt",
        working_dir: str | None = None,
    ):
        """Initialize Ralph Manager.

        Args:
            prd_path: Path to the PRD JSON file.
            progress_path: Path to the progress/learning log file.
            working_dir: Working directory for the project.
        """
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.prd_path = self.working_dir / prd_path
        self.progress_path = self.working_dir / progress_path
        self.prd: PRD | None = None

    def load_prd(self) -> PRD:
        """Load PRD from file."""
        if not self.prd_path.exists():
            raise FileNotFoundError(f"PRD file not found: {self.prd_path}")

        with open(self.prd_path, encoding="utf-8") as f:
            data = json.load(f)

        self.prd = PRD.from_dict(data)
        return self.prd

    def save_prd(self) -> None:
        """Save PRD to file."""
        if not self.prd:
            raise ValueError("No PRD loaded")

        self.prd.updated_at = datetime.now().isoformat()

        with open(self.prd_path, "w", encoding="utf-8") as f:
            json.dump(self.prd.to_dict(), f, indent=2, ensure_ascii=False)

    def create_prd(
        self,
        project_name: str,
        description: str,
        tasks: list[dict[str, Any]],
        max_iterations: int = 100,
    ) -> PRD:
        """Create a new PRD.

        Args:
            project_name: Name of the project.
            description: Project description.
            tasks: List of task dictionaries with at least 'description' key.
            max_iterations: Maximum number of loop iterations.

        Returns:
            The created PRD.
        """
        task_objects = []
        for i, task_data in enumerate(tasks, start=1):
            task = Task(
                id=task_data.get("id", i),
                description=task_data["description"],
                success_criteria=task_data.get("success_criteria", ""),
                files_to_modify=task_data.get("files_to_modify", []),
            )
            task_objects.append(task)

        self.prd = PRD(
            project_name=project_name,
            description=description,
            tasks=task_objects,
            max_iterations=max_iterations,
        )

        self.save_prd()
        return self.prd

    def increment_iteration(self) -> int:
        """Increment the iteration counter."""
        if not self.prd:
            self.load_prd()

        self.prd.iteration += 1
        self.save_prd()
        return self.prd.iteration

    def should_continue(self) -> bool:
        """Check if the loop should continue."""
        if not self.prd:
            self.load_prd()

        # Stop if all tasks pass
        if self.prd.passes:
            return False

        # Stop if max iterations reached
        if self.prd.iteration >= self.prd.max_iterations:
            return False

        # Stop if no more tasks to work on
        next_task = self.prd.get_next_task()
        if next_task is None:
            return False

        return True

    def log_progress(self, message: str) -> None:
        """Log a progress message to the progress file."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        iteration = self.prd.iteration if self.prd else 0

        log_entry = f"[{timestamp}] [Iteration {iteration}] {message}\n"

        with open(self.progress_path, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def log_learning(self, learning: str) -> None:
        """Log a learning and add it to the PRD."""
        if not self.prd:
            self.load_prd()

        self.prd.add_learning(learning)
        self.save_prd()

        # Also log to progress file
        self.log_progress(f"LEARNING: {learning}")

    def get_context_for_ai(self) -> str:
        """Generate context string for AI prompt."""
        if not self.prd:
            self.load_prd()

        next_task = self.prd.get_next_task()
        progress = self.prd.get_progress_summary()

        context = f"""## Project: {self.prd.project_name}

{self.prd.description}

## Progress
- Iteration: {progress['iteration']}
- Tasks: {progress['done']}/{progress['total']} completed ({progress['progress_percent']}%)
- Status: {'ALL TASKS COMPLETE' if self.prd.passes else 'In Progress'}

## Current Task
"""

        if next_task:
            context += f"""
### Task #{next_task.id}: {next_task.description}

**Success Criteria:** {next_task.success_criteria or 'Not specified'}

**Files to Modify:** {', '.join(next_task.files_to_modify) if next_task.files_to_modify else 'Not specified'}

**Attempts:** {next_task.attempts}
"""
            if next_task.last_error:
                context += f"""
**Previous Error:** {next_task.last_error}
"""
        else:
            context += "\nNo pending tasks."

        # Add recent learnings
        if self.prd.learnings:
            context += "\n## Recent Learnings\n"
            for learning in self.prd.learnings[-5:]:  # Last 5 learnings
                context += f"- {learning}\n"

        return context

    def build_consensus_prompt(self, task: Task | None = None) -> str:
        """Build a prompt for consensus decision-making."""
        if not self.prd:
            self.load_prd()

        if task is None:
            task = self.prd.get_next_task()

        if task is None:
            return "No tasks to work on."

        prompt = f"""## Ralph Loop Decision Request

**Project:** {self.prd.project_name}
**Task #{task.id}:** {task.description}

**Success Criteria:**
{task.success_criteria or 'Code quality checks pass (ruff, black, isort, pytest)'}

**Files to Consider:**
{chr(10).join(f'- {f}' for f in task.files_to_modify) if task.files_to_modify else '- To be determined based on task'}

**Previous Attempts:** {task.attempts}
"""

        if task.last_error:
            prompt += f"""
**Previous Error (must be fixed):**
```
{task.last_error}
```
"""

        prompt += """
**Question for Consensus:**
What is the best approach to complete this task? Consider:
1. What specific changes are needed?
2. What are potential risks or edge cases?
3. How can we ensure the success criteria are met?
"""

        return prompt


# CLI Interface
def main():
    """CLI interface for Ralph utilities."""
    import argparse

    parser = argparse.ArgumentParser(description="Ralph Loop Utilities")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init command
    init_parser = subparsers.add_parser("init", help="Initialize a new PRD")
    init_parser.add_argument("--name", required=True, help="Project name")
    init_parser.add_argument("--description", required=True, help="Project description")
    init_parser.add_argument("--tasks-file", help="JSON file with tasks")

    # status command
    subparsers.add_parser("status", help="Show current status")

    # next command
    subparsers.add_parser("next", help="Get next task")

    # context command
    subparsers.add_parser("context", help="Get AI context")

    # done command
    done_parser = subparsers.add_parser("done", help="Mark task as done")
    done_parser.add_argument("task_id", type=int, help="Task ID to mark as done")
    done_parser.add_argument("--notes", default="", help="Completion notes")

    # fail command
    fail_parser = subparsers.add_parser("fail", help="Mark task as failed")
    fail_parser.add_argument("task_id", type=int, help="Task ID to mark as failed")
    fail_parser.add_argument("--error", default="", help="Error message")

    # start command
    start_parser = subparsers.add_parser("start", help="Mark task as in progress")
    start_parser.add_argument("task_id", type=int, help="Task ID to start")

    # learn command
    learn_parser = subparsers.add_parser("learn", help="Record a learning")
    learn_parser.add_argument("message", help="Learning message")

    # check command
    subparsers.add_parser("check", help="Check if loop should continue")

    # iterate command
    subparsers.add_parser("iterate", help="Increment iteration counter")

    # consensus-prompt command
    subparsers.add_parser("consensus-prompt", help="Get consensus prompt for current task")

    args = parser.parse_args()

    manager = RalphManager()

    try:
        if args.command == "init":
            tasks = []
            if args.tasks_file:
                with open(args.tasks_file, encoding="utf-8") as f:
                    tasks = json.load(f)
            prd = manager.create_prd(args.name, args.description, tasks)
            print(f"Created PRD: {manager.prd_path}")
            print(json.dumps(prd.to_dict(), indent=2))

        elif args.command == "status":
            prd = manager.load_prd()
            progress = prd.get_progress_summary()
            print(f"Project: {prd.project_name}")
            print(f"Progress: {progress['done']}/{progress['total']} ({progress['progress_percent']}%)")
            print(f"Iteration: {progress['iteration']}")
            print(f"Passes: {progress['passes']}")
            print("\nTasks:")
            for task in prd.tasks:
                status_icon = {"done": "✅", "in_progress": "🔄", "failed": "❌", "pending": "⏳", "blocked": "🚫"}
                icon = status_icon.get(task.status.value, "❓")
                print(f"  {icon} [{task.id}] {task.description} ({task.status.value})")

        elif args.command == "next":
            prd = manager.load_prd()
            task = prd.get_next_task()
            if task:
                print(json.dumps(task.to_dict(), indent=2))
            else:
                print("No pending tasks")
                sys.exit(1)

        elif args.command == "context":
            context = manager.get_context_for_ai()
            print(context)

        elif args.command == "done":
            manager.load_prd()
            if manager.prd.mark_task_done(args.task_id, args.notes):
                manager.save_prd()
                manager.log_progress(f"Task #{args.task_id} completed")
                print(f"Task #{args.task_id} marked as done")
            else:
                print(f"Task #{args.task_id} not found")
                sys.exit(1)

        elif args.command == "fail":
            manager.load_prd()
            if manager.prd.mark_task_failed(args.task_id, args.error):
                manager.save_prd()
                manager.log_progress(f"Task #{args.task_id} failed: {args.error}")
                print(f"Task #{args.task_id} marked as failed")
            else:
                print(f"Task #{args.task_id} not found")
                sys.exit(1)

        elif args.command == "start":
            manager.load_prd()
            if manager.prd.mark_task_in_progress(args.task_id):
                manager.save_prd()
                manager.log_progress(f"Task #{args.task_id} started")
                print(f"Task #{args.task_id} marked as in progress")
            else:
                print(f"Task #{args.task_id} not found")
                sys.exit(1)

        elif args.command == "learn":
            manager.log_learning(args.message)
            print(f"Learning recorded: {args.message}")

        elif args.command == "check":
            should_continue = manager.should_continue()
            print("continue" if should_continue else "stop")
            sys.exit(0 if should_continue else 1)

        elif args.command == "iterate":
            iteration = manager.increment_iteration()
            manager.log_progress(f"Starting iteration {iteration}")
            print(f"Iteration: {iteration}")

        elif args.command == "consensus-prompt":
            prompt = manager.build_consensus_prompt()
            print(prompt)

        else:
            parser.print_help()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run 'ralph_utils.py init' first to create a PRD")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
