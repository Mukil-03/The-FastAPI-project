from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional


class ToolRegistry:
    """Simple registry to look up callable tools by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def list_tools(self) -> List[str]:
        return sorted(self._tools.keys())


@dataclass
class NodeResult:
    state: Dict[str, Any]
    next_node: Optional[str] = None
    log: Optional[str] = None


NodeCallable = Callable[[Dict[str, Any], ToolRegistry], Awaitable[NodeResult] | NodeResult]


@dataclass
class GraphDefinition:
    graph_id: str
    nodes: Dict[str, NodeCallable]
    edges: Dict[str, List[str]]
    start_node: str
    description: Optional[str] = None


@dataclass
class GraphRunRecord:
    run_id: str
    graph_id: str
    current_state: Dict[str, Any]
    status: str
    logs: List[Dict[str, Any]] = field(default_factory=list)
    current_node: Optional[str] = None
    error: Optional[str] = None


class GraphEngine:
    """In-memory graph storage and executor."""

    def __init__(self, node_library: Dict[str, NodeCallable], tool_registry: ToolRegistry):
        self._graphs: Dict[str, GraphDefinition] = {}
        self._runs: Dict[str, GraphRunRecord] = {}
        self._lock = asyncio.Lock()
        self._node_library = node_library
        self._tool_registry = tool_registry

    async def register_graph(
        self, nodes: List[str], edges: Dict[str, List[str]], start_node: str, description: Optional[str] = None
    ) -> str:
        async with self._lock:
            graph_id = str(uuid.uuid4())
            node_map = {}
            for name in nodes:
                if name not in self._node_library:
                    raise ValueError(f"Unknown node '{name}'. Available: {sorted(self._node_library.keys())}")
                node_map[name] = self._node_library[name]
            if start_node not in node_map:
                raise ValueError(f"Start node '{start_node}' must be in nodes list")
            normalized_edges = {k: (v if isinstance(v, list) else [v]) for k, v in edges.items()}
            self._graphs[graph_id] = GraphDefinition(
                graph_id=graph_id,
                nodes=node_map,
                edges=normalized_edges,
                start_node=start_node,
                description=description,
            )
            return graph_id

    async def run_graph(self, graph_id: str, initial_state: Dict[str, Any]) -> GraphRunRecord:
        async with self._lock:
            if graph_id not in self._graphs:
                raise KeyError(f"Graph '{graph_id}' not found")
            run_id = str(uuid.uuid4())
            run = GraphRunRecord(
                run_id=run_id, graph_id=graph_id, current_state=dict(initial_state), status="running", current_node=None
            )
            self._runs[run_id] = run

        try:
            final_state, logs = await self._execute(self._graphs[graph_id], initial_state)
            async with self._lock:
                run.status = "completed"
                run.current_state = final_state
                run.logs = logs
                run.current_node = None
            return run
        except Exception as exc:  # pylint: disable=broad-except
            async with self._lock:
                run.status = "failed"
                run.error = str(exc)
            raise

    async def _execute(self, graph: GraphDefinition, state: Dict[str, Any]) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        logs: List[Dict[str, Any]] = []
        current_node = graph.start_node
        current_state = dict(state)

        while current_node:
            node_fn = graph.nodes[current_node]
            result = await self._run_node(node_fn, current_state)

            log_entry = {
                "node": current_node,
                "log": result.log,
                "state_snapshot": result.state,
            }
            logs.append(log_entry)

            current_state = result.state
            if result.next_node is not None:
                current_node = result.next_node
                continue

            next_candidates = graph.edges.get(current_node, [])
            if len(next_candidates) > 1:
                raise ValueError(f"Node '{current_node}' has multiple edges but no next_node provided by the node logic")
            current_node = next_candidates[0] if next_candidates else None

        return current_state, logs

    async def _run_node(self, fn: NodeCallable, state: Dict[str, Any]) -> NodeResult:
        result = fn(state, self._tool_registry)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, NodeResult):
            return result
        if isinstance(result, dict):
            return NodeResult(state=result)
        raise TypeError("Node must return NodeResult or dict")

    async def get_run(self, run_id: str) -> GraphRunRecord:
        async with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Run '{run_id}' not found")
            return self._runs[run_id]

    def list_graphs(self) -> List[str]:
        return list(self._graphs.keys())

    def list_nodes(self) -> List[str]:
        return sorted(self._node_library.keys())

    def describe_graphs(self) -> List[Dict[str, Any]]:
        return [
            {
                "graph_id": g.graph_id,
                "nodes": list(g.nodes.keys()),
                "start_node": g.start_node,
                "description": g.description,
            }
            for g in self._graphs.values()
        ]

