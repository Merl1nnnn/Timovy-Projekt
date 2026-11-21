import pytest

from esco.data import Catalog, Concept, Labels
from esco.search import Matcher, Query, key, make_queries


def catalog():
    rows = []
    for n, name, aliases in [(1, "Java", ["Java programming"]), (2, "JavaScript", ["JS"]),
                             (3, "C", []), (4, "C++", []), (5, "C#", [])]:
        rows.append(Concept(uri=f"http://data.europa.eu/esco/skill/00000000-0000-0000-0000-{n:012}",
                            labels={"en": Labels(preferred=name, alternative=aliases)}))
    return Catalog(esco_version="synthetic-test", concepts=rows)


def test_exact_and_alternative_labels_rank_first():
    matcher = Matcher(catalog())
    for name, expected in [("java", "Java"), ("JS", "JavaScript"), ("  JavaScript  ", "JavaScript")]:
        result = matcher.search(Query(id="q", skill=name))
        assert result["candidates"][0]["labels"]["en"] == expected
        assert result["candidates"][0]["method"] == "exact_label"
        assert result["selected_uri"] is None
        assert result["status"] == "needs_review"


def test_programming_language_punctuation_is_significant():
    matcher = Matcher(catalog())
    assert len({key(x) for x in ["C", "C++", "C#", ".NET"]}) == 4
    for name in ["C", "C++", "C#"]:
        assert matcher.search(Query(id="q", skill=name))["candidates"][0]["labels"]["en"] == name


def test_ambiguous_exact_matches_need_review():
    data = catalog()
    data.concepts[0].labels["en"].alternative.append("shared")
    data.concepts[1].labels["en"].alternative.append("shared")
    result = Matcher(data).search(Query(id="q", skill="shared"))
    assert result["exact_match_count"] == 2
    assert result["selected_uri"] is None


def test_lexical_typo_search_is_a_suggestion_not_a_decision():
    result = Matcher(catalog()).search(Query(id="q", skill="JavScript"))
    assert result["candidates"][0]["labels"]["en"] == "JavaScript"
    assert result["candidates"][0]["method"] == "lexical_similarity"
    assert result["status"] == "needs_review"


def test_collect_groups_skills_without_losing_origins():
    rows = [{"id": "1", "site": "profesia", "required_skills": ["SQL", "Python"], "nice_to_have_skills": []},
            {"id": "2", "site": "profesia", "required_skills": [], "nice_to_have_skills": ["sql"]}]
    queries = make_queries(rows)
    sql = next(q for q in queries if key(q.skill) == "sql")
    assert len(queries) == 2
    assert len(sql.occurrences) == 2
    assert {r["field"] for r in sql.occurrences} == {"required_skills", "nice_to_have_skills"}
    assert sql.context == ""
    assert rows[0]["required_skills"] == ["SQL", "Python"]


def test_collect_rejects_duplicate_jobs_and_bad_skill_fields():
    row = {"id": "1", "required_skills": ["SQL"], "nice_to_have_skills": []}
    with pytest.raises(ValueError, match="Duplicate"):
        make_queries([row, row])
    with pytest.raises(ValueError, match="list of skill"):
        make_queries([row | {"required_skills": "SQL"}])
    with pytest.raises(ValueError, match="No skills"):
        make_queries([])


def test_invalid_search_arguments_fail():
    matcher = Matcher(catalog())
    with pytest.raises(ValueError, match="non-empty"):
        matcher.search(Query(id="q", skill=" "))
    with pytest.raises(ValueError, match="index"):
        matcher.search(Query(id="q", skill="SQL"), "embedding")
    with pytest.raises(ValueError, match="Unknown"):
        matcher.search(Query(id="q", skill="SQL"), "magic")


def test_hybrid_preserves_exact_match_and_deduplicates():
    data = catalog()
    class FakeSemantic:
        def search(self, skill, context, k):
            return [(data.concepts[1], 0.9), (data.concepts[0], 0.8)]
    result = Matcher(data, FakeSemantic()).search(Query(id="q", skill="Java"), "hybrid")
    assert [r["labels"]["en"] for r in result["candidates"]] == ["Java", "JavaScript"]
    assert result["candidates"][0]["method"] == "exact_label"
