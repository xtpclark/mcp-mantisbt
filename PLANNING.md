# mcp-mantisbt — Planning

## Why

MantisBT is the only major issue tracker without an MCP server. Jira, Linear, GitHub Issues
all have them. MantisBT is widely deployed in enterprises (manufacturing, defense, telco) that
are also heavy database users — exactly the Assay customer profile.

The primary driver: Assay needs to pull resolution history from MantisBT at AI analysis time.
But this is a standalone, publishable MCP server useful to anyone running MantisBT.

## MantisBT REST API

Base: `{url}/api/rest/index.php/`
Auth: Raw API token in `Authorization` header — **no "Bearer" prefix** (MantisBT quirk)
Token length: exactly 32 chars (validated server-side by strlen check)

Key endpoints:
```
GET  /projects/                    → list projects
GET  /projects/{id}                → project detail + categories
GET  /issues/                      → list/search issues
GET  /issues/{id}                  → single issue
POST /issues/                      → create issue
PATCH /issues/{id}                 → update issue
POST /issues/{id}/notes/           → add note
GET  /issues/?project_id=1&status_id=90&summary=bloat  → search
```

Status IDs: 10=new, 20=feedback, 30=acknowledged, 40=confirmed, 50=assigned, 80=resolved, 90=closed
Severity: trivial, minor, major, crash, block
Priority: low, normal, high, urgent, immediate

## MCP Tools

### `create_issue`
```python
create_issue(
    project_id: int,
    summary: str,
    description: str,
    severity: str = "major",      # trivial|minor|major|crash|block
    priority: str = "normal",     # low|normal|high|urgent|immediate
    category: str = "General",
    tags: list[str] = []
) -> {"issue_id": int, "url": str}
```

### `get_issue`
```python
get_issue(issue_id: int) -> Issue
```

### `search_issues`
```python
search_issues(
    query: str,                   # full-text search on summary + description + notes
    project_id: int = None,
    status: str = None,           # "new"|"resolved"|"closed"|"all"
    category: str = None,
    limit: int = 10
) -> list[Issue]
```

**This is the key tool for Assay resolution lookup.** Returns structured results
formatted for AI prompt injection.

### `add_note`
```python
add_note(
    issue_id: int,
    text: str,
    private: bool = False
) -> {"note_id": int}
```

### `resolve_issue`
```python
resolve_issue(
    issue_id: int,
    resolution_note: str,
    resolution: str = "fixed"    # fixed|wontfix|duplicate|nochange|suspended|notabug
) -> {"issue_id": int, "status": str}
```

### `list_projects`
```python
list_projects() -> list[{"id": int, "name": str, "description": str}]
```

## MCP Resources

```
mantisbt://issues/{id}     → get_issue(id)
mantisbt://projects        → list_projects()
```

## Implementation Plan

### Phase 1 — Core server (this week)
- [ ] Project scaffold: `pyproject.toml`, `src/mcp_mantisbt/`
- [ ] MantisBT REST client (`client.py`) — thin wrapper, handles auth quirk
- [ ] MCP server (`server.py`) — tools + resources via `mcp` SDK
- [ ] `search_issues` — the most important tool, implement first
- [ ] `create_issue`, `get_issue`, `add_note`, `resolve_issue`, `list_projects`
- [ ] Config via env vars: `MANTISBT_URL`, `MANTISBT_API_TOKEN`
- [ ] Basic tests against real MantisBT instance

### Phase 2 — Assay integration
- [ ] `similar_incidents` prompt context in Assay's `prompt_generator.py`
- [ ] MCP connector called at analysis time with finding text → search_issues
- [ ] Results injected into AI prompt alongside `similar_findings` (pgvector RAG)

### Phase 3 — Polish + publish
- [ ] PyPI package: `mcp-mantisbt`
- [ ] MCP server registry submission
- [ ] Smithery.ai listing
- [ ] Error handling, rate limiting, connection pooling
- [ ] Claude Desktop config example

## Tech Stack

- Python 3.11+
- `mcp` SDK (Anthropic's official Python SDK for MCP servers)
- `httpx` — async HTTP client (MantisBT REST)
- `pydantic` — data models for Issue, Project, etc.

## MantisBT Instance for Testing

- URL: http://52.205.47.28:8989
- Token: oi_ru7VSUnECk16H_CTtt9nsnXt0t31X
- Project: 1 (Assay POC)
- Note: token goes raw in Authorization header, no Bearer prefix

## File Layout

```
mcp-mantisbt/
├── README.md
├── PLANNING.md
├── pyproject.toml
├── src/
│   └── mcp_mantisbt/
│       ├── __init__.py
│       ├── server.py       ← MCP server, tools, resources
│       ├── client.py       ← MantisBT REST API client
│       └── models.py       ← Pydantic models: Issue, Project, Note
└── tests/
    └── test_client.py
```

## Open Questions

1. **`search_issues` implementation** — MantisBT's REST search is filter-based, not
   full-text. May need to combine multiple filter params or fall back to fetching
   recent resolved issues and filtering client-side. Worth testing the API first.

2. **Async vs sync** — MCP SDK supports both. Given this will be called from Assay's
   Flask app (sync), start sync. Can add async later.

3. **Rate limiting** — MantisBT doesn't document rate limits. Watch for 429s.
   Add exponential backoff if needed.

4. **MCP registry submission** — check current submission process at
   https://github.com/modelcontextprotocol/servers
