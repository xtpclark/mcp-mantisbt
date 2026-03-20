"""
mcp-mantisbt — MCP server for MantisBT bug tracker.

Tools:
    create_issue       — create a new issue
    get_issue          — fetch a single issue by ID
    search_issues      — search by text/status/project (key tool for resolution lookup)
    add_note           — add a comment/note to an issue
    resolve_issue      — mark resolved with a resolution note
    list_projects      — list available projects

Resources:
    mantisbt://issues/{id}   — single issue
    mantisbt://projects      — all projects

Config (env vars):
    MANTISBT_URL        — e.g. http://your-mantis:8989
    MANTISBT_API_TOKEN  — 32-char raw token (no Bearer prefix)
"""

import json
import logging
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from .client import MantisBTClient

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def get_client() -> MantisBTClient:
    url = os.environ.get('MANTISBT_URL')
    token = os.environ.get('MANTISBT_API_TOKEN')
    if not url or not token:
        raise ValueError(
            "MANTISBT_URL and MANTISBT_API_TOKEN environment variables are required"
        )
    return MantisBTClient(url=url, api_token=token)


server = Server("mcp-mantisbt")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="create_issue",
            description="Create a new issue in MantisBT",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id":  {"type": "integer", "description": "Project ID"},
                    "summary":     {"type": "string",  "description": "Issue summary/title"},
                    "description": {"type": "string",  "description": "Detailed description"},
                    "severity":    {"type": "string",  "description": "trivial|minor|major|crash|block", "default": "major"},
                    "priority":    {"type": "string",  "description": "low|normal|high|urgent|immediate", "default": "normal"},
                    "category":    {"type": "string",  "description": "Category name", "default": "General"},
                    "tags":        {"type": "array",   "items": {"type": "string"}, "description": "Tags to apply"},
                },
                "required": ["project_id", "summary", "description"],
            },
        ),
        types.Tool(
            name="get_issue",
            description="Fetch a single MantisBT issue by ID, including notes and resolution history",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "integer", "description": "Issue ID"},
                },
                "required": ["issue_id"],
            },
        ),
        types.Tool(
            name="search_issues",
            description=(
                "Search MantisBT issues by text, status, and project. "
                "Use status='resolved' to find similar past issues and how they were fixed. "
                "Returns issue summaries, descriptions, and resolution notes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query":      {"type": "string",  "description": "Text to search for in summary/description/notes"},
                    "project_id": {"type": "integer", "description": "Filter by project ID"},
                    "status":     {"type": "string",  "description": "new|resolved|closed|all (default: all)"},
                    "category":   {"type": "string",  "description": "Filter by category name"},
                    "limit":      {"type": "integer", "description": "Max results (default: 10)"},
                },
                "required": [],
            },
        ),
        types.Tool(
            name="add_note",
            description="Add a comment or note to an existing MantisBT issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id": {"type": "integer", "description": "Issue ID"},
                    "text":     {"type": "string",  "description": "Note text"},
                    "private":  {"type": "boolean", "description": "Make note private (default: false)"},
                },
                "required": ["issue_id", "text"],
            },
        ),
        types.Tool(
            name="resolve_issue",
            description="Mark a MantisBT issue as resolved with a resolution note",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_id":        {"type": "integer", "description": "Issue ID"},
                    "resolution_note": {"type": "string",  "description": "How the issue was resolved"},
                    "resolution":      {"type": "string",  "description": "fixed|wontfix|duplicate|nochange|suspended|notabug", "default": "fixed"},
                },
                "required": ["issue_id", "resolution_note"],
            },
        ),
        types.Tool(
            name="list_projects",
            description="List all accessible MantisBT projects",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    client = get_client()

    try:
        if name == "create_issue":
            issue = client.create_issue(
                project_id=arguments["project_id"],
                summary=arguments["summary"],
                description=arguments["description"],
                severity=arguments.get("severity", "major"),
                priority=arguments.get("priority", "normal"),
                category=arguments.get("category", "General"),
                tags=arguments.get("tags", []),
            )
            return [types.TextContent(
                type="text",
                text=f"Created issue #{issue.id}: {issue.summary}\nURL: {client.base_url.replace('/api/rest/index.php', '')}/view.php?id={issue.id}",
            )]

        elif name == "get_issue":
            issue = client.get_issue(arguments["issue_id"])
            return [types.TextContent(type="text", text=issue.to_context_str())]

        elif name == "search_issues":
            issues = client.search_issues(
                query=arguments.get("query"),
                project_id=arguments.get("project_id"),
                status=arguments.get("status"),
                category=arguments.get("category"),
                limit=arguments.get("limit", 10),
            )
            if not issues:
                return [types.TextContent(type="text", text="No matching issues found.")]
            parts = [f"Found {len(issues)} issue(s):\n"]
            for issue in issues:
                parts.append(issue.to_context_str())
                parts.append("---")
            return [types.TextContent(type="text", text="\n".join(parts))]

        elif name == "add_note":
            note = client.add_note(
                issue_id=arguments["issue_id"],
                text=arguments["text"],
                private=arguments.get("private", False),
            )
            note_id = note.get("id", "?") if isinstance(note, dict) else "?"
            return [types.TextContent(
                type="text",
                text=f"Note #{note_id} added to issue #{arguments['issue_id']}",
            )]

        elif name == "resolve_issue":
            issue = client.resolve_issue(
                issue_id=arguments["issue_id"],
                resolution_note=arguments["resolution_note"],
                resolution=arguments.get("resolution", "fixed"),
            )
            return [types.TextContent(
                type="text",
                text=f"Issue #{issue.id} resolved as '{arguments.get('resolution', 'fixed')}'",
            )]

        elif name == "list_projects":
            projects = client.list_projects()
            if not projects:
                return [types.TextContent(type="text", text="No projects found.")]
            lines = [f"#{p.id}: {p.name}" + (f" — {p.description}" if p.description else "")
                     for p in projects]
            return [types.TextContent(type="text", text="\n".join(lines))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {e}")]


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="mantisbt://projects",
            name="MantisBT Projects",
            description="All accessible MantisBT projects",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    client = get_client()

    if uri == "mantisbt://projects":
        projects = client.list_projects()
        return json.dumps([p.model_dump() for p in projects], default=str)

    if uri.startswith("mantisbt://issues/"):
        issue_id = int(uri.split("/")[-1])
        issue = client.get_issue(issue_id)
        return issue.to_context_str()

    raise ValueError(f"Unknown resource URI: {uri}")


def main():
    import asyncio
    import anyio

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    anyio.run(_run)


if __name__ == "__main__":
    main()
