"""Analysis models."""

from typing import Literal

from pydantic import BaseModel, Field

from analyzer.models.evidence import Evidence

# Type definitions
AnalysisLanguage = Literal["ja", "en"]


class CustomAnalysisResult(BaseModel):
    """Result of custom analysis with user-defined prompt."""

    prompt_text: str = Field(..., description="The custom prompt used for analysis")
    prompt_id: str | None = Field(None, description="ID of saved prompt if used")
    answer: str = Field(..., description="Free-form answer to the custom prompt")
    evidences: list[Evidence] = Field(default_factory=list, description="Supporting evidence")
