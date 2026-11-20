import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictStr, model_validator

API = "https://ec.europa.eu/esco/api/resource/skill"
SKILL_URI = re.compile(r"^http://data\.europa\.eu/esco/(?:skill/[0-9a-f-]{36}|isced-f/[0-9]+)$")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Labels(Record):
    preferred: StrictStr = Field(min_length=1)
    alternative: list[StrictStr] = Field(default_factory=list)
    description: StrictStr = ""


class Concept(Record):
    uri: StrictStr
    labels: dict[str, Labels]
    skill_type: str = ""

    @model_validator(mode="after")
    def check(self):
        if not SKILL_URI.fullmatch(self.uri) or not self.labels:
            raise ValueError("Expected an ESCO skill URI and at least one language")
        return self


class Catalog(Record):
    format_version: Literal[1] = 1
    esco_version: StrictStr = Field(min_length=1)
    concepts: list[Concept] = Field(min_length=1)
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def check(self):
        if len({c.uri for c in self.concepts}) != len(self.concepts):
            raise ValueError("Duplicate concept URIs")
        return self

    @property
    def fingerprint(self):
        return digest({"esco_version": self.esco_version,
                       "concepts": sorted((c.model_dump() for c in self.concepts), key=lambda c: c["uri"])})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def load_catalog(path: Path):
    return Catalog.model_validate(read_json(path))


def from_api(payload, languages):
    concepts = []
    for item in payload["concepts"]:
        uri = item["uri"]
        node = payload["_embedded"][uri]
        if node.get("uri") != uri or node.get("className") != "Skill":
            raise ValueError("Unexpected ESCO API concept")
        labels = {}
        for lang in languages:
            preferred = node.get("preferredLabel", {}).get(lang)
            if preferred:
                labels[lang] = Labels(preferred=preferred,
                    alternative=node.get("alternativeLabel", {}).get(lang, []),
                    description=node.get("description", {}).get(lang, {}).get("literal", ""))
        types = node.get("_links", {}).get("hasSkillType", [])
        concepts.append(Concept(uri=uri, labels=labels, skill_type=types[0]["uri"] if types else ""))
    return concepts


def fetch_catalog(out: Path, version="v1.2.0", languages=("en", "sk"), page_size=200,
                  cache_dir: Path | None = None, http=None, log=print):
    if out.exists():
        raise ValueError("Catalog output already exists; choose a new path")
    if not 1 <= page_size <= 500:
        raise ValueError("Page size must be between 1 and 500")
    config = {"version": version, "languages": sorted(set(languages)), "page_size": page_size, "api": API, "pagination": "page-number"}
    cache = (cache_dir or out.parent / "downloads") / digest(config)
    cache.mkdir(parents=True, exist_ok=True)
    owned = http is None
    client = http or httpx.Client(timeout=120, follow_redirects=True)
    concepts, pages, offset, total = [], [], 0, None
    try:
        while total is None or len(concepts) < total:
            path = cache / f"page-{offset:06}.json"
            if path.exists():
                page = read_json(path)
            else:
                params = {"isInScheme": "http://data.europa.eu/esco/concept-scheme/skills",
                          "selectedVersion": version, "language": "en", "offset": offset,
                          "limit": page_size, "viewObsolete": "false"}
                for attempt in range(3):
                    response = client.get(API, params=params)
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()
                    break
                payload = response.json()
                rows = from_api(payload, languages)
                page = {"offset": payload["offset"], "total": payload["total"],
                        "concepts": [c.model_dump() for c in rows],
                        "response_sha256": hashlib.sha256(response.content).hexdigest()}
                if payload["count"] != len(rows):
                    raise ValueError("Incomplete API page")
                write_json(path, page)
                time.sleep(0.15)
            if page["offset"] != offset or not page["concepts"]:
                raise ValueError("Invalid pagination; download cannot be marked complete")
            if total is not None and total != page["total"]:
                raise ValueError("API total changed during download")
            total = page["total"]
            concepts.extend(Concept.model_validate(c) for c in page["concepts"])
            pages.append({"offset": offset, "response_sha256": page["response_sha256"]})
            offset += 1
            log(f"ESCO skills: {len(concepts)}/{total}")
        if len(concepts) != total:
            raise ValueError("Incomplete ESCO catalog")
        catalog = Catalog(esco_version=version, concepts=sorted(concepts, key=lambda c: c.uri),
            provenance={"source": API, "requested_version": version, "languages": list(languages),
                        "downloaded_at": datetime.now(timezone.utc).isoformat(),
                        "complete": True, "api_total": total, "pages": pages})
        write_json(out, catalog.model_dump())
        return catalog
    finally:
        if owned:
            client.close()


def import_csv(files: dict[str, Path], version: str, out: Path):
    concepts, sources = {}, []
    for lang, path in files.items():
        sources.append({"language": lang, "file": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not {"conceptUri", "preferredLabel", "altLabels", "description"} <= set(reader.fieldnames or []):
                raise ValueError(f"{path.name}: expected an official skills CSV")
            seen = set()
            for row in reader:
                uri = row["conceptUri"]
                if uri in seen:
                    raise ValueError(f"Duplicate URI in {path.name}: {uri}")
                seen.add(uri)
                labels = Labels(preferred=row["preferredLabel"].strip(),
                                alternative=[x.strip() for x in row["altLabels"].splitlines() if x.strip()],
                                description=row["description"].strip())
                item = concepts.setdefault(uri, {"uri": uri, "labels": {}, "skill_type": row.get("skillType", "")})
                item["labels"][lang] = labels
    catalog = Catalog(esco_version=version, concepts=[Concept.model_validate(v) for v in concepts.values()],
                      provenance={"source": "official_csv", "files": sources,
                                  "version_note": "Release version supplied by the importer; check the downloaded package."})
    write_json(out, catalog.model_dump())
    return catalog
