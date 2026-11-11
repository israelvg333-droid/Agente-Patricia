from __future__ import annotations

import re
import unicodedata
from typing import Any

EMERGENCY_TERMS = {
    # Spanish
    "emergencia", "auxilio", "ayuda", "urgente", "ambulancia", "policia",
    "bomberos", "incendio", "choque", "accidente", "asalto", "robo",
    "arma", "balazo", "disparo", "herido", "sangre", "violencia",
    "golpearon", "secuestro", "amenaza", "desmayo", "infarto", "medico",
    # English
    "emergency", "help", "urgent", "ambulance", "police", "fire department",
    "firefighters", "fire", "crash", "robbery", "theft", "weapon", "gun",
    "gunshot", "shot", "shooting", "injured", "bleeding", "blood",
    "attacked", "kidnapping", "threat", "fainted", "heart attack", "doctor",
    "911", "assault", "stabbing", "dead", "dying",
}
JOKE_TERMS = {
    # Spanish
    "jaja", "jeje", "risa", "broma", "mentira", "jugando", "molestar",
    "troleo", "falso", "no es cierto", "era broma", "jajaja", "xd",
    # English
    "haha", "hehe", "lol", "lmao", "lmfao", "rofl", "joking", "prank",
    "kidding", "fake", "jk", "just kidding", "not real", "it was a joke",
    "i was joking", "not serious", "fooling around",
}
LOCATION_HINTS = {
    # Spanish
    "calle", "avenida", "colonia", "municipio", "delegacion", "esquina",
    "numero", "km", "kilometro", "carretera", "casa", "edificio",
    "parque", "escuela", "hospital", "tienda", "plaza",
    # English
    "street", "avenue", "neighborhood", "district", "corner", "highway",
    "road", "house", "building", "park", "school", "store", "mall",
    "intersection", "boulevard", "lane", "drive", "block", "suburb",
}
VICTIM_HINTS = {
    # Spanish
    "persona", "senor", "senora", "nino", "nina", "adulto", "herido",
    "victima", "mi mama", "mi papa", "mi hijo", "mi hija", "alguien",
    "conductor", "pasajero",
    # English
    "person", "man", "woman", "child", "kid", "adult", "injured",
    "victim", "my mom", "my dad", "my son", "my daughter", "someone",
    "driver", "passenger", "guy", "lady", "elderly", "baby",
}
INCIDENT_HINTS = {
    # Spanish
    "incendio", "robo", "asalto", "choque", "accidente", "pelea",
    "agresion", "violencia", "disparo", "balazo", "desmayo", "fuga",
    "gas", "inundacion", "amenaza", "secuestro",
    # English
    "fire", "robbery", "theft", "crash", "accident", "fight",
    "assault", "violence", "gunshot", "shooting", "stabbing", "fainted",
    "gas leak", "flood", "threat", "kidnapping", "overdose", "break-in",
}


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def analyze_text(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    tokens = re.findall(r"\b[\w]+\b", normalized)
    word_count = len(tokens)
    emergency_matches = _find_terms(normalized, EMERGENCY_TERMS)
    joke_matches = _find_terms(normalized, JOKE_TERMS)
    has_location = bool(
        _find_terms(normalized, LOCATION_HINTS) or _has_address_like_text(normalized)
    )
    has_victim = bool(_find_terms(normalized, VICTIM_HINTS))
    incident_matches = _find_terms(normalized, INCIDENT_HINTS)

    completeness_items = {
        "has_location": has_location,
        "has_affected_people": has_victim,
        "has_incident_type": bool(incident_matches),
        "has_minimum_detail": word_count >= 12,
    }
    completeness_score = sum(completeness_items.values()) / len(completeness_items)

    return {
        "word_count": word_count,
        "emergency_keywords": emergency_matches,
        "joke_or_mockery_keywords": joke_matches,
        "incident_keywords": incident_matches,
        "has_location": has_location,
        "has_affected_people": has_victim,
        "has_incident_type": bool(incident_matches),
        "completeness_items": completeness_items,
        "completeness_score": round(completeness_score, 3),
        "text_is_empty": word_count == 0,
    }


def _find_terms(text: str, terms: set[str]) -> list[str]:
    found = []
    for term in sorted(terms):
        normalized_term = normalize_text(term)
        if " " in normalized_term:
            if normalized_term in text:
                found.append(term)
        elif re.search(rf"\b{re.escape(normalized_term)}\b", text):
            found.append(term)
    return found


def _has_address_like_text(text: str) -> bool:
    return bool(re.search(r"\b(no\.?|numero|#)\s*\d+\b", text) or re.search(r"\b\d{2,5}\b", text))
