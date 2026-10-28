"""
Test suite for advanced autonomous features: Self-Healing, Knowledge Graph, Context Pruner, and Consensus Voting.
"""

import pytest
from utils.advanced_autonomy import (
    SelfHealingToolExecutor,
    FindingKnowledgeGraph,
    AdaptiveContextPruner,
    ConsensusVotingEngine,
)


def test_self_healing_executor():
    # Test healing missing file_path
    err = "File not found or missing"
    args = {"file_path": ""}
    success, healed_args, notes = SelfHealingToolExecutor.diagnose_and_heal(err, args)
    assert success is True
    assert healed_args["file_path"] == "."
    assert "Healed" in notes

    # Test healing unavailable model
    err_model = "Model 'invalid' is not available with current API keys."
    args_model = {"model": "invalid"}
    success_m, healed_m, _ = SelfHealingToolExecutor.diagnose_and_heal(err_model, args_model)
    assert success_m is True
    assert healed_m["model"] == "gemini-3.6-flash"


def test_finding_knowledge_graph():
    kg = FindingKnowledgeGraph()
    kg.add_finding("f1", "SQL Injection in Login", "Security", "Input sanitization missing")
    kg.add_finding("f2", "Database Exfiltration Risk", "Risk", "Sensitive tables exposed")
    kg.link_findings("f1", "f2", "leads_to")

    related = kg.get_related_findings("f1")
    assert len(related) == 1
    assert related[0]["relation"] == "leads_to"
    assert related[0]["target"]["title"] == "Database Exfiltration Risk"


def test_adaptive_context_pruner():
    items = [
        {"title": "Unrelated Document", "content": "Cooking recipe for pasta."},
        {"title": "API Auth", "content": "Authentication token validation logic in jwt.py."},
        {"title": "Database Schema", "content": "Users table schema and indexes."}
    ]
    task = "Verify authentication token security in jwt.py"
    pruned = AdaptiveContextPruner.prune_context(task, items, max_items=1)
    assert len(pruned) == 1
    assert "Auth" in pruned[0]["title"]


def test_consensus_voting_engine():
    responses = [
        {"model": "gemini-pro", "verdict": "vulnerable", "confidence": 0.9},
        {"model": "gpt-5", "verdict": "vulnerable", "confidence": 0.8},
        {"model": "claude", "verdict": "safe", "confidence": 0.6}
    ]
    result = ConsensusVotingEngine.calculate_consensus(responses)
    assert result["consensus"] == "vulnerable"
    assert result["total_votes"] == 3
    assert result["confidence"] > 0.5
