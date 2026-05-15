from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import asdict
from typing import Any, Dict, List

from app.agents.agents import build_agent_registry
from app.agents.types import AgentName, AgentResult, AgentTask


logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self):
        self.registry = build_agent_registry()

    def catalog(self) -> List[Dict[str, str]]:
        return [{"agent": name.value, "description": self._description(name)} for name in AgentName]

    def _description(self, agent_name: AgentName) -> str:
        descriptions = {
            AgentName.DATA_COLLECTION: "Autonomous data collection from indexed and external sources",
            AgentName.PDF_PARSER: "Parses PDF payloads into analyzable chunks",
            AgentName.SOCIAL_INTEL: "Collects social/public intelligence snapshots",
            AgentName.PLACEMENT_ANALYSIS: "Analyzes placement trends and branch outcomes",
            AgentName.DYNAMIC_UPDATES: "Tracks recency and dynamic source freshness",
            AgentName.SEARCH_RESEARCH: "Runs hybrid semantic+keyword research",
            AgentName.VERIFICATION: "Validates evidence quality and confidence",
            AgentName.RECOMMENDATION: "Builds final counseling recommendations",
            AgentName.STUDENT_MEMORY: "Maintains long-lived student context and preferences",
            AgentName.HYBRID_RAG: "Metadata-aware hybrid retrieval with compression and citations",
        }
        return descriptions.get(agent_name, "")

    def build_plan(self, goal: str, collection: str, student_id: str) -> List[AgentTask]:
        goal_lower = goal.lower()
        needs_social = any(token in goal_lower for token in ["social", "reddit", "linkedin", "x.com"])
        needs_pdf = any(token in goal_lower for token in ["pdf", "brochure", "prospectus"])

        tasks: List[AgentTask] = [
            AgentTask(
                id="task_hybrid_rag",
                agent=AgentName.HYBRID_RAG,
                objective="Run metadata-aware hybrid retrieval",
                payload={"query": goal, "collection": collection},
            ),
            AgentTask(
                id="task_data_collect",
                agent=AgentName.DATA_COLLECTION,
                objective="Collect supporting sources",
                payload={"query": goal, "collection": collection},
                depends_on=["task_hybrid_rag"],
            ),
            AgentTask(
                id="task_research",
                agent=AgentName.SEARCH_RESEARCH,
                objective="Execute search and research",
                payload={"query": goal, "collection": collection},
                depends_on=["task_data_collect"],
            ),
            AgentTask(
                id="task_placement",
                agent=AgentName.PLACEMENT_ANALYSIS,
                objective="Placement analysis and branch insight",
                depends_on=["task_research"],
            ),
            AgentTask(
                id="task_updates",
                agent=AgentName.DYNAMIC_UPDATES,
                objective="Dynamic updates and recency checks",
                depends_on=["task_research"],
            ),
            AgentTask(
                id="task_verify",
                agent=AgentName.VERIFICATION,
                objective="Validate sources and confidence",
                depends_on=["task_research", "task_updates"],
            ),
            AgentTask(
                id="task_recommend",
                agent=AgentName.RECOMMENDATION,
                objective="Produce recommendations",
                depends_on=["task_placement", "task_verify"],
            ),
            AgentTask(
                id="task_memory",
                agent=AgentName.STUDENT_MEMORY,
                objective="Persist student memory",
                payload={"student_id": student_id},
                depends_on=["task_recommend"],
            ),
        ]

        if needs_pdf:
            tasks.insert(
                2,
                AgentTask(
                    id="task_pdf",
                    agent=AgentName.PDF_PARSER,
                    objective="Parse PDF sources",
                    payload={"documents": []},
                    depends_on=["task_data_collect"],
                ),
            )
        if needs_social:
            tasks.insert(
                3,
                AgentTask(
                    id="task_social",
                    agent=AgentName.SOCIAL_INTEL,
                    objective="Collect social signals",
                    payload={"urls": []},
                    depends_on=["task_data_collect"],
                ),
            )

        return tasks

    async def execute_plan(self, tasks: List[AgentTask], initial_context: Dict[str, Any]) -> Dict[str, Any]:
        context = dict(initial_context)
        completed: Dict[str, AgentResult] = {}

        pending = {task.id: task for task in tasks}
        while pending:
            ready = [task for task in pending.values() if all(dep in completed for dep in task.depends_on)]
            if not ready:
                raise RuntimeError("Task graph has unresolved dependencies")

            for task in ready:
                logger.info("Executing agent task=%s agent=%s", task.id, task.agent.value)
                agent = self.registry[task.agent]
                result = await agent.execute(task, context)
                completed[task.id] = result
                context[task.agent.value] = result.data
                pending.pop(task.id, None)

        citations = []
        for result in completed.values():
            citations.extend(
                {
                    "source_id": c.source_id,
                    "title": c.title,
                    "url": c.url,
                    "excerpt": c.excerpt,
                }
                for c in result.citations
            )

        verification = next(
            (r for r in completed.values() if r.agent == AgentName.VERIFICATION),
            None,
        )
        overall_confidence = verification.confidence if verification else 0.65

        recommendations = context.get(AgentName.RECOMMENDATION.value, {}).get("recommendations", [])
        return {
            "tasks": [
                {
                    "task_id": result.task_id,
                    "agent": result.agent.value,
                    "success": result.success,
                    "confidence": round(result.confidence, 4),
                    "summary": result.summary,
                    "attempts": result.attempts,
                    "warnings": result.warnings,
                }
                for result in completed.values()
            ],
            "recommendations": recommendations,
            "citations": citations,
            "overall_confidence": round(overall_confidence, 4),
            "context": context,
        }


agent_orchestrator = AgentOrchestrator()
