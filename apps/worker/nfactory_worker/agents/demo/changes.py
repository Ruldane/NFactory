"""Demo answer of the requirements agent for a change request (scenario E).

Starts from the delivered brief and adds each field the request names ("un filtre par
département", "le champ éditeur"). What it cannot apply becomes an open question.
"""

import re
import unicodedata
from typing import Any

from nfactory_worker.agents.demo.domains import GENERIC_ENTITY

_PARTS = re.compile(r"\s*(?:,|;|\bet\b|\bpuis\b)\s*")
_ELIDED = "l['" + chr(0x2019) + "]"  # l' with a straight or a typographic apostrophe
_FIELD = re.compile(
    r"(?:par|champ|colonne|attribut)\s+(?:le |la |les |" + _ELIDED + r"|un |une |des )?([a-zà-ÿ]+)",
    re.IGNORECASE,
)
_ARTICLE = re.compile(
    r"^(?:ajoute[rz]?|ajout(?:er)? d[e']|un |une |le |la |les |des |" + _ELIDED + r")\s*", re.I
)
_MAX_FIELDS = 12


def answer_change(payload: dict[str, Any]) -> dict[str, Any]:
    previous: dict[str, Any] = dict(payload["previous_brief"])
    request = " ".join(str(payload.get("request", "")).split())
    brief = {**previous, "goals": list(previous.get("goals", []))}
    entity = _entity(previous)
    questions = list(previous.get("open_questions", []))

    for part in filter(None, (p.strip(" .") for p in _PARTS.split(request))):
        match = _FIELD.search(part)
        if match and entity is not None:
            _add_field(entity, match.group(1))
        else:
            questions.append(
                f"« {_strip_articles(part)} » : non traité par le mode démo, à préciser."
            )
    if entity is not None:
        brief["entity"] = entity
    brief["goals"] = (brief["goals"] + [request])[:20]
    brief["summary"] = f"{previous.get('summary', '')}\nÉvolution : {request}"[:2000]
    brief["open_questions"] = questions[:20]
    return brief


def _entity(previous: dict[str, Any]) -> dict[str, Any] | None:
    if previous.get("entity"):
        source = previous["entity"]
    elif previous.get("project_type") in ("api", "webapp"):
        source = GENERIC_ENTITY  # what the recipe used when the brief had none
    else:
        return None
    return {**source, "fields": [dict(f) for f in source["fields"]]}


def _add_field(entity: dict[str, Any], word: str) -> None:
    name = _identifier(word)
    label = word[:1].upper() + word[1:].lower()
    known = {_identifier(f["name"]) for f in entity["fields"]}
    known |= {_identifier(f["label"]) for f in entity["fields"]}
    if not name or name in known or len(entity["fields"]) >= _MAX_FIELDS:
        return
    entity["fields"].append({"name": name, "label": label, "type": "str"})


def _identifier(word: str) -> str:
    ascii_word = unicodedata.normalize("NFKD", word).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9_]", "", ascii_word.lower())


def _strip_articles(part: str) -> str:
    previous = None
    while previous != part:
        previous, part = part, _ARTICLE.sub("", part)
    return part
