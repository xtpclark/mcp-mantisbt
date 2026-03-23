"""
MantisBT REST API client.

Auth quirk: token goes raw in the Authorization header — no "Bearer" prefix.
MantisBT validates strlen(token) == 32 before checking the hash, so the
"Bearer " prefix (7 chars) causes silent 401s.
"""

import logging
from typing import Optional

import httpx

from .models import MantisBTIssue, MantisBTProject, MantisBTNote

logger = logging.getLogger(__name__)

# MantisBT status name → status_id mapping (standard installation defaults)
STATUS_IDS = {
    'new':          10,
    'feedback':     20,
    'acknowledged': 30,
    'confirmed':    40,
    'assigned':     50,
    'resolved':     80,
    'closed':       90,
}

# Hard cap on results fetched from MantisBT in a single search.
# Protects MantisBT from large result floods and keeps AI context payloads reasonable.
MAX_FETCH = 50


class MantisBTClient:
    """Async wrapper around the MantisBT REST API."""

    def __init__(self, url: str, api_token: str, timeout: float = 15.0):
        if not url:
            raise ValueError("MantisBT URL is required")
        if not api_token:
            raise ValueError("MantisBT API token is required")
        if len(api_token) != 32:
            logger.warning(
                "API token is %d chars (expected 32) — MantisBT may reject it silently",
                len(api_token),
            )
        self.base_url = url.rstrip('/') + '/api/rest/index.php'
        self.instance_url = url.rstrip('/')
        self._headers = {
            'Authorization': api_token,   # raw token, no "Bearer" prefix
            'Content-Type': 'application/json',
        }
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=self.timeout)

    async def _get(self, path: str, params: dict = None) -> dict:
        async with self._client() as client:
            resp = await client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, body: dict) -> dict:
        async with self._client() as client:
            resp = await client.post(f"{self.base_url}{path}", json=body)
            resp.raise_for_status()
            return resp.json()

    async def _patch(self, path: str, body: dict) -> dict:
        async with self._client() as client:
            resp = await client.patch(f"{self.base_url}{path}", json=body)
            resp.raise_for_status()
            return resp.json()

    # ── Projects ──────────────────────────────────────────────────────────

    async def list_projects(self) -> list[MantisBTProject]:
        data = await self._get('/projects/')
        return [MantisBTProject(**p) for p in data.get('projects', [])]

    async def get_project(self, project_id: int) -> MantisBTProject:
        data = await self._get(f'/projects/{project_id}')
        project_data = data.get('project') or data
        return MantisBTProject(**project_data)

    # ── Issues ────────────────────────────────────────────────────────────

    async def get_issue(self, issue_id: int) -> MantisBTIssue:
        data = await self._get(f'/issues/{issue_id}')
        issues = data.get('issues') or [data.get('issue')] or [data]
        if not issues or issues[0] is None:
            raise ValueError(f"Issue #{issue_id} not found or unexpected API response")
        return MantisBTIssue(**issues[0])

    async def create_issue(
        self,
        project_id: int,
        summary: str,
        description: str,
        severity: str = 'major',
        priority: str = 'normal',
        category: str = 'General',
        tags: list[str] = None,
    ) -> MantisBTIssue:
        body = {
            'project':     {'id': project_id},
            'category':    {'name': category},
            'summary':     summary[:255],         # MantisBT summary field limit
            'description': description,
            'severity':    {'name': severity},
            'priority':    {'name': priority},
        }
        if tags:
            body['tags'] = [{'name': t} for t in tags]

        data = await self._post('/issues/', body)
        issue_data = data.get('issue') or data
        return MantisBTIssue(**issue_data)

    async def search_issues(
        self,
        query: str = None,
        project_id: int = None,
        status: str = None,
        category: str = None,
        limit: int = 10,
    ) -> tuple[list[MantisBTIssue], bool]:
        """
        Search issues. Returns (results, truncated) where truncated=True means
        there may be more matches beyond what was fetched.

        MantisBT REST search is filter-based, not full-text — we fetch filtered
        results then do client-side text matching on query.

        Hard cap: MAX_FETCH issues fetched from MantisBT regardless of limit,
        to protect the instance and keep AI context payloads reasonable.
        """
        # Enforce sane limit
        limit = min(limit, MAX_FETCH)
        fetch_size = MAX_FETCH   # always fetch the cap; filter down to limit

        params: dict = {'page_size': fetch_size, 'page': 1}

        if project_id:
            params['project_id'] = project_id
        if status and status != 'all':
            status_id = STATUS_IDS.get(status.lower())
            if status_id:
                params['status_id'] = status_id
            else:
                logger.warning("Unknown status '%s', ignoring status filter", status)
        # Note: category filtering by name is not reliably supported in the MantisBT
        # REST API — it expects category_id (int). Skipping to avoid silent mis-filter.
        # To filter by category, pass a project_id and filter client-side.

        data = await self._get('/issues/', params)
        raw_issues = data.get('issues', [])
        issues = [MantisBTIssue(**i) for i in raw_issues]

        # Client-side status filter (server-side status_id param not reliable across versions)
        if status and status != 'all':
            target_id = STATUS_IDS.get(status.lower())
            if target_id:
                issues = [i for i in issues if i.status and i.status.id == target_id]

        # Client-side text filter
        if query:
            terms = query.lower().split()
            def matches(issue: MantisBTIssue) -> bool:
                haystack = ' '.join(filter(None, [
                    issue.summary or '',
                    issue.description or '',
                    ' '.join(n.text for n in (issue.notes or []) if n.text),
                ])).lower()
                return any(term in haystack for term in terms)
            issues = [i for i in issues if matches(i)]

        # Client-side category filter (by name, since API doesn't support it reliably)
        if category:
            cat_lower = category.lower()
            issues = [
                i for i in issues
                if i.category and i.category.name.lower() == cat_lower
            ]

        truncated = len(raw_issues) >= fetch_size  # may be more on server
        return issues[:limit], truncated

    async def add_note(
        self,
        issue_id: int,
        text: str,
        private: bool = False,
    ) -> MantisBTNote:
        body = {
            'text': text,
            'view_state': {'name': 'private' if private else 'public'},
        }
        data = await self._post(f'/issues/{issue_id}/notes/', body)
        note_data = data.get('note') or data
        return MantisBTNote(**note_data)

    async def resolve_issue(
        self,
        issue_id: int,
        resolution_note: str,
        resolution: str = 'fixed',
    ) -> MantisBTIssue:
        # Update status first — if this fails, no orphaned note
        body = {
            'status':     {'name': 'resolved'},
            'resolution': {'name': resolution},
        }
        data = await self._patch(f'/issues/{issue_id}', body)

        # Parse response (PATCH may return 'issues' list or 'issue' singular)
        if 'issues' in data and data['issues']:
            issue = MantisBTIssue(**data['issues'][0])
        elif 'issue' in data:
            issue = MantisBTIssue(**data['issue'])
        else:
            issue = MantisBTIssue(**data)

        # Add resolution note after status change
        if resolution_note and resolution_note.strip():
            await self.add_note(issue_id, resolution_note)

        return issue
