"""
Test suite for stateful orchestrator, task dependency graphs, and evidence tracking.
"""

from utils.stateful_orchestrator import InvestigationSession, OrchestratorSupervisor


def test_investigation_session_and_task_dag():
    session = InvestigationSession(objective="Analyze and secure target API")

    # Add tasks with dependencies
    t1 = session.add_task(title="Reconnaissance", description="Gather endpoints and tech stack")
    t2 = session.add_task(title="Endpoint Discovery", description="Find all API routes", prerequisites=[t1.task_id])
    session.add_task(title="Auth Testing", description="Test authentication mechanisms", prerequisites=[t2.task_id])

    # Initially only t1 should be runnable
    runnable = session.get_next_runnable_tasks()
    assert len(runnable) == 1
    assert runnable[0].task_id == t1.task_id

    # Complete t1
    t1.status = "completed"
    runnable = session.get_next_runnable_tasks()
    assert len(runnable) == 1
    assert runnable[0].task_id == t2.task_id


def test_orchestrator_supervisor_and_replan():
    session = InvestigationSession(objective="Security Audit")
    t1 = session.add_task(title="Initial Scan", description="Scan ports")

    supervisor = OrchestratorSupervisor(session)
    summary = supervisor.evaluate_progress()
    assert summary["total_tasks"] == 1
    assert summary["completed_tasks"] == 0

    # Test dynamic replan trigger
    t1.status = "completed"
    discovery = "Unexpected custom JWT implementation detected with weak signature validation"
    assert supervisor.check_replan_needed(t1.task_id, discovery) is True

    new_task = supervisor.dynamic_replan(t1.task_id, discovery)
    assert new_task.task_id in session.tasks
    assert t1.task_id in new_task.prerequisites


def test_evidence_tracking():
    session = InvestigationSession(objective="Vulnerability Assessment")
    evidence = session.add_evidence(
        claim="Endpoint /api/users exposes unauthenticated PII",
        source_tool="secaudit",
        validation_state="evidence_collected",
        raw_data="HTTP/1.1 200 OK\n[{\"id\": 1, \"email\": \"test@example.com\"}]"
    )
    assert evidence.evidence_id in session.evidence_store
    assert session.evidence_store[evidence.evidence_id].validation_state == "evidence_collected"
