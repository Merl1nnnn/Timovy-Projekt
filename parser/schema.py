"""NLP schema v2. Extraction is provisional until validate_posting passes.

Accepted records keep exact evidence spans and metadata quotes. Review records
must not be used as accepted analytics data. Legacy lists are retained for consumers.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Seniority = Literal["junior", "medior", "senior", "lead"]
EmploymentType = Literal["full_time", "part_time", "contract"]
Specialization = Literal["Python", "Java", "DevOps", "Data", "QA", "Frontend", "Backend", "ML", "Security", "Mobile", "Fullstack"]
WorkplaceType = Literal["on-site", "hybrid", "remote"]


class _SalaryCheck(BaseModel):
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None

    @model_validator(mode="after")
    def _check_salary(self) -> Any:
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError("salary_min must be <= salary_max")
        if self.salary_currency is not None:
            self.salary_currency = self.salary_currency.upper()
        return self


SkillKind = Literal["technology", "tool", "certification", "language", "methodology", "soft_skill"]
Requirement = Literal["required", "nice_to_have"]


class CandidateMention(BaseModel):
    model_config = ConfigDict(extra="forbid")
    surface: str = Field(min_length=1, description="Exact skill spelling from the posting")
    canonical: str = Field(min_length=1)
    kind: SkillKind
    requirement: Requirement
    evidence: str = Field(min_length=1, description="Exact unmodified quote from the requirements, containing surface")
    implicit: bool = False


class EvidenceSpan(BaseModel):
    quote: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)


class SkillMention(BaseModel):
    id: str
    surface: str
    canonical: str
    kind: SkillKind
    requirement: Requirement
    evidence: EvidenceSpan
    implicit: bool = False
    verdict: Literal["pending", "supported", "unsupported", "uncertain"] = "pending"
    confidence: float = Field(default=0, ge=0, le=1)
    reason: str = ""


class RejectedItem(BaseModel):
    canonical: str
    verdict: Literal["unsupported", "uncertain"]
    reason: str


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
    salary_min: float | None = Field(description="Salary lower bound as written; period/basis are normalised separately")
    salary_max: float | None = Field(description="Salary upper bound as written; null for 'from X'")
    salary_currency: str | None = Field(description="ISO 4217 code, e.g. EUR")
    mentions: list[CandidateMention] = Field(default_factory=list)
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
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    language: Literal["sk", "en", "cs", "und"]
    source_url: str

    skill_mentions: list[SkillMention] = Field(default_factory=list)
    certificates: list[str] = Field(default_factory=list)
    rejected_items: list[RejectedItem] = Field(default_factory=list)
    review_required: bool = False
    validation_status: Literal["unvalidated", "validated", "review"] = "unvalidated"
    alias_version: str = "nlp-1"
    language_confidence: float = 0
    region: str | None = None
    role_specializations: list[str] = Field(default_factory=list)
    salary_period: Literal["hour", "month", "year"] | None = None
    salary_basis: Literal["gross", "net", "unknown"] = "unknown"
    salary_monthly_min: float | None = None
    salary_monthly_max: float | None = None
    normalization_issues: list[str] = Field(default_factory=list)
    source_text_sha256: str = ""
    field_evidence: dict[str, EvidenceSpan] = Field(default_factory=dict)


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Усі властивості required для structured output, включно з вкладеними схемами."""
    schema = model.model_json_schema()
    def walk(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(schema)
    return schema


def llm_json_schema() -> dict[str, Any]:
    return strict_schema(JobExtraction)
