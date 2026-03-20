# mcp-mantisbt

The first [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [MantisBT](https://mantisbt.org) — the open source bug tracker.

Gives AI assistants (Claude, Cursor, etc.) read/write access to MantisBT issues, projects, and resolution history. Designed as a companion to [Assay](https://assayhq.ai) — the database health check platform — where it powers resolution history lookups during AI-assisted incident analysis.

## What it does

- **Create issues** — push findings, alerts, or incidents into MantisBT
- **Search issues** — find similar resolved issues to inform current investigation
- **Update issues** — add notes, change status, attach resolution details
- **List projects** — discover available projects and categories

## Why this exists

MantisBT is widely deployed in enterprises — particularly in manufacturing, defense, and telco — but had no MCP server. Every other major issue tracker (Jira, Linear, GitHub Issues) has one. This fills that gap.

The primary use case that drove it: [Assay](https://assayhq.ai) detects database health issues and creates MantisBT tickets. When a similar pattern appears later, the MCP server lets the AI analyst ask "how did we fix this before?" and get real answers from the issue history.

## Installation

```bash
pip install mcp-mantisbt
```

Or from source:

```bash
git clone https://github.com/xtpclark/mcp-mantisbt
cd mcp-mantisbt
pip install -e .
```

## Configuration

```json
{
  "mcpServers": {
    "mantisbt": {
      "command": "mcp-mantisbt",
      "env": {
        "MANTISBT_URL": "http://your-mantis-instance:8989",
        "MANTISBT_API_TOKEN": "your-32-char-token"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `create_issue` | Create a new issue in a project |
| `get_issue` | Fetch a single issue by ID |
| `search_issues` | Search issues by text, project, status, category |
| `add_note` | Add a note/comment to an existing issue |
| `resolve_issue` | Mark an issue resolved with a resolution note |
| `list_projects` | List available projects |
| `get_project` | Get project details including categories |

## Resources

| Resource | Description |
|----------|-------------|
| `mantisbt://issues/{id}` | Direct access to a specific issue |
| `mantisbt://projects` | All accessible projects |

## The `search_issues` tool — the key for AI resolution lookup

```python
search_issues(
    query="autovacuum bloat vacuum freeze",  # text search
    project_id=1,                           # optional filter
    status="resolved",                      # find resolved issues
    category="postgresql",                  # optional tech filter
    limit=5
)
```

Returns structured results including summary, description, resolution notes, and tags — formatted for direct injection into AI analysis prompts as `similar_incidents` context.

## Architecture

```
AI Assistant (Claude/Cursor)
    ↓ MCP protocol
mcp-mantisbt server
    ↓ HTTP REST
MantisBT instance
    ↓ PostgreSQL
mantisbt database
```

## Relationship to Assay

[Assay](https://assayhq.ai) uses this server in two directions:

**Push (destinations plugin):** After each healthcheck run, Assay creates MantisBT issues via `destinations/mantisbt.py` — one issue per `(company, technology)` run.

**Pull (MCP):** At AI analysis time, Assay calls `search_issues(query, status="resolved")` to find similar resolved issues, injects results as `similar_incidents` context into the AI prompt. The analyst sees: *"Here are 2 similar issues your team resolved before, and how they fixed them."*

## Status

🚧 **Active development** — first release coming soon.

## License

MIT
