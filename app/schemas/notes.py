"""笔记分析的输入与输出；本地校验始终执行。"""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

class NoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_text: str = Field(min_length=1, max_length=10000)

    @field_validator("note_text", mode="before")
    @classmethod
    def strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

class NoteAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    keywords: list[NonBlank] = Field(min_length=1, max_length=5)
    difficulty: Literal["easy", "medium", "hard"]

    @field_validator("keywords")
    @classmethod
    def unique_keywords(cls, value):
        if len({word.casefold() for word in value}) != len(value):
            raise ValueError("关键词不能重复")
        return value
