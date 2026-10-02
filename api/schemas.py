"""Validated public API shapes shared by the browser and future channels."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, StrictBool, field_validator


Category = Literal[
    "Healthcare",
    "Education",
    "Resettlement / Legal / Shelter",
]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Optional[Category] = None
    language: str = Field(default="en", min_length=2, max_length=16)
    limit: int = Field(default=3, ge=1, le=10)
    use_llm: StrictBool = True
    state: Optional[str] = Field(default=None, min_length=2, max_length=2)
    language_filter: Optional[str] = Field(default=None, min_length=2, max_length=32)
    use_semantic: StrictBool = True

    @field_validator("query")
    def query_must_have_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must contain text")
        return value

    @field_validator("state")
    def normalize_state(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else None

    @field_validator("language", "language_filter")
    def normalize_language(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().lower() if value else value


class RetrievalMetadata(BaseModel):
    mode: Literal["lexical", "hybrid"]
    semantic_available: bool
    source_ids: List[str]


class SearchResponse(BaseModel):
    category: str
    query: str
    understood: str
    zip: Optional[str]
    service: Optional[str]
    language: str
    results: List[Dict[str, Any]]
    intro: str
    text: str
    llm_used: bool
    retrieval: RetrievalMetadata
