"""
RAG Retriever for Dr. B. R. Ambedkar Writings & Speeches
=========================================================
Loads the FAISS vector index and provides query-time retrieval.

Usage:
    from rag.retriever import retrieve, format_context
    chunks = retrieve("What did Ambedkar say about caste?", top_k=5)
    context = format_context(chunks)
"""

import os
import sys
import pickle
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTORSTORE_DIR = os.path.join(SERVER_DIR, "data", "ambedkar", "vectorstore")
FAISS_INDEX_PATH = os.path.join(VECTORSTORE_DIR, "index.faiss")
CHUNKS_PATH = os.path.join(VECTORSTORE_DIR, "chunks.pkl")

# Lazy-loaded globals
_index = None
_chunks = None
_model = None

# Same model used during ingestion
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Flag to prevent double-loading in concurrent startup
_preloading = False


def _load_index():
    """Lazily load the FAISS index and chunk metadata."""
    global _index, _chunks

    if _index is not None and _chunks is not None:
        return True

    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(CHUNKS_PATH):
        print(f"[RAG Retriever] ⚠️ Vector index not found at {VECTORSTORE_DIR}")
        print(f"[RAG Retriever] Run 'python server/rag/ingest.py' to build the index.")
        return False

    try:
        import faiss
        _index = faiss.read_index(FAISS_INDEX_PATH)

        with open(CHUNKS_PATH, "rb") as f:
            _chunks = pickle.load(f)

        print(f"[RAG Retriever] ✓ Loaded FAISS index: {_index.ntotal} vectors")
        print(f"[RAG Retriever] ✓ Loaded {len(_chunks)} chunk metadata entries")
        return True

    except Exception as e:
        print(f"[RAG Retriever] ❌ Failed to load index: {e}")
        return False


def _load_model():
    """Lazily load the embedding model."""
    global _model

    if _model is not None:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
        print(f"[RAG Retriever] Loading embedding model: {EMBEDDING_MODEL}...")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[RAG Retriever] ✓ Embedding model loaded.")
        return _model
    except Exception as e:
        print(f"[RAG Retriever] ❌ Failed to load embedding model: {e}")
        return None


def is_available():
    """Check if the RAG index is available and ready."""
    return _load_index()


def preload():
    """
    Eagerly load both the FAISS index AND embedding model.
    Call this once at server startup so the first user request is instant.
    Returns True if everything loaded successfully.
    """
    global _preloading
    if _preloading:
        return False
    _preloading = True
    try:
        print("[RAG Retriever] Pre-warming FAISS index and embedding model...")
        idx_ok = _load_index()
        model_ok = _load_model() is not None
        if idx_ok and model_ok:
            print("[RAG Retriever] ✓ Pre-warm complete — first request will be fast.")
        else:
            print("[RAG Retriever] ⚠️ Pre-warm incomplete — check FAISS index / embedding model.")
        return idx_ok and model_ok
    except Exception as e:
        print(f"[RAG Retriever] ❌ Pre-warm failed: {e}")
        return False
    finally:
        _preloading = False


def retrieve(query, top_k=5):
    """
    Retrieve the top-K most relevant document chunks for a query.

    Returns a list of dicts:
    [
        {
            "text": "...",
            "source": "Volume_17_01.pdf",
            "page": 142,
            "collection": "Dr. Ambedkar Writings and Speeches",
            "score": 0.85
        },
        ...
    ]
    """
    if not _load_index():
        return []

    model = _load_model()
    if model is None:
        return []

    import faiss

    try:
        # Encode the query
        query_embedding = model.encode([query])
        query_embedding = np.array(query_embedding, dtype=np.float32)
        faiss.normalize_L2(query_embedding)

        # Search
        scores, indices = _index.search(query_embedding, min(top_k, _index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(_chunks):
                continue
            chunk = _chunks[idx]
            results.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "page": chunk["page"],
                "collection": chunk["collection"],
                "score": float(score),
            })

        return results

    except Exception as e:
        print(f"[RAG Retriever] ❌ Retrieval error: {e}")
        return []


def format_context(chunks):
    """
    Format retrieved chunks into a context block for the LLM prompt.
    """
    if not chunks:
        return "No relevant source material found in the archive."

    lines = ["RETRIEVED SOURCE MATERIAL:\n"]
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", "Unknown")
        page = chunk.get("page", "?")
        text = chunk.get("text", "").strip()

        # Parse volume info from filename
        vol_str = source.replace("Volume_", "").replace(".pdf", "")
        if "_" in vol_str:
            parts = vol_str.split("_")
            try:
                volume_label = f"Volume {int(parts[0])}, Part {int(parts[1])}"
            except (ValueError, IndexError):
                volume_label = source
        else:
            try:
                volume_label = f"Volume {int(vol_str)}"
            except ValueError:
                volume_label = source

        lines.append(f"[Source {i}] {volume_label}, Page {page}")
        lines.append(f"File: {source}")
        lines.append(f"{text}")
        lines.append("")

    return "\n".join(lines)


def format_sources(chunks):
    """
    Format retrieved chunks into a sources list for the API response.
    Does not expose internal vector IDs.
    """
    sources = []
    seen = set()

    for chunk in chunks:
        source = chunk.get("source", "Unknown")
        page = chunk.get("page", "?")

        # Parse volume label
        vol_str = source.replace("Volume_", "").replace(".pdf", "")
        if "_" in vol_str:
            parts = vol_str.split("_")
            try:
                volume_label = f"Volume {int(parts[0])}, Part {int(parts[1])}"
            except (ValueError, IndexError):
                volume_label = source
        else:
            try:
                volume_label = f"Volume {int(vol_str)}"
            except ValueError:
                volume_label = source

        key = f"{source}:{page}"
        if key not in seen:
            seen.add(key)
            sources.append({
                "volume": volume_label,
                "page": page,
                "source": source,
            })

    return sources
