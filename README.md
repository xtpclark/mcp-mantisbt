# mcp-mantisbt

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for [MantisBT](https://mantisbt.org) — the open source bug tracker.

Built in Python for automated AI analysis pipelines. Most MantisBT MCP servers are editor integrations — tools that let Claude or Cursor read your bug tracker while you code. This one is designed for a different job: autonomous systems that create tickets from diagnostic runs, and AI analysts that query resolution history to inform the next investigation.

## What it does

- **Create issues** — push findings, alerts, or incidents from automated pipelines into MantisBT
- **Search issues** — find similar resolved issues and inject them as context into AI analysis prompts
- **Update issues** — add notes, change status, attach resolution details
- **Resolve issues** — mark issues resolved with structured resolution notes, capturing *how* an issue was fixed, not just that it was closed
- **List projects** — discover available projects and categories

## Why this exists

MantisBT is widely deployed in enterprises — particularly in manufacturing, defense, and telco — and it holds institutional memory: years of resolved tickets, root cause notes, and fix documentation.

This server makes that memory available to AI pipelines. The core pattern:

**Push:** An automated system (health check, monitoring agent, CI pipeline) detects a problem and creates a MantisBT issue — findings, severity, and context captured without manual triage.

**Pull:** When a similar pattern appears later, the pipeline calls `search_issues(query, status="resolved")` to find how your team fixed it before. Those results are injected directly into the AI's prompt as context. The analyst sees: *"Here are 2 similar issues your team resolved before, and how they fixed them."*

Over time, your issue tracker becomes a searchable record of institutional knowledge — and any AI analyst with access to this server can draw on it.

This server is for you if you're building automated Python systems that need to interact with MantisBT as a system of record, not just as a UI to browse.

**Why Python:** The existing MantisBT MCP servers are TypeScript/Node. Python means no glue code when your pipeline is already Python, and straightforward extension when you need something specific.

## Requirements

- Python 3.10+
- MantisBT 2.23+ (REST API must be enabled)
- An API token (create under My Account → API Tokens in MantisBT)

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

Add the following to your MCP client's configuration file (e.g., `claude_desktop_config.json` or `mcp.json`):

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

## The `search_issues` tool — resolution history for AI context

The key tool for AI pipelines. Search resolved issues by keyword and inject the results directly into your prompt as `similar_incidents` context:

```python
search_issues(
    query="autovacuum bloat vacuum freeze",  # text search
    project_id=1,                           # optional filter
    status="resolved",                      # find resolved issues
    category="postgresql",                  # optional tech filter
    limit=5
)
```

Returns structured results including summary, description, resolution notes, and tags — ready for injection into an AI analysis prompt.

## Architecture

Two flows, both mediated by the MCP server:

**Push — capturing findings:**
```
Automated pipeline (monitoring, CI, health check, etc.)
    → create_issue / add_note / resolve_issue
    → mcp-mantisbt
    → MantisBT
```

**Pull — querying resolution history:**
```
AI analysis pipeline
    → search_issues(query, status="resolved")
    → mcp-mantisbt
    → MantisBT REST API
    → similar_incidents injected into AI prompt
```

## Status

🚧 **Active development** — first release coming soon.

## License

MIT
