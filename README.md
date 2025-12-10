## Minimal Workflow / Graph Engine

Small FastAPI service that runs simple workflow graphs (nodes + shared state) with branching and looping. Includes a sample Code Review mini-agent workflow.

### Requirements
- Python 3.10+
- `pip install -r requirements.txt`

### Run
```bash
uvicorn app.main:app --reload --port 8000
```

### API
- `POST /graph/create` — create a graph using node names from the library and edge mapping.
- `POST /graph/run` — run a graph by `graph_id` with an initial state.
- `GET /graph/state/{run_id}` — inspect a run.
- `GET /graph/nodes` — list available nodes and tools.
- `GET /graph/list` — see available graphs (use this to fetch the default graph id).

A default code-review workflow is auto-created on startup.

### Sample Request
```json
POST /graph/run
{
  "graph_id": "<graph-id-from-/graph/list>",
  "initial_state": {
    "code": "def foo():\n    pass",
    "quality_threshold": 0.7,
    "max_iterations": 3
  }
}
```

### What the Engine Supports
- Nodes are Python callables reading/modifying shared state.
- Edges define default transitions; nodes can override `next_node` for branching/loops.
- Simple tool registry; nodes can call tools by name.
- In-memory graph and run storage.

### If I Had More Time
- Persist graphs/runs to a database.
- Add WebSocket log streaming.
- Pluggable node/tool registration via API.
- Richer edge conditions and concurrency controls.

