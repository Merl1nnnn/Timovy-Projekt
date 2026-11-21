import difflib
import re
import unicodedata

from pydantic import Field, StrictStr

from esco.data import Catalog, Record, digest


class Query(Record):
    id: StrictStr = Field(min_length=1)
    skill: StrictStr = Field(min_length=1)
    context: StrictStr = ""
    occurrences: list[dict] = Field(default_factory=list)


def key(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def make_queries(records):
    queries = {}
    seen_jobs = set()
    for row in records:
        source = row.get("source_url") or row.get("url")
        job_id = row.get("id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("Every input job needs a string id")
        identity = (row.get("site", ""), job_id)
        if identity in seen_jobs:
            raise ValueError(f"Duplicate job {identity}; select one parser run")
        seen_jobs.add(identity)
        for field in ("required_skills", "nice_to_have_skills"):
            values = row.get(field)
            if not isinstance(values, list) or not all(isinstance(x, str) and x.strip() for x in values):
                raise ValueError(f"{job_id}: {field} must be a list of skill names")
            for skill in dict.fromkeys(values):
                normalized = key(skill)
                query = queries.setdefault(normalized, Query(id=digest(normalized)[:20], skill=skill.strip()))
                occurrence = {"job_id": job_id, "site": row.get("site"), "source_url": source,
                              "field": field, "original_skill": skill, "text_hash": row.get("text_hash")}
                if occurrence not in query.occurrences:
                    query.occurrences.append(occurrence)
    if not queries:
        raise ValueError("No skills found in input records")
    return sorted(queries.values(), key=lambda q: key(q.skill))


class Matcher:
    def __init__(self, catalog: Catalog, semantic=None):
        self.catalog, self.semantic = catalog, semantic
        self.aliases = {}
        self.names = {}
        for concept in catalog.concepts:
            names = {key(name) for labels in concept.labels.values()
                     for name in [labels.preferred, *labels.alternative] if name.strip()}
            self.names[concept.uri] = names
            for name in names:
                self.aliases.setdefault(name, {})[concept.uri] = concept

    def search(self, query: Query, method="lexical", k=3):
        if not query.skill.strip() or not 1 <= k <= 20:
            raise ValueError("Use a non-empty skill and k between 1 and 20")
        if method not in ("lexical", "embedding", "hybrid"):
            raise ValueError("Unknown mapping method")
        normalized = key(query.skill)
        exact = self.aliases.get(normalized, {})
        ranked = []
        if method != "embedding":
            ranked.extend((c, 1.0, "exact_label") for c in sorted(exact.values(), key=lambda c: c.uri))
        if method in ("embedding", "hybrid"):
            if self.semantic is None:
                raise ValueError("Embedding search needs a compatible index")
            ranked.extend((c, score, "embedding") for c, score in self.semantic.search(query.skill, query.context, k))
        else:
            tokens = set(re.findall(r"[\w+#.]+", normalized))
            for concept in self.catalog.concepts:
                if concept.uri in exact:
                    continue
                best = 0.0
                for name in self.names[concept.uri]:
                    other = set(re.findall(r"[\w+#.]+", name))
                    overlap = len(tokens & other) / len(tokens | other) if tokens | other else 0
                    similarity = difflib.SequenceMatcher(None, normalized, name, autojunk=False).ratio()
                    best = max(best, 0.5 * overlap + 0.5 * similarity)
                if best > 0:
                    ranked.append((concept, best, "lexical_similarity"))
            ranked.sort(key=lambda x: (x[2] != "exact_label", -x[1], x[0].uri))
        candidates, seen = [], set()
        for concept, score, evidence in ranked:
            if concept.uri in seen:
                continue
            seen.add(concept.uri)
            candidates.append({"uri": concept.uri, "labels": {lang: v.preferred for lang, v in concept.labels.items()},
                               "score": round(score, 6), "method": evidence})
            if len(candidates) == k:
                break
        return {**query.model_dump(), "status": "needs_review" if candidates else "no_candidates",
                "selected_uri": None, "exact_match_count": len(exact), "candidates": candidates}
