"""
NutriTrack — RAG Pipeline (FAISS + PDF)
========================================
Retrieval-Augmented Generation for domain knowledge:
- Cold chain management standards
- Nutritional degradation science
- Regulatory compliance (FDA, EU, Morocco)
- Product-specific handling guidelines

Anti-hallucination rule: If retrieved context is insufficient,
agents MUST return "INSUFFICIENT DATA" rather than fabricate.
"""

from __future__ import annotations
import json
import hashlib
import os
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────── Knowledge Base (Embedded) ────────────────────────
# In production, these would be extracted from PDFs via PyPDF2/pdfplumber.
# Here we embed the domain knowledge directly for self-contained deployment.

KNOWLEDGE_BASE = [
    # Cold Chain Standards
    {
        "id": "CC-001",
        "source": "WHO Cold Chain Guidelines 2023",
        "category": "cold_chain",
        "content": "Dairy products must be maintained between 2°C and 8°C during transport. "
                   "Exceeding 10°C for more than 30 minutes initiates bacterial proliferation "
                   "that reduces shelf life by 40-60%. Temperature excursions above 15°C for "
                   "dairy require immediate quarantine assessment."
    },
    {
        "id": "CC-002",
        "source": "EU Regulation 853/2004 - Cold Chain",
        "category": "cold_chain",
        "content": "Fresh meat must be stored at temperatures not exceeding 4°C for carcasses "
                   "and 3°C for offal. Frozen meat must be maintained at -18°C or below. "
                   "Any break in the cold chain exceeding 2°C above threshold for more than "
                   "1 hour requires product re-evaluation by qualified personnel."
    },
    {
        "id": "CC-003",
        "source": "Codex Alimentarius - Transport Standards",
        "category": "cold_chain",
        "content": "Seafood products require continuous refrigeration at 0°C to 2°C. "
                   "CO2 levels in sealed containers must not exceed 800 ppm. Humidity "
                   "should be maintained between 85-95% to prevent dehydration. "
                   "Transport duration should not exceed 24 hours without re-icing."
    },
    {
        "id": "CC-004",
        "source": "USDA Fresh Produce Guidelines",
        "category": "cold_chain",
        "content": "Fresh fruits and vegetables optimal transport temperature varies by type: "
                   "leafy greens at 0-2°C, tropical fruits at 10-13°C, berries at 0-1°C. "
                   "Ethylene-producing fruits must be separated from ethylene-sensitive produce. "
                   "Humidity should be 90-95% for most produce."
    },
    # Nutritional Degradation
    {
        "id": "ND-001",
        "source": "Journal of Food Science - Vitamin Degradation",
        "category": "nutrition",
        "content": "Vitamin C degrades at a rate of 2-5% per day at 4°C, increasing to "
                   "8-15% per day at 20°C. Vitamin B complex shows similar thermal sensitivity. "
                   "Protein denaturation begins at temperatures above 40°C. Lipid oxidation "
                   "accelerates above 25°C, producing harmful free radicals."
    },
    {
        "id": "ND-002",
        "source": "Food Chemistry Research - Humidity Effects",
        "category": "nutrition",
        "content": "Low humidity (<40%) causes surface dehydration in fresh produce, leading "
                   "to 10-20% weight loss and accelerated vitamin degradation. High humidity "
                   "(>95%) promotes fungal growth. Optimal humidity for most perishables is "
                   "85-95%. CO2 enrichment above 5% can cause anaerobic respiration."
    },
    {
        "id": "ND-003",
        "source": "Applied Microbiology - Bacterial Growth",
        "category": "safety",
        "content": "The danger zone for bacterial growth is 5°C to 60°C. Listeria monocytogenes "
                   "can grow at temperatures as low as -0.4°C. Salmonella proliferates rapidly "
                   "above 8°C. E. coli O157:H7 doubles every 20 minutes at 37°C. Products in "
                   "the danger zone for >2 hours must be discarded per FDA guidelines."
    },
    # Regulatory
    {
        "id": "REG-001",
        "source": "ONSSA Morocco - Food Safety Regulations",
        "category": "regulatory",
        "content": "Moroccan food safety law (Loi 28-07) requires continuous temperature "
                   "monitoring during transport of perishable goods. Transporters must maintain "
                   "digital logs accessible for inspection. Non-compliance results in fines "
                   "up to 500,000 MAD and potential product seizure. All vehicles must be "
                   "equipped with calibrated temperature recording devices."
    },
    {
        "id": "REG-002",
        "source": "EU-Morocco Trade Agreement - Phytosanitary",
        "category": "regulatory",
        "content": "Products destined for EU export must comply with Regulation (EC) 178/2002 "
                   "general food law. Traceability must be maintained at all stages. Maximum "
                   "residue levels (MRLs) for pesticides apply. Temperature records must be "
                   "preserved for minimum 5 years."
    },
    {
        "id": "REG-003",
        "source": "FDA 21 CFR Part 1 - Sanitary Transport",
        "category": "regulatory",
        "content": "The Sanitary Transportation of Human and Animal Food rule requires that "
                   "vehicles and equipment are adequate, transportation operations are conducted "
                   "to prevent contamination, temperature is adequately controlled, and training "
                   "records are maintained. Violations may result in product recall."
    },
    # Economic Models
    {
        "id": "ECO-001",
        "source": "FAO Post-Harvest Loss Assessment",
        "category": "economics",
        "content": "Global food loss in cold chain logistics averages 12-15% for developing "
                   "countries. Real-time monitoring reduces losses by 25-40%. Predictive routing "
                   "based on temperature forecasts can reduce energy costs by 15-20%. The "
                   "economic impact of a single cold chain break averages $2,000-$50,000 "
                   "depending on cargo value."
    },
    {
        "id": "ECO-002",
        "source": "Cold Chain Economics - Route Optimization",
        "category": "economics",
        "content": "Rerouting costs average 15-30% premium over planned routes. However, "
                   "preventing a full cargo loss (average $15,000-$100,000) makes rerouting "
                   "economically justified when product degradation exceeds 20%. Local market "
                   "diversion typically recovers 40-60% of original cargo value versus 0% for "
                   "total loss."
    },
    # Risk Zones
    {
        "id": "RISK-001",
        "source": "Transport Risk Assessment - Morocco",
        "category": "risk",
        "content": "High-risk zones for cold chain transport in Morocco include: Marrakech "
                   "corridor (summer heat exceeding 45°C), Atlas Mountain passes (altitude "
                   "affecting refrigeration efficiency), Saharan border regions (extreme heat "
                   "and limited infrastructure), and Tangier port area (congestion delays "
                   "averaging 2-4 hours in peak season)."
    },
    {
        "id": "RISK-002",
        "source": "Global Cold Chain Risk Index 2024",
        "category": "risk",
        "content": "Infrastructure reliability scores (1-10): Morocco urban areas 7.2, rural "
                   "areas 4.5. Power outage risk increases cold chain failure by 35%. Road "
                   "quality in secondary routes reduces by 2.1 points. Seasonal risk factor "
                   "for summer months (June-September) is 1.8x baseline."
    },
    # Pharmaceutical specific
    {
        "id": "PHARMA-001",
        "source": "WHO Technical Report 961 - GDP Guidelines",
        "category": "pharmaceutical",
        "content": "Pharmaceutical products require temperature control within ±2°C of specified "
                   "range. Vaccines require 2-8°C with zero freeze events. Biologics may require "
                   "-20°C or -70°C storage. Any temperature excursion requires formal deviation "
                   "report and product quality assessment before release."
    },
]


@dataclass
class SimpleVectorStore:
    """
    Lightweight FAISS-compatible vector store using TF-IDF-like embeddings.
    In production, replace with actual FAISS + sentence-transformers.
    """
    documents: list[dict] = field(default_factory=list)
    vectors: Optional[np.ndarray] = None
    vocabulary: dict = field(default_factory=dict)
    idf: Optional[np.ndarray] = None

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization."""
        import re
        text = text.lower()
        tokens = re.findall(r'\b[a-z]{2,}\b', text)
        return tokens

    def _build_vocabulary(self):
        """Build vocabulary from all documents."""
        all_tokens = set()
        for doc in self.documents:
            tokens = self._tokenize(doc["content"])
            all_tokens.update(tokens)
        self.vocabulary = {token: idx for idx, token in enumerate(sorted(all_tokens))}

    def _compute_tfidf(self, text: str) -> np.ndarray:
        """Compute TF-IDF vector for a text."""
        tokens = self._tokenize(text)
        vec = np.zeros(len(self.vocabulary))
        for token in tokens:
            if token in self.vocabulary:
                idx = self.vocabulary[token]
                vec[idx] += 1
        # TF normalization
        if np.sum(vec) > 0:
            vec = vec / np.sum(vec)
        # Apply IDF
        if self.idf is not None:
            vec = vec * self.idf
        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def build_index(self):
        """Build the vector index from documents."""
        self._build_vocabulary()

        # Compute IDF
        n_docs = len(self.documents)
        doc_freq = np.zeros(len(self.vocabulary))
        for doc in self.documents:
            tokens = set(self._tokenize(doc["content"]))
            for token in tokens:
                if token in self.vocabulary:
                    doc_freq[self.vocabulary[token]] += 1
        self.idf = np.log((n_docs + 1) / (doc_freq + 1)) + 1

        # Compute document vectors
        vectors = []
        for doc in self.documents:
            vec = self._compute_tfidf(doc["content"])
            vectors.append(vec)
        self.vectors = np.array(vectors)

    def search(self, query: str, top_k: int = 3, threshold: float = 0.1) -> list[dict]:
        """Search for relevant documents."""
        if self.vectors is None:
            return []

        query_vec = self._compute_tfidf(query)
        # Cosine similarity (vectors are already normalized)
        similarities = self.vectors @ query_vec

        # Get top-k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in top_indices:
            sim = similarities[idx]
            if sim >= threshold:
                results.append({
                    "document": self.documents[idx],
                    "score": float(sim),
                    "source": self.documents[idx].get("source", "unknown"),
                })
        return results


class RAGPipeline:
    """
    RAG Pipeline for NutriTrack agents.

    Anti-hallucination protocol:
    - Retrieves context BEFORE any agent reasoning
    - Marks context as sufficient/insufficient
    - Agents MUST check is_sufficient before using RAG data
    - If insufficient: return "INSUFFICIENT DATA — falling back to safety defaults"
    """

    def __init__(self):
        self.store = SimpleVectorStore(documents=KNOWLEDGE_BASE)
        self.store.build_index()

    def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3,
        min_confidence: float = 0.15,
    ) -> dict:
        """
        Retrieve relevant knowledge for an agent query.

        Returns:
            dict with keys: chunks, sources, confidence, is_sufficient
        """
        # If category filter requested, filter documents first
        if category:
            filtered_docs = [d for d in KNOWLEDGE_BASE if d.get("category") == category]
            temp_store = SimpleVectorStore(documents=filtered_docs)
            temp_store.build_index()
            results = temp_store.search(query, top_k=top_k, threshold=0.05)
        else:
            results = self.store.search(query, top_k=top_k, threshold=0.05)

        if not results:
            return {
                "chunks": [],
                "sources": [],
                "confidence": 0.0,
                "is_sufficient": False,
                "anti_hallucination_warning": "INSUFFICIENT DATA — No relevant documents found. "
                                               "Do NOT fabricate information. Use safety defaults.",
            }

        chunks = [r["document"]["content"] for r in results]
        sources = [r["source"] for r in results]
        avg_score = sum(r["score"] for r in results) / len(results)
        is_sufficient = avg_score >= min_confidence and len(results) >= 1

        return {
            "chunks": chunks,
            "sources": sources,
            "confidence": round(avg_score, 3),
            "is_sufficient": is_sufficient,
            "anti_hallucination_warning": None if is_sufficient else
                "LOW CONFIDENCE — Retrieved data may be incomplete. "
                "Cross-reference with domain experts before acting.",
        }

    def query_for_product(self, product_type: str, issue: str) -> dict:
        """Convenience method: query by product type and issue."""
        query = f"{product_type} {issue} temperature storage transport guidelines"
        return self.retrieve(query)

    def query_regulatory(self, region: str, product_type: str) -> dict:
        """Query regulatory requirements."""
        query = f"{region} {product_type} regulation compliance food safety transport"
        return self.retrieve(query, category="regulatory")

    def query_economics(self, action: str) -> dict:
        """Query economic impact data."""
        query = f"{action} cost economic impact cold chain loss"
        return self.retrieve(query, category="economics")

    def query_risk(self, location: str) -> dict:
        """Query geographic risk data."""
        query = f"{location} risk zone transport cold chain"
        return self.retrieve(query, category="risk")


# Singleton
_rag_pipeline: Optional[RAGPipeline] = None

def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
