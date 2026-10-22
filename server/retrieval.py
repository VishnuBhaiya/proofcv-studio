"""Semantic job retrieval with an inspectable offline test backend."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np


TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")

DOMAIN_TERMS = (
    "python", "java", "sql", "machine learning", "deep learning", "computer vision",
    "opencv", "tensorflow", "pytorch", "nlp", "natural language", "rag", "retrieval",
    "llm", "agent", "agentic", "data science", "pandas", "numpy", "scikit-learn",
    "docker", "cloud", "aws", "azure", "api", "rest", "backend", "software",
    "security", "cybersecurity", "testing", "git", "mlops", "recommendation",
    "multimodal", "classification", "object detection", "analytics", "research",
)


class EmbeddingBackend(Protocol):
    name: str

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        """Return one normalised vector for every text."""


class SentenceTransformerBackend:
    name = "sentence-transformers"

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "Install sentence-transformers to run the assessed semantic retrieval mode."
                ) from error
            # Use the installed cache first; an uncached installation can download
            # the model explicitly. Never substitute a lexical ranker silently.
            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except OSError:
                self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        matrix = self._load().encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(matrix, dtype=np.float32)


class InspectableHashEmbeddingBackend:
    """Small offline vectoriser used for tests and no-key demonstrations.

    It is intentionally labelled and never presented as the assessed semantic
    model. Domain-term dimensions make its behaviour inspectable, while hashed
    token dimensions prevent fixed or hard-coded job rankings.
    """

    name = "offline-inspectable-vectors"

    def __init__(self, dimensions: int = 256):
        if dimensions < len(DOMAIN_TERMS) + 32:
            raise ValueError("Embedding dimensions are too small")
        self.dimensions = dimensions

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        domain_offset = len(DOMAIN_TERMS)
        for row, original in enumerate(texts):
            text = str(original).lower()
            for index, term in enumerate(DOMAIN_TERMS):
                if term in text:
                    matrix[row, index] += 2.0 + min(2.0, text.count(term) * 0.25)
            for token in TOKEN_RE.findall(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = domain_offset + int.from_bytes(digest, "little") % (
                    self.dimensions - domain_offset
                )
                matrix[row, bucket] += 1.0
            norm = float(np.linalg.norm(matrix[row]))
            if norm:
                matrix[row] /= norm
        return matrix


@dataclass
class RetrievalResult:
    rank: int
    score: float
    document_id: str
    title: str
    location: str | None
    job_type: str | None
    excerpt: str
    job: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "score": round(self.score, 4),
            "document_id": self.document_id,
            "title": self.title,
            "location": self.location,
            "job_type": self.job_type,
            "excerpt": self.excerpt,
            "job": self.job,
        }


def build_job_text(job: dict[str, Any]) -> str:
    benefits = "; ".join(str(item) for item in job.get("benefits") or [])
    return "\n".join(
        [
            f"Document ID: {job['document_id']}",
            f"Title: {job['title']}",
            f"Location: {job.get('location') or ''}",
            f"Job type: {job.get('job_type') or ''}",
            f"Description: {job['description']}",
            f"Benefits: {benefits}",
        ]
    )


def flatten_profile_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        preferred = ("title", "name", "role", "description", "summary", "evidence", "outcome")
        values = [str(item[key]) for key in preferred if item.get(key)]
        if values:
            return " | ".join(values)
        return " | ".join(str(value) for value in item.values() if value)
    return str(item)


def build_profile_query(profile: dict[str, Any]) -> str:
    parts = [
        "Target roles: " + "; ".join(map(str, profile.get("target_roles") or [])),
        "Confirmed skills: " + "; ".join(map(str, profile.get("technical_skills") or [])),
        "Skill evidence: " + "; ".join(flatten_profile_item(x) for x in profile.get("skill_evidence") or []),
        "Education: " + "; ".join(flatten_profile_item(x) for x in profile.get("education") or []),
        "Experience: " + "; ".join(flatten_profile_item(x) for x in profile.get("experience") or []),
        "Projects: " + "; ".join(flatten_profile_item(x) for x in profile.get("projects") or []),
        "Achievements: " + "; ".join(flatten_profile_item(x) for x in profile.get("achievements") or []),
    ]
    return "\n".join(part for part in parts if not part.endswith(": "))


def evidence_excerpt(description: str, query: str, max_chars: int = 360) -> str:
    clean = re.sub(r"\s+", " ", str(description)).strip()
    if len(clean) <= max_chars:
        return clean
    query_terms = {
        token.lower() for token in TOKEN_RE.findall(query) if len(token) > 3
    }
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: sum(term in pair[1].lower() for term in query_terms),
        reverse=True,
    )
    selected = ranked[0][1] if ranked else sentences[0]
    if len(selected) > max_chars:
        return selected[: max_chars - 3].rsplit(" ", 1)[0] + "..."
    return selected


class JobRetriever:
    def __init__(self, jobs: list[dict[str, Any]], backend: EmbeddingBackend):
        if not jobs:
            raise ValueError("At least one job is required")
        ids = [str(job["document_id"]) for job in jobs]
        if len(ids) != len(set(ids)):
            raise ValueError("Job document_id values must be unique")
        self.jobs = jobs
        self.backend = backend
        self._job_texts = [build_job_text(job) for job in jobs]
        self._vectors: np.ndarray | None = None

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def build_index(self) -> np.ndarray:
        if self._vectors is None:
            vectors = np.asarray(self.backend.encode(self._job_texts), dtype=np.float32)
            if vectors.shape[0] != len(self.jobs):
                raise ValueError("Embedding backend returned the wrong number of vectors")
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._vectors = vectors / norms
        return self._vectors

    def search(self, profile: dict[str, Any], top_k: int = 3) -> dict[str, Any]:
        if top_k != 3:
            raise ValueError("Assessment retrieval must return exactly three jobs")
        query = build_profile_query(profile)
        if not query.strip():
            raise ValueError("The confirmed profile does not contain searchable evidence")
        job_vectors = self.build_index()
        query_vector = np.asarray(self.backend.encode([query]), dtype=np.float32)
        if query_vector.shape[0] != 1:
            raise ValueError("Embedding backend returned an invalid query vector")
        norm = float(np.linalg.norm(query_vector[0])) or 1.0
        scores = job_vectors @ (query_vector[0] / norm)
        positions = np.argsort(-scores)[:top_k]
        results = []
        for rank, position in enumerate(positions, 1):
            job = self.jobs[int(position)]
            results.append(
                RetrievalResult(
                    rank=rank,
                    score=float(scores[int(position)]),
                    document_id=str(job["document_id"]),
                    title=str(job["title"]),
                    location=job.get("location"),
                    job_type=job.get("job_type"),
                    excerpt=evidence_excerpt(job["description"], query),
                    job=job,
                ).as_dict()
            )
        return {
            "query": query,
            "embedding_backend": self.backend_name,
            "indexed_documents": len(self.jobs),
            "results": results,
        }
