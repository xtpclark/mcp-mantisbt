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
        """
        Format for injection into AI prompt as similar_incidents context.
        Focuses on resolution notes — that's the actionable value.
        Skips the Assay findings dump in description (not useful as prior art).
        """
        status_name = self.status.name if self.status else 'unknown'
        lines = [
            f"Status: {status_name}",
        ]

        # Surface all resolution/notes — the most valuable content
        if self.notes:
            substantive = [
                n for n in self.notes
                if n.text and len(n.text) > 20
            ]
            if substantive:
                lines.append("How it was resolved:")
                for note in substantive:
                    lines.append(f"  {note.text[:600]}")

        if not self.notes or not any(n.text and len(n.text) > 20 for n in self.notes):
            # Fall back to first 200 chars of description if no notes
            if self.description:
                # Skip Assay-generated header lines
                desc_lines = [l for l in self.description.splitlines()
                              if l.strip() and not l.startswith('=') and 'Assay healthcheck' not in l]
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
