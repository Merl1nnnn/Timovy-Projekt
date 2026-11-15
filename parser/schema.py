"""Pydantic schemas for a job posting.

JobExtraction is what the LLM returns (its JSON Schema is passed to the model as structured output).
  Fields are phrased the way they literally appear on the page (workplace_type instead of remote: bool):
  a 7B model makes far fewer mistakes on such fields than on derived ones.
JobPosting is the final record per the spec (remote: bool, language: sk|en, source_url).
  parser/normalize.py converts JobExtraction -> JobPosting.
JobPosting field semantics match data/ground_truth.json (docs/JOURNAL.md, stage 1).
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Seniority = Literal["junior", "medior", "senior", "lead"]
EmploymentType = Literal["full_time", "part_time", "contract"]
Specialization = Literal["Python", "Java", "DevOps", "Data", "QA", "Frontend"]
WorkplaceType = Literal["on-site", "hybrid", "remote"]


class _SalaryCheck(BaseModel):
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None

    @model_validator(mode="after")
    def _check_salary(self) -> Any:
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        if self.salary_currency is not None:
            self.salary_currency = self.salary_currency.upper()
        return self


class JobExtraction(_SalaryCheck):
    # extra="forbid" -> additionalProperties: false in the schema (required by structured outputs).
    # No field has a default -> all of them are in "required"; nullable via `| None`.
    # Field order = the order in which the model generates the JSON.
    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Job title exactly as written on the page, not translated")
    company: str
    location: str | None = Field(description="City only, canonical Slovak spelling; null if fully remote")
    workplace_type: WorkplaceType
    employment_type: EmploymentType | None
    seniority: Seniority | None
    specialization: Specialization | None
    required_skills: list[str]
    nice_to_have_skills: list[str]
    technologies: list[str]
    salary_min: int | None = Field(description="Monthly gross salary lower bound")
    salary_max: int | None = Field(description="Monthly gross salary upper bound; null for 'from X'")
    salary_currency: str | None = Field(description="ISO 4217 code, e.g. EUR")
    # language is deliberately not requested from the LLM: qwen2.5:7b kept answering "Slovak" for English
    # postings (0.38-0.56 accuracy). The rule parser/normalize.py:detect_language sets the language.


class JobPosting(_SalaryCheck):
    title: str
    company: str
    location: str | None
    remote: bool  # true for both fully remote and hybrid work
    employment_type: EmploymentType | None
    seniority: Seniority | None
    specialization: Specialization | None
    required_skills: list[str]
    nice_to_have_skills: list[str]
    technologies: list[str]
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    language: Literal["sk", "en"]
    source_url: str


def llm_json_schema() -> dict[str, Any]:
    """JSON Schema for structured output (shared by Ollama and Claude)."""
    return JobExtraction.model_json_schema()
