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
    tags: list[MantisBTEnum] = []
    notes: list[MantisBTNote] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_context_str(self) -> str:
        """
        Format for injection into AI prompt as similar_incidents context.
        Focuses on resolution notes — that's the actionable value.
        """
        status_name = self.status.name if self.status else 'unknown'
        lines = [
            f"Issue #{self.id}: {self.summary}",
            f"Status: {status_name}",
        ]

        if self.category:
            lines.append(f"Category: {self.category.name}")

        # Surface resolution notes — the most valuable content for AI context
        substantive_notes = [
            n for n in (self.notes or [])
            if n.text and len(n.text.strip()) > 20
        ]
        if substantive_notes:
            lines.append("Resolution notes:")
            for note in substantive_notes:
                lines.append(f"  {note.text.strip()[:600]}")
        elif self.description:
            # Fall back to first few lines of description if no notes
            desc_lines = [
                l for l in self.description.splitlines()
                if l.strip() and not l.startswith('=')
            ]
            if desc_lines:
                lines.append(f"Context: {' '.join(desc_lines[:3])[:300]}")

        return '\n'.join(lines)


class MantisBTProject(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[MantisBTEnum] = None
    enabled: bool = True
    categories: list[dict] = []
