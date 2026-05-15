from __future__ import annotations

import uuid
from typing import Dict

from fastapi import APIRouter, Depends

from app.agents.memory import student_memory_store
from app.agents.orchestrator import agent_orchestrator
from app.models.agent_models import (
    AgentExecuteRequest,
    AgentExecuteResponse,
    AgentPlanRequest,
    AgentPlanResponse,
    AgentTaskView,
    CitationView,
    MemoryNoteRequest,
    MemoryPreferencesRequest,
    MemoryResponse,
    RecommendationView,
    TaskExecutionView,
)
from app.security import require_agent_api_key


router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("/catalog")
async def get_agent_catalog():
    return {"agents": agent_orchestrator.catalog()}


@router.post("/plan", response_model=AgentPlanResponse, dependencies=[Depends(require_agent_api_key)])
async def plan_agent_workflow(request: AgentPlanRequest):
    plan_id = str(uuid.uuid4())
    tasks = agent_orchestrator.build_plan(
        goal=request.goal,
        collection=request.collection,
        student_id=request.student_profile.student_id,
    )
    return AgentPlanResponse(
        plan_id=plan_id,
        tasks=[
            AgentTaskView(task_id=t.id, agent=t.agent.value, objective=t.objective, depends_on=t.depends_on)
            for t in tasks
        ],
    )


@router.post("/execute", response_model=AgentExecuteResponse, dependencies=[Depends(require_agent_api_key)])
async def execute_agent_workflow(request: AgentExecuteRequest):
    tasks = agent_orchestrator.build_plan(
        goal=request.goal,
        collection=request.collection,
        student_id=request.student_profile.student_id,
    )

    initial_context: Dict = {
        "goal": request.goal,
        "student_profile": request.student_profile.model_dump(),
    }
    result = await agent_orchestrator.execute_plan(tasks, initial_context)

    return AgentExecuteResponse(
        overall_confidence=result["overall_confidence"],
        tasks=[TaskExecutionView(**task) for task in result["tasks"]],
        recommendations=[RecommendationView(**row) for row in result["recommendations"]],
        citations=[CitationView(**row) for row in result["citations"]],
    )


@router.get("/memory/{student_id}", response_model=MemoryResponse, dependencies=[Depends(require_agent_api_key)])
async def get_student_memory(student_id: str):
    memory = student_memory_store.get_or_create(student_id)
    return MemoryResponse(
        student_id=student_id,
        preferences=memory.preferences,
        notes=[{"note": n.note, "source": n.source, "created_at": n.created_at} for n in memory.notes],
        last_context=memory.last_context,
    )


@router.post("/memory/{student_id}/note", response_model=MemoryResponse, dependencies=[Depends(require_agent_api_key)])
async def add_memory_note(student_id: str, request: MemoryNoteRequest):
    memory = student_memory_store.add_note(student_id, request.note, request.source)
    return MemoryResponse(
        student_id=student_id,
        preferences=memory.preferences,
        notes=[{"note": n.note, "source": n.source, "created_at": n.created_at} for n in memory.notes],
        last_context=memory.last_context,
    )


@router.post("/memory/{student_id}/preferences", response_model=MemoryResponse, dependencies=[Depends(require_agent_api_key)])
async def update_memory_preferences(student_id: str, request: MemoryPreferencesRequest):
    memory = student_memory_store.update_preferences(student_id, request.preferences)
    return MemoryResponse(
        student_id=student_id,
        preferences=memory.preferences,
        notes=[{"note": n.note, "source": n.source, "created_at": n.created_at} for n in memory.notes],
        last_context=memory.last_context,
    )
