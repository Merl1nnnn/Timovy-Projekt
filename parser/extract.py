"""Витяг JobPosting із тексту сторінки через LLM: промпт, валідація Pydantic, retry."""

from pydantic import ValidationError

from parser.llm import LLMClient, Message
from parser.normalize import normalize
from parser.schema import JobExtraction, JobPosting, llm_json_schema

MAX_RETRIES = 2  # додаткові спроби після першої

SYSTEM_PROMPT = """You extract structured data from one IT job posting page. Return ONLY a JSON object matching the schema.
Ignore cookie banners, navigation, and the "Podobné ponuky" / "People also viewed" list of other jobs.

TITLE / COMPANY
- title: copy the main job title character by character, e.g. "Senior Java vývojár (m/ž)". NEVER translate it.
- company: employer name exactly as written.

WHERE / HOW
- location: city only, Slovak spelling with diacritics (Bratislava, Košice, Žilina). null if fully remote.
- workplace_type: "remote" if fully remote (Remote, práca z domu, anywhere); "hybrid" if Hybrid or some days of home office per week ("Možnosť home office", "days per week from home"); otherwise "on-site".
- employment_type: copy the label from the page: "Full-time" / "plný úväzok" / "TPP" -> full_time; "Part-time" / "skrátený" / "čiastočný úväzok" -> part_time; "Contract" / "Contractor" / "B2B" / "živnosť" / "kontrakt" -> contract.

LEVEL / ROLE
- seniority: from the title if it contains a level (Junior/Jr./Začínajúci -> junior; Medior/Mid -> medior; Senior/Sr./Skúsený -> senior; Lead/Tech Lead/Team Lead/Principal -> lead). If the title has no level, use required experience: 0-1 years junior, 2-4 medior, 5-6 senior, 7+ or team leading lead.
- specialization: one of Python, Java, DevOps, Data, QA, Frontend.

SKILLS - take them ONLY from the requirements part (Požiadavky, Požadujeme, Must have, Requirements, Who we're looking for, What you bring, Čo by si mal/a ovládať, or a sentence like "Hľadáme..." / "We are looking for..."). NEVER from duties (Náplň práce, What you'll do, Čo budeš robiť) or benefits.
- nice_to_have_skills: items under a "Výhodou je" / "Nice to have" / "Bonus points" / "Plusové body" heading, or items marked with (výhodou), (plus), (bonus), (nice to have), "– a plus", "– nice to have", or after "Výhodou je znalosť" / "It's a plus if you know".
- required_skills: every other requirement item that is a technology or skill. Skip years of experience and education.
- Non-technical requirements: include them ONLY if the page explicitly asks for them, and name them "English" (English language), "Slovak" (Slovak/Czech language), "Scrum" (Scrum/agile experience), "Communication" (communication skills). Do not add any of these if the page does not mention it.
- technologies: every technology/tool/framework from required_skills and nice_to_have_skills (no English/Slovak/Scrum/Communication).
- Write technologies with standard names: js -> JavaScript, k8s -> Kubernetes, postgres -> PostgreSQL.

SALARY
- salary_min / salary_max: monthly gross integers. "od X" / "From X" -> salary_min=X, salary_max=null. No salary -> all three salary fields null. salary_currency: "EUR"."""


class ExtractionError(RuntimeError):
    def __init__(self, message: str, attempts: int, last_output: str) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.last_output = last_output


def extract(client: LLMClient, page_text: str, source_url: str) -> tuple[JobPosting, int]:
    """Повертає (нормалізований JobPosting, кількість спроб)."""
    schema = llm_json_schema()
    messages: list[Message] = [{"role": "user", "content": f"Job posting page text:\n\n{page_text}"}]
    raw = ""
    for attempt in range(1, MAX_RETRIES + 2):
        raw = client.complete(SYSTEM_PROMPT, messages, schema)
        try:
            ex = JobExtraction.model_validate_json(raw)
        except ValidationError as e:
            if attempt > MAX_RETRIES:
                raise ExtractionError(f"невалідний JSON після {attempt} спроб: {e}", attempt, raw) from e
            # Повертаємо моделі її відповідь і помилку валідації — нехай виправить.
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Your JSON failed validation:\n"
                                            f"{e}\nReturn the corrected JSON object only."},
            ]
            continue
        return normalize(ex, source_url, page_text), attempt
    raise AssertionError("unreachable")
