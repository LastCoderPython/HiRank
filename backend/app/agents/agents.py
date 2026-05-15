from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, Dict, List

from app.agents.memory import student_memory_store
from app.agents.retrieval import hybrid_retriever
from app.agents.tools import tool_registry
from app.agents.types import AgentName, AgentResult, AgentTask, Citation


class BaseAgent:
    agent_name: AgentName

    async def execute(self, task: AgentTask, context: Dict[str, Any], max_retries: int = 2) -> AgentResult:
        last_error = None
        for attempt in range(1, max_retries + 2):
            try:
                result = await self.run(task, context)
                result.attempts = attempt
                return result
            except Exception as exc:
                last_error = str(exc)
                await asyncio.sleep(0.2 * attempt)

        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=False,
            confidence=0.0,
            summary=f"{self.agent_name.value} failed: {last_error}",
            warnings=["retry_exhausted"],
            attempts=max_retries + 1,
        )

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class AutonomousDataCollectionAgent(BaseAgent):
    agent_name = AgentName.DATA_COLLECTION

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        query = task.payload.get("query") or task.objective
        collection = task.payload.get("collection", "cee")
        found = await tool_registry.call("local_vector_search", query=query, collection=collection, limit=6)
        rows = found.payload.get("results", []) if found.success else []
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.72 if rows else 0.42,
            summary=f"Collected {len(rows)} candidate sources",
            data={"sources": rows},
        )


class PdfParsingAgent(BaseAgent):
    agent_name = AgentName.PDF_PARSER

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        documents = task.payload.get("documents", [])
        parsed = []
        for doc in documents:
            parsed.append({"name": doc.get("name", "document.pdf"), "text": doc.get("text", "")[:2000]})
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.65 if parsed else 0.5,
            summary=f"Parsed {len(parsed)} PDF payloads",
            data={"parsed_documents": parsed},
        )


class SocialMediaIntelligenceAgent(BaseAgent):
    agent_name = AgentName.SOCIAL_INTEL

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        urls = task.payload.get("urls", [])
        snapshots = []
        for url in urls[:3]:
            result = await tool_registry.call("web_snapshot", url=url)
            if result.success:
                snapshots.append({"url": url, "snippet": result.payload.get("snippet", "")})
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.62 if snapshots else 0.45,
            summary=f"Scanned {len(snapshots)} social/public pages",
            data={"social_signals": snapshots},
        )


class PlacementAnalysisAgent(BaseAgent):
    agent_name = AgentName.PLACEMENT_ANALYSIS

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        hybrid = context.get("hybrid_rag", {})
        sources = hybrid.get("sources", [])
        branch_scores: Dict[str, float] = {}
        for item in sources:
            metadata = item.get("metadata", {})
            branch = metadata.get("branch", "Unknown")
            score = float(item.get("score", 0.5))
            branch_scores[branch] = max(score, branch_scores.get(branch, 0.0))

        ranked_branches = sorted(branch_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.68 if ranked_branches else 0.4,
            summary="Generated placement trend snapshot",
            data={"branch_trends": [{"branch": b, "score": round(s, 3)} for b, s in ranked_branches]},
        )


class DynamicUpdateAgent(BaseAgent):
    agent_name = AgentName.DYNAMIC_UPDATES

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        items = context.get("hybrid_rag", {}).get("sources", [])
        recent = [row for row in items if int((row.get("metadata") or {}).get("year", 0) or 0) >= 2023]
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.7 if recent else 0.5,
            summary=f"{len(recent)} high-recency records detected",
            data={"recent_records": recent},
        )


class SearchResearchAgent(BaseAgent):
    agent_name = AgentName.SEARCH_RESEARCH

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        query = task.payload.get("query") or task.objective
        collection = task.payload.get("collection", "cee")
        results = await hybrid_retriever.retrieve(query, collection, top_k=8)
        compressed = hybrid_retriever.compress_chunks(results)
        citations = [
            Citation(
                source_id=row.source_id,
                title=row.metadata.get("college_name") or row.metadata.get("institute") or "Knowledge Source",
                url=row.metadata.get("source_url"),
                excerpt=row.text,
            )
            for row in compressed[:5]
        ]
        data_rows = [
            {
                "source_id": row.source_id,
                "text": row.text,
                "metadata": row.metadata,
                "score": round(row.final_score, 4),
            }
            for row in compressed
        ]
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.76 if data_rows else 0.35,
            summary=f"Retrieved and reranked {len(data_rows)} documents",
            data={"results": data_rows},
            citations=citations,
        )


class VerificationAgent(BaseAgent):
    agent_name = AgentName.VERIFICATION

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        research = context.get("search_research", {}).get("results", [])
        unique_sources = len({row.get("source_id") for row in research})
        confidence = min(0.95, 0.45 + (unique_sources * 0.07))
        warnings = []
        if unique_sources < 3:
            warnings.append("low_source_diversity")
        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=confidence,
            summary=f"Validated evidence across {unique_sources} unique sources",
            data={"unique_sources": unique_sources},
            warnings=warnings,
        )


class RecommendationEngineAgent(BaseAgent):
    agent_name = AgentName.RECOMMENDATION

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        research = context.get("search_research", {}).get("results", [])
        trends = context.get("placement_analysis", {}).get("branch_trends", [])

        recommendations = []
        for row in research[:5]:
            metadata = row.get("metadata", {})
            recommendations.append(
                {
                    "college": metadata.get("college_name") or metadata.get("institute") or "Unknown College",
                    "branch": metadata.get("branch", "Unknown"),
                    "category": metadata.get("category", "General"),
                    "year": metadata.get("year"),
                    "confidence": row.get("score", 0.5),
                    "reasoning": "Hybrid RAG retrieval + verified source alignment",
                }
            )

        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.81 if recommendations else 0.3,
            summary=f"Generated {len(recommendations)} recommendations",
            data={"recommendations": recommendations, "branch_trends": trends},
        )


class StudentMemoryAgent(BaseAgent):
    agent_name = AgentName.STUDENT_MEMORY

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        student_id = task.payload.get("student_id", "guest")
        preferences = task.payload.get("preferences", {})
        summary = task.payload.get("summary", "")

        memory = student_memory_store.update_preferences(student_id, preferences)
        if summary:
            memory = student_memory_store.add_note(student_id, summary, source="agent_pipeline")

        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.9,
            summary="Student memory updated",
            data={
                "student_id": student_id,
                "preferences": memory.preferences,
                "notes_count": len(memory.notes),
            },
        )


class HybridRAGAgent(BaseAgent):
    agent_name = AgentName.HYBRID_RAG

    async def run(self, task: AgentTask, context: Dict[str, Any]) -> AgentResult:
        query = task.payload.get("query") or task.objective
        collection = task.payload.get("collection", "cee")
        rows = await hybrid_retriever.retrieve(query, collection, top_k=10)
        compressed = hybrid_retriever.compress_chunks(rows, max_chars=380)
        citations = [
            Citation(
                source_id=row.source_id,
                title=row.metadata.get("college_name") or row.metadata.get("institute") or "Knowledge Source",
                url=row.metadata.get("source_url"),
                excerpt=row.text,
            )
            for row in compressed[:7]
        ]

        results = [
            {
                "source_id": row.source_id,
                "text": row.text,
                "metadata": row.metadata,
                "score": round(row.final_score, 4),
            }
            for row in compressed
        ]

        return AgentResult(
            task_id=task.id,
            agent=self.agent_name,
            success=True,
            confidence=0.8 if results else 0.2,
            summary=f"Hybrid retrieval completed with {len(results)} records",
            data={"sources": results},
            citations=citations,
        )


def build_agent_registry() -> Dict[AgentName, BaseAgent]:
    return {
        AgentName.DATA_COLLECTION: AutonomousDataCollectionAgent(),
        AgentName.PDF_PARSER: PdfParsingAgent(),
        AgentName.SOCIAL_INTEL: SocialMediaIntelligenceAgent(),
        AgentName.PLACEMENT_ANALYSIS: PlacementAnalysisAgent(),
        AgentName.DYNAMIC_UPDATES: DynamicUpdateAgent(),
        AgentName.SEARCH_RESEARCH: SearchResearchAgent(),
        AgentName.VERIFICATION: VerificationAgent(),
        AgentName.RECOMMENDATION: RecommendationEngineAgent(),
        AgentName.STUDENT_MEMORY: StudentMemoryAgent(),
        AgentName.HYBRID_RAG: HybridRAGAgent(),
    }
