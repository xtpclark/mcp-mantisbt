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

# MantisBT status name → status_id mapping
STATUS_IDS = {
    'new':          10,
    'feedback':     20,
    'acknowledged': 30,
    'confirmed':    40,
    'assigned':     50,
    'resolved':     80,
    'closed':       90,
}


class MantisBTClient:
    """Thin synchronous wrapper around the MantisBT REST API."""

    def __init__(self, url: str, api_token: str, timeout: float = 15.0):
        self.base_url = url.rstrip('/') + '/api/rest/index.php'
        self.headers = {
            'Authorization': api_token,   # raw token, no "Bearer" prefix
            'Content-Type': 'application/json',
        }
        self.timeout = timeout

    def _get(self, path: str, params: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = httpx.get(url, headers=self.headers, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        resp = httpx.post(url, headers=self.headers, json=body, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, body: dict) -> dict:
        url = f"{self.base_url}{path}"
        resp = httpx.patch(url, headers=self.headers, json=body, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # ── Projects ──────────────────────────────────────────────────────────

    def list_projects(self) -> list[MantisBTProject]:
        data = self._get('/projects/')
        return [MantisBTProject(**p) for p in data.get('projects', [])]

    def get_project(self, project_id: int) -> MantisBTProject:
        data = self._get(f'/projects/{project_id}')
        return MantisBTProject(**data.get('project', data))

    # ── Issues ────────────────────────────────────────────────────────────

    def get_issue(self, issue_id: int) -> MantisBTIssue:
        data = self._get(f'/issues/{issue_id}')
        issues = data.get('issues', [data])
        return MantisBTIssue(**issues[0])

    def create_issue(
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
            'summary':     summary,
            'description': description,
            'severity':    {'name': severity},
            'priority':    {'name': priority},
        }
        if tags:
            body['tags'] = [{'name': t} for t in tags]

        data = self._post('/issues/', body)
        return MantisBTIssue(**data.get('issue', data))

    def search_issues(
        self,
        query: str = None,
        project_id: int = None,
        status: str = None,
        category: str = None,
        limit: int = 10,
    ) -> list[MantisBTIssue]:
        """
        Search issues. MantisBT REST search is filter-based, not full-text.
        We fetch filtered results then do client-side text matching on query.
        """
        params = {'page_size': min(limit * 3, 50)}  # fetch extra for client-side filter

        if project_id:
            params['project_id'] = project_id
        if status and status != 'all':
            status_id = STATUS_IDS.get(status.lower())
            if status_id:
                params['status_id'] = status_id
        if category:
            params['category_id'] = category  # by name if API supports, else skip

        data = self._get('/issues/', params)
        issues = [MantisBTIssue(**i) for i in data.get('issues', [])]

        # Client-side text filter
        if query:
            query_lower = query.lower()
            terms = query_lower.split()
            def matches(issue: MantisBTIssue) -> bool:
                haystack = ' '.join(filter(None, [
                    issue.summary or '',
                    issue.description or '',
                    ' '.join(n.text for n in issue.notes if n.text),
                ])).lower()
                return any(term in haystack for term in terms)
            issues = [i for i in issues if matches(i)]

        return issues[:limit]

    def add_note(
        self,
        issue_id: int,
        text: str,
        private: bool = False,
    ) -> dict:
        body = {
            'text': text,
            'view_state': {'name': 'private' if private else 'public'},
        }
        data = self._post(f'/issues/{issue_id}/notes/', body)
        return data.get('note', data)

    def resolve_issue(
        self,
        issue_id: int,
        resolution_note: str,
        resolution: str = 'fixed',
    ) -> MantisBTIssue:
        # Add resolution note first
        if resolution_note:
            self.add_note(issue_id, resolution_note)

        # Update status to resolved
        body = {
            'status':     {'name': 'resolved'},
            'resolution': {'name': resolution},
        }
        data = self._patch(f'/issues/{issue_id}', body)
        return MantisBTIssue(**data.get('issue', data))
