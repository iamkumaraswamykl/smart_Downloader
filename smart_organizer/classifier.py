from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
import json
import math
import os
import re

from .config import (
    ARCHIVE_EXTENSIONS,
    DEFAULT_CATEGORIES,
    IMAGE_EXTENSIONS,
    MEDIA_EXTENSIONS,
    PDF_EXTENSIONS,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_EMBEDDING_MODEL,
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
        self._category_embeddings: Dict[str, List[float]] = {}

    def classify(
        self, 
        text: str, 
        path: Path, 
        mime_type: str = "", 
        learned_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> ClassificationResult:
        text = (text or "").strip()

        # 0. Try User Corrections (Learned Patterns) first - Priority 4
        if learned_patterns:
            learned_result = self._try_learned_patterns(text, path, learned_patterns)
            if learned_result:
                return learned_result

        if self.llm_provider:
            # 1. Try LLM (Generative)
            llm_result = self._try_llm(text, path, mime_type)
            if llm_result:
                return llm_result
            
            # 2. Fallback to Embeddings (Semantic Search) if LLM fails
            embed_result = self._classify_with_embeddings(text, path)
            if embed_result:
                return embed_result

        return self._classify_locally(text, path, mime_type)

    def _try_learned_patterns(self, text: str, path: Path, patterns: List[Dict[str, Any]]) -> Optional[ClassificationResult]:
        """Matches current file against historical user corrections."""
        normalized_doc = _normalize_text(f"{path.name} {text[:500]}")
        
        for pattern in patterns:
            pattern_text = pattern.get("text_content", "")
            if not pattern_text:
                continue
                
            normalized_pattern = _normalize_text(pattern_text)
            
            # Simple exact match or very high similarity check
            # In the future, this can use the 'embedding' column if available
            if normalized_pattern in normalized_doc or normalized_doc in normalized_pattern:
                return ClassificationResult(
                    pattern["category"],
                    0.95,
                    "user-learning",
                    f"Matched historical correction for: '{pattern_text[:50]}...'",
                    []
                )
        return None

    def _classify_locally(self, text: str, path: Path, mime_type: str) -> ClassificationResult:
        suffix = path.suffix.lower()
        # Include the filename in the text to be analyzed for strong keyword signals
        combined_text = f"{path.name}\n{text}"
        normalized = _normalize_text(combined_text)
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
        if not self.llm_provider:
            return None

        categories = {name: cfg.get("description", "") for name, cfg in self.categories.items()}
        prompt_data = {
            "file_name": path.name,
            "mime_type": mime_type,
            "categories": categories,
            "content_excerpt": text[:6000],
            "instruction": (
                "Classify this downloaded file into exactly one category from the provided list. "
                "Respond ONLY with a valid JSON object containing: 'category', 'confidence' (0-1), and 'rationale'."
            ),
        }
        prompt_json = json.dumps(prompt_data)

        # 1. Gemini Implementation (Priority)
        if self.llm_provider == "gemini":
            if not GEMINI_API_KEY:
                return None
            try:
                import google.generativeai as genai  # type: ignore
                genai.configure(api_key=GEMINI_API_KEY)
                model = genai.GenerativeModel(GEMINI_MODEL)
                
                response = model.generate_content(
                    prompt_json,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0,
                        max_output_tokens=1024,
                        response_mime_type="application/json",
                    ),
                )
                
                data = _json_from_text(response.text or "{}")
                category = str(data.get("category", "Uncategorized"))
                if category not in self.categories:
                    category = "Uncategorized"
                    
                return ClassificationResult(
                    category,
                    float(data.get("confidence", 0.5)),
                    "gemini-llm",
                    str(data.get("rationale", "Gemini classified the file.")),
                    [],
                )
            except Exception:
                return None

        # 2. OpenAI Implementation (Secondary)
        if self.llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            try:
                from openai import OpenAI  # type: ignore
                client = OpenAI(api_key=api_key)
                
                response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": "You are a professional file organizer. Respond only in JSON."},
                        {"role": "user", "content": prompt_json}
                    ],
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content or "{}"
                data = _json_from_text(content)
                category = str(data.get("category", "Uncategorized"))
                if category not in self.categories:
                    category = "Uncategorized"
                    
                return ClassificationResult(
                    category,
                    float(data.get("confidence", 0.5)),
                    "openai-llm",
                    str(data.get("rationale", "OpenAI classified the file.")),
                    [],
                )
            except Exception:
                return None

        return None

    def _classify_with_embeddings(self, text: str, path: Path) -> Optional[ClassificationResult]:
        """Classifies using Gemini embeddings and cosine similarity."""
        if self.llm_provider != "gemini" or not GEMINI_API_KEY:
            return None

        try:
            import google.generativeai as genai # type: ignore
            genai.configure(api_key=GEMINI_API_KEY)

            # 1. Ensure category embeddings are cached
            if not self._category_embeddings:
                for name, cfg in self.categories.items():
                    desc = str(cfg.get("description", name))
                    keywords = ", ".join([str(k) for k in cfg.get("keywords", [])])
                    target_text = f"{name}: {desc}. Keywords: {keywords}"
                    result = genai.embed_content(
                        model=GEMINI_EMBEDDING_MODEL,
                        content=target_text,
                        task_type="classification"
                    )
                    self._category_embeddings[name] = result['embedding']

            # 2. Get embedding for the document
            doc_text = f"{path.name}\n{text[:2000]}"
            doc_result = genai.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                content=doc_text,
                task_type="classification"
            )
            doc_embedding = doc_result['embedding']

            # 3. Compare and find best match
            best_category = "Uncategorized"
            best_similarity = -1.0

            for name, cat_embedding in self._category_embeddings.items():
                sim = _cosine_similarity(doc_embedding, cat_embedding)
                if sim > best_similarity:
                    best_similarity = sim
                    best_category = name

            confidence = max(0.0, min(1.0, (best_similarity - 0.4) / 0.5))
            if confidence < 0.4:
                return None

            return ClassificationResult(
                best_category,
                round(confidence, 3),
                "gemini-embeddings",
                f"Highest semantic similarity ({best_similarity:.3f}) with {best_category}.",
                []
            )
        except Exception:
            return None


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    magnitude1 = math.sqrt(sum(a * a for a in v1))
    magnitude2 = math.sqrt(sum(a * a for a in v2))
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)


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

