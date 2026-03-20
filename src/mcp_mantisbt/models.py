"""Pydantic models for MantisBT API objects."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class MantisBTEnum(BaseModel):
    id: int
    name: str
    label: Optional[str] = None


class MantisBTUser(BaseModel):
    id: int
    name: str
    real_name: Optional[str] = None
    email: Optional[str] = None


class MantisBTNote(BaseModel):
    id: int
    reporter: Optional[MantisBTUser] = None
    text: str
    view_state: Optional[MantisBTEnum] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MantisBTIssue(BaseModel):
    id: int
    summary: str
    description: Optional[str] = None
    project: Optional[MantisBTEnum] = None
    category: Optional[MantisBTEnum] = None
    status: Optional[MantisBTEnum] = None
    resolution: Optional[MantisBTEnum] = None
    severity: Optional[MantisBTEnum] = None
    priority: Optional[MantisBTEnum] = None
    reporter: Optional[MantisBTUser] = None
    handler: Optional[MantisBTUser] = None
    tags: list[dict] = []
    notes: list[MantisBTNote] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_context_str(self) -> str:
        """Format for injection into AI prompt as similar_incidents context."""
        lines = [
            f"Issue #{self.id}: {self.summary}",
            f"Status: {self.status.name if self.status else 'unknown'}",
            f"Severity: {self.severity.name if self.severity else 'unknown'}",
        ]
        if self.description:
            lines.append(f"Description: {self.description[:500]}")
        if self.notes:
            resolution_notes = [
                n for n in self.notes
                if n.text and len(n.text) > 20
            ]
            if resolution_notes:
                last = resolution_notes[-1]
                lines.append(f"Resolution note: {last.text[:500]}")
        return '\n'.join(lines)


class MantisBTProject(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[MantisBTEnum] = None
    enabled: bool = True
    categories: list[dict] = []
