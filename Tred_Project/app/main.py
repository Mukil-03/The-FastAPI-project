from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.engine.core import GraphEngine, ToolRegistry
from app.workflows.code_review import NODE_LIBRARY


def detect_smells_tool(code: str) -> Dict[str, Any]:
    """Tiny heuristic smell detector."""
    long_lines = [line for line in code.splitlines() if len(line) > 120]
    todo_comments = [line for line in code.splitlines() if "TODO" in line]
    return {"issues": len(long_lines) + len(todo_comments), "long_lines": len(long_lines), "todos": len(todo_comments)}


class GraphCreateRequest(BaseModel):
    nodes: List[str] = Field(..., description="Names of nodes to include, must exist in the node library")
    edges: Dict[str, Union[str, List[str]]] = Field(
        ..., description="Mapping of node -> next node(s). For branching, nodes decide via `next_node`."
    )
    start_node: str
    description: Optional[str] = None


class GraphCreateResponse(BaseModel):
    graph_id: str


class GraphRunRequest(BaseModel):
    graph_id: str
    initial_state: Dict[str, Any] = Field(default_factory=dict)


class GraphRunResponse(BaseModel):
    run_id: str
    final_state: Dict[str, Any]
    logs: List[Dict[str, Any]]


class GraphStateResponse(BaseModel):
    run_id: str
    status: str
    current_state: Dict[str, Any]
    logs: List[Dict[str, Any]]
    current_node: Optional[str] = None
    error: Optional[str] = None


tool_registry = ToolRegistry()
tool_registry.register("detect_smells", detect_smells_tool)

engine = GraphEngine(node_library=NODE_LIBRARY, tool_registry=tool_registry)
app = FastAPI(title="Minimal Workflow Engine", version="0.1.0")


async def _ensure_default_graph() -> str:
    if engine.list_graphs():
        return engine.list_graphs()[0]
    nodes = list(NODE_LIBRARY.keys())
    edges = {
        "extract_functions": ["check_complexity"],
        "check_complexity": ["detect_issues"],
        "detect_issues": ["suggest_improvements"],
        "suggest_improvements": ["check_quality"],
        "check_quality": [],
    }
    return await engine.register_graph(nodes=nodes, edges=edges, start_node="extract_functions", description="Code review loop")


@app.on_event("startup")
async def startup_event() -> None:
    await _ensure_default_graph()


@app.post("/graph/create", response_model=GraphCreateResponse)
async def create_graph(request: GraphCreateRequest) -> GraphCreateResponse:
    try:
        graph_id = await engine.register_graph(
            nodes=request.nodes, edges={k: v if isinstance(v, list) else [v] for k, v in request.edges.items()}, start_node=request.start_node, description=request.description
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GraphCreateResponse(graph_id=graph_id)


@app.post("/graph/run", response_model=GraphRunResponse)
async def run_graph(request: GraphRunRequest) -> GraphRunResponse:
    try:
        run = await engine.run_graph(graph_id=request.graph_id, initial_state=request.initial_state)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pylint: disable=broad-except
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return GraphRunResponse(run_id=run.run_id, final_state=run.current_state, logs=run.logs)


@app.get("/graph/state/{run_id}", response_model=GraphStateResponse)
async def get_state(run_id: str) -> GraphStateResponse:
    try:
        run = await engine.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GraphStateResponse(
        run_id=run.run_id,
        status=run.status,
        current_state=run.current_state,
        logs=run.logs,
        current_node=run.current_node,
        error=run.error,
    )


@app.get("/graph/nodes")
async def list_nodes() -> Dict[str, Any]:
    return {"available_nodes": engine.list_nodes(), "tools": tool_registry.list_tools()}


@app.get("/graph/list")
async def list_graphs() -> Dict[str, Any]:
    return {"graphs": engine.describe_graphs()}

