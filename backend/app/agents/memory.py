from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class MemoryNote:
    note: str
    source: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class StudentMemory:
    student_id: str
    preferences: Dict[str, str] = field(default_factory=dict)
    notes: List[MemoryNote] = field(default_factory=list)
    last_context: Optional[str] = None


class StudentMemoryStore:
    def __init__(self):
        self._store: Dict[str, StudentMemory] = {}

    def get_or_create(self, student_id: str) -> StudentMemory:
        if student_id not in self._store:
            self._store[student_id] = StudentMemory(student_id=student_id)
        return self._store[student_id]

    def add_note(self, student_id: str, note: str, source: str) -> StudentMemory:
        memory = self.get_or_create(student_id)
        memory.notes.append(MemoryNote(note=note, source=source))
        return memory

    def update_preferences(self, student_id: str, preferences: Dict[str, str]) -> StudentMemory:
        memory = self.get_or_create(student_id)
        memory.preferences.update(preferences)
        return memory

    def set_last_context(self, student_id: str, context: str):
        memory = self.get_or_create(student_id)
        memory.last_context = context


student_memory_store = StudentMemoryStore()
