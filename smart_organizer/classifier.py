from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import json
import os
import re

from .config import (
    ARCHIVE_EXTENSIONS,
    DEFAULT_CATEGORIES,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    PDF_EXTENSIONS,
)


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    method: str
    rationale: str
    matched_terms: List[str]


class SemanticClassifier:
    def __init__(self, categories: Optional[Dict[str, Dict[str, object]]] = None):
        self.categories = categories or DEFAULT_CATEGORIES
        self.llm_provider = os.getenv("ORGANIZER_LLM_PROVIDER", "").strip().lower()

    def classify(self, text: str, path: Path, mime_type: str = "") -> ClassificationResult:
        text = (text or "").strip()

        if self.llm_provider:
            llm_result = self._try_llm(text, path, mime_type)
            if llm_result:
                return llm_result

        return self._classify_locally(text, path, mime_type)

    def _classify_locally(self, text: str, path: Path, mime_type: str) -> ClassificationResult:
        suffix = path.suffix.lower()
        normalized = _normalize_text(text)
        scores: Dict[str, float] = {}
        matches: Dict[str, List[str]] = {}

        for category, cfg in self.categories.items():
            if category == "Uncategorized":
                continue
            score, terms = self._score_category(normalized, cfg.get("keywords", []))
            if score:
                scores[category] = score
                matches[category] = terms

        if suffix in IMAGE_EXTENSIONS or mime_type.startswith("image/"):
            scores["Images"] = scores.get("Images", 0) + (2.5 if not normalized else 1.0)
            matches.setdefault("Images", []).append("image metadata")
        elif suffix in ARCHIVE_EXTENSIONS:
            scores["Archives"] = scores.get("Archives", 0) + 3.0
            matches.setdefault("Archives", []).append("archive metadata")
        elif suffix in MEDIA_EXTENSIONS or mime_type.startswith(("audio/", "video/")):
            scores["Media"] = scores.get("Media", 0) + 3.0
            matches.setdefault("Media", []).append("media metadata")
        elif suffix in PDF_EXTENSIONS and not normalized:
            scores["Documents"] = scores.get("Documents", 0) + 0.75
            matches.setdefault("Documents", []).append("pdf metadata")

        if not scores:
            return ClassificationResult(
                "Uncategorized",
                0.0,
                "local-semantic",
                "No strong semantic signal was found.",
                [],
            )

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        category, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        confidence = _confidence(best_score, second_score, len(normalized))

        if confidence < 0.33 and category not in {"Images", "Archives", "Media"}:
            return ClassificationResult(
                "Uncategorized",
                confidence,
                "local-semantic",
                "Signals were too weak or ambiguous.",
                matches.get(category, [])[:8],
            )

        return ClassificationResult(
            category,
            confidence,
            "local-semantic",
            f"Matched semantic terms for {category}.",
            matches.get(category, [])[:8],
        )

    def _score_category(self, normalized_text: str, keywords: Iterable[object]) -> Tuple[float, List[str]]:
        score = 0.0
        matched_terms: List[str] = []
        if not normalized_text:
            return score, matched_terms

        for raw_term in keywords:
            term = str(raw_term).lower().strip()
            if not term:
                continue
            normalized_term = _normalize_text(term)
            count = _phrase_count(normalized_text, normalized_term)
            if count:
                weight = 1.0 + min(len(normalized_term.split()), 4) * 0.25
                score += min(count, 4) * weight
                matched_terms.append(term)

        return score, matched_terms

    def _try_llm(self, text: str, path: Path, mime_type: str) -> Optional[ClassificationResult]:
        if self.llm_provider != "openai":
            return None
        if not os.getenv("OPENAI_API_KEY"):
            return None

        try:
            from openai import OpenAI  # type: ignore

            client = OpenAI()
            categories = {
                name: cfg.get("description", "")
                for name, cfg in self.categories.items()
            }
            prompt = {
                "file_name": path.name,
                "mime_type": mime_type,
                "categories": categories,
                "content_excerpt": text[:6000],
                "instruction": (
                    "Classify this downloaded file into exactly one category. "
                    "Respond only as JSON with category, confidence between 0 and 1, and rationale."
                ),
            }
            response = client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                messages=[
                    {
                        "role": "system",
                        "content": "You classify local downloaded files safely and conservatively.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                temperature=0,
            )
            content = response.choices[0].message.content or ""
            data = _json_from_text(content)
            category = str(data.get("category", "Uncategorized"))
            if category not in self.categories:
                category = "Uncategorized"
            return ClassificationResult(
                category,
                float(data.get("confidence", 0.5)),
                "openai-llm",
                str(data.get("rationale", "LLM classification.")),
                [],
            )
        except Exception:
            return None


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _phrase_count(text: str, phrase: str) -> int:
    if not phrase:
        return 0
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return len(re.findall(pattern, text))


def _confidence(best_score: float, second_score: float, normalized_length: int) -> float:
    margin = best_score - second_score
    base = min(best_score / 8.0, 0.72)
    margin_bonus = min(max(margin, 0) / 6.0, 0.22)
    length_bonus = 0.06 if normalized_length > 300 else 0.0
    return round(min(0.97, base + margin_bonus + length_bonus), 3)


def _json_from_text(text: str) -> Dict[str, object]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)

