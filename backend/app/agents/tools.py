from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict

import httpx

from app.core.chroma_client import chroma_client


@dataclass
class ToolResult:
    success: bool
    payload: Dict[str, Any]


class BaseTool:
    name: str = "base"

    async def run(self, **kwargs) -> ToolResult:
        raise NotImplementedError


class LocalVectorSearchTool(BaseTool):
    name = "local_vector_search"

    async def run(self, **kwargs) -> ToolResult:
        query = kwargs.get("query", "")
        collection = kwargs.get("collection", "cee")
        limit = int(kwargs.get("limit", 5))
        if not query:
            return ToolResult(success=False, payload={"error": "Missing query"})

        rows = await asyncio.to_thread(chroma_client.search_similar, query, collection, limit, None)
        return ToolResult(success=True, payload={"results": rows})


class WebSnapshotTool(BaseTool):
    name = "web_snapshot"

    async def run(self, **kwargs) -> ToolResult:
        url = kwargs.get("url")
        if not url:
            return ToolResult(success=False, payload={"error": "Missing url"})

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
            text = response.text[:1500]
            return ToolResult(success=True, payload={"status": response.status_code, "snippet": text})
        except Exception as exc:
            return ToolResult(success=False, payload={"error": str(exc)})


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {
            LocalVectorSearchTool.name: LocalVectorSearchTool(),
            WebSnapshotTool.name: WebSnapshotTool(),
        }

    async def call(self, tool_name: str, **kwargs) -> ToolResult:
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, payload={"error": f"Unknown tool: {tool_name}"})
        return await tool.run(**kwargs)


tool_registry = ToolRegistry()
