"""
Advanced Autonomous Capabilities for PAL MCP Server:
1. Self-Healing Tool Execution (Auto-Retry & Parameter Correction)
2. Semantic Knowledge Graph & Finding Cross-Referencing
3. Adaptive Token Budgeting & Dynamic Context Pruning
4. Automated Multi-Model Consensus Voting
"""

import logging
import re
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SelfHealingToolExecutor:
    """Automatically detects tool execution failures and applies heuristic parameter corrections"""

    @staticmethod
    def diagnose_and_heal(error_message: str, original_arguments: dict[str, Any]) -> tuple[bool, dict[str, Any], str]:
        """
        Analyze error message and attempt parameter/argument healing.
        Returns (success_flag, corrected_arguments, diagnosis_notes)
        """
        healed_args = dict(original_arguments)
        notes = ""

        # Heuristic 1: Missing required file path or empty target
        if "file" in error_message.lower() and ("not found" in error_message.lower() or "missing" in error_message.lower()):
            if "file_path" in healed_args and not healed_args["file_path"]:
                healed_args["file_path"] = "."
                notes = "Healed missing file_path to root directory '.'."
                return True, healed_args, notes

        # Heuristic 2: Invalid model name or unavailable model substitution
        if "model" in error_message.lower() and "not available" in error_message.lower():
            if "model" in healed_args:
                healed_args["model"] = "gemini-3.6-flash"
                notes = "Healed unavailable model to fallback 'gemini-3.6-flash'."
                return True, healed_args, notes

        # Heuristic 3: JSON decode or syntax error in payload
        if "json" in error_message.lower() or "syntax" in error_message.lower():
            notes = "Detected JSON/syntax formatting error in payload."
            return False, healed_args, notes

        return False, healed_args, "No automatic healing heuristic matched error signature."


class FindingKnowledgeGraph:
    """Maintains a graph of findings, code elements, and vulnerabilities to detect attack chains"""

    def __init__(self):
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[tuple[str, str, str]] = []  # (source_id, target_id, relation)

    def add_finding(self, finding_id: str, title: str, category: str, details: str) -> None:
        self.nodes[finding_id] = {
            "title": title,
            "category": category,
            "details": details
        }

    def link_findings(self, source_id: str, target_id: str, relation: str) -> None:
        if source_id in self.nodes and target_id in self.nodes:
            self.edges.append((source_id, target_id, relation))
            logger.info(f"Knowledge Graph: Linked {source_id} -> {target_id} [{relation}]")

    def get_related_findings(self, finding_id: str) -> list[dict[str, Any]]:
        related = []
        for src, tgt, rel in self.edges:
            if src == finding_id and tgt in self.nodes:
                related.append({"target": self.nodes[tgt], "relation": rel})
            elif tgt == finding_id and src in self.nodes:
                related.append({"source": self.nodes[src], "relation": rel})
        return related


class AdaptiveContextPruner:
    """Prioritizes and prunes context items based on semantic relevance to current task"""

    @staticmethod
    def prune_context(task_description: str, items: list[dict[str, Any]], max_items: int = 5) -> list[dict[str, Any]]:
        """Score items by keyword overlap with task description and return top relevant items"""
        task_keywords = set(re.findall(r'\w+', task_description.lower()))
        
        scored_items = []
        for item in items:
            text = str(item.get("content", "")) + " " + str(item.get("title", ""))
            item_words = set(re.findall(r'\w+', text.lower()))
            overlap = len(task_keywords.intersection(item_words))
            scored_items.append((overlap, item))

        # Sort descending by relevance score
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_items[:max_items]]


class ConsensusVotingEngine:
    """Aggregates multi-model opinions and calculates weighted consensus on findings"""

    @staticmethod
    def calculate_consensus(model_responses: list[dict[str, Any]]) -> dict[str, Any]:
        """
        model_responses format: [{"model": "...", "verdict": "vulnerable/safe", "confidence": 0.9, "reasoning": "..."}]
        """
        if not model_responses:
            return {"consensus": "inconclusive", "confidence": 0.0, "votes": 0}

        verdict_counts = {}
        total_confidence = 0.0

        for resp in model_responses:
            verdict = resp.get("verdict", "unknown").lower()
            conf = float(resp.get("confidence", 0.5))
            verdict_counts[verdict] = verdict_counts.get(verdict, 0) + conf
            total_confidence += conf

        best_verdict = max(verdict_counts, key=verdict_counts.get)
        confidence_score = verdict_counts[best_verdict] / len(model_responses)

        return {
            "consensus": best_verdict,
            "confidence": round(confidence_score, 2),
            "total_votes": len(model_responses),
            "verdict_distribution": verdict_counts
        }
