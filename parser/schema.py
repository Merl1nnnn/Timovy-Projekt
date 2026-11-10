"""Pydantic-схеми вакансії.

JobExtraction — те, що повертає LLM (її JSON Schema передається моделі як structured output).
  Поля сформульовано так, як їх буквально видно на сторінці (workplace_type замість remote: bool):
  7B-модель на таких полях помиляється значно рідше, ніж на похідних.
JobPosting — фінальний запис за ТЗ (remote: bool, language: sk|en, source_url).
  Перетворення JobExtraction -> JobPosting робить parser/normalize.py.
Семантика полів JobPosting збігається з data/ground_truth.json (docs/JOURNAL.md, етап 1).
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
    # extra="forbid" -> additionalProperties: false у схемі (вимога structured outputs).
    # Усі поля без значень за замовчуванням -> усі в "required"; nullable через `| None`.
    # Порядок полів = порядок генерації JSON моделлю.
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
    # language навмисно не питаємо в LLM: qwen2.5:7b стабільно ставила "Slovak" для англійських
    # вакансій (0.38-0.56 accuracy). Мову визначає правило parser/normalize.py:detect_language.


class JobPosting(_SalaryCheck):
    title: str
    company: str
    location: str | None
    remote: bool  # true для повністю віддаленої і для гібридної роботи
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
    """JSON Schema для structured output (спільна для Ollama і Claude)."""
    return JobExtraction.model_json_schema()
