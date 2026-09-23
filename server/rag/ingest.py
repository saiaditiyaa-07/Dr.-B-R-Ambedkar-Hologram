"""
RAG Ingestion Pipeline for Dr. B. R. Ambedkar Writings & Speeches
==================================================================
Extracts text from PDFs, chunks it, generates embeddings, and builds
a FAISS vector index.

Usage:
    python server/rag/ingest.py

Rebuilds the entire vector index from scratch.
"""

import os
import sys
import json
import pickle
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ── Paths ────────────────────────────────────────────────────
SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WRITINGS_DIR = os.path.join(SERVER_DIR, "data", "ambedkar", "writings")
VECTORSTORE_DIR = os.path.join(SERVER_DIR, "data", "ambedkar", "vectorstore")
METADATA_PATH = os.path.join(SERVER_DIR, "data", "ambedkar", "metadata.json")

FAISS_INDEX_PATH = os.path.join(VECTORSTORE_DIR, "index.faiss")
CHUNKS_PATH = os.path.join(VECTORSTORE_DIR, "chunks.pkl")

# ── Chunking Config ──────────────────────────────────────────
CHUNK_SIZE = 3000       # ~750 tokens worth of characters (700-800 tokens target)
CHUNK_OVERLAP = 400     # ~100 tokens overlap
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def is_valid_pdf(filepath):
    """Check if a file starts with the PDF signature %PDF."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF")
    except Exception:
        return False


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF file using PyMuPDF.
    Returns list of (page_number, text) tuples.
    Detects scanned/image-only pages.
    """
    if not is_valid_pdf(pdf_path):
        raise ValueError(f"File {pdf_path} failed %PDF signature check.")

    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages = []
    empty_pages = 0
    total_pages = len(doc)

    for page_num in range(total_pages):
        page = doc.load_page(page_num)
        text = page.get_text("text")

        if text and text.strip():
            pages.append((page_num + 1, text.strip()))  # 1-indexed page numbers
        else:
            empty_pages += 1

    doc.close()

    return pages, total_pages, empty_pages


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into overlapping chunks using paragraph/sentence boundaries.
    Falls back to character splitting if no good boundaries found.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:])
            break

        # Try to break at paragraph boundary
        break_point = text.rfind("\n\n", start + chunk_size // 2, end)
        if break_point == -1:
            # Try sentence boundary
            break_point = text.rfind(". ", start + chunk_size // 2, end)
            if break_point != -1:
                break_point += 2  # Include the period and space
        if break_point == -1:
            # Try newline
            break_point = text.rfind("\n", start + chunk_size // 2, end)
        if break_point == -1:
            # Try space
            break_point = text.rfind(" ", start + chunk_size // 2, end)
        if break_point == -1:
            # Hard break
            break_point = end

        chunks.append(text[start:break_point])
        prev_start = start
        start = break_point - overlap  # Overlap for context continuity

        # Prevent infinite loop
        if start <= prev_start:
            start = break_point

    return [c.strip() for c in chunks if c.strip()]


def build_chunks_from_pdfs():
    """
    Process all PDFs and build a list of text chunks with metadata.
    """
    if not os.path.exists(WRITINGS_DIR):
        print(f"ERROR: PDF directory not found: {WRITINGS_DIR}")
        print("Run the PDF downloader first: python server/data/ambedkar/download_pdfs.py")
        sys.exit(1)

    pdf_files = sorted([f for f in os.listdir(WRITINGS_DIR) if f.lower().endswith(".pdf")])
    if not pdf_files:
        print(f"ERROR: No PDF files found in {WRITINGS_DIR}")
        print("Run the PDF downloader first: python server/data/ambedkar/download_pdfs.py")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files to process.\n")

    all_chunks = []  # Each: {"text": ..., "source": ..., "page": ..., "collection": ...}
    scanned_files = []
    total_pages_processed = 0
    total_empty_pages = 0

    for pdf_file in pdf_files:
        pdf_path = os.path.join(WRITINGS_DIR, pdf_file)
        print(f"  📄 Processing: {pdf_file}...", end="", flush=True)

        try:
            pages, total_pages, empty_pages = extract_text_from_pdf(pdf_path)
            total_pages_processed += total_pages
            total_empty_pages += empty_pages

            if not pages:
                print(f" ⚠️ SCANNED/NO TEXT ({total_pages} pages, 0 extractable)")
                scanned_files.append(pdf_file)
                continue

            if empty_pages > total_pages * 0.8:
                print(f" ⚠️ MOSTLY SCANNED ({total_pages} pages, {len(pages)} with text)")
                scanned_files.append(pdf_file)

            # Chunk each page's text
            file_chunks = 0
            for page_num, page_text in pages:
                # Clean up the text
                page_text = page_text.replace("\x00", "")  # Remove null bytes
                # Normalize whitespace but preserve paragraph breaks
                lines = page_text.split("\n")
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line:
                        cleaned_lines.append(line)
                    else:
                        cleaned_lines.append("")
                page_text = "\n".join(cleaned_lines)

                if len(page_text.strip()) < 50:
                    continue  # Skip nearly empty pages

                chunks = chunk_text(page_text)
                for chunk in chunks:
                    if len(chunk.strip()) < 50:
                        continue  # Skip tiny chunks

                    all_chunks.append({
                        "text": chunk,
                        "source": pdf_file,
                        "page": page_num,
                        "collection": "Dr. Ambedkar Writings and Speeches",
                    })
                    file_chunks += 1

            print(f" ✓ {len(pages)}/{total_pages} pages → {file_chunks} chunks")

        except Exception as e:
            print(f" ❌ ERROR: {e}")
            continue

    print(f"\n{'─' * 60}")
    print(f"  Total PDFs processed:    {len(pdf_files)}")
    print(f"  Total pages scanned:     {total_pages_processed}")
    print(f"  Pages with text:         {total_pages_processed - total_empty_pages}")
    print(f"  Empty/scanned pages:     {total_empty_pages}")
    print(f"  Total chunks created:    {len(all_chunks)}")

    if scanned_files:
        print(f"\n  ⚠️ Scanned/image-only PDFs (no extractable text):")
        for sf in scanned_files:
            print(f"    • {sf}")

    return all_chunks


def build_faiss_index(chunks):
    """
    Generate embeddings and build the FAISS index.
    """
    if not chunks:
        print("\nERROR: No chunks to index!")
        sys.exit(1)

    print(f"\n{'═' * 60}")
    print(f"  Building FAISS index with {len(chunks)} chunks...")
    print(f"  Embedding model: {EMBEDDING_MODEL}")
    print(f"{'═' * 60}\n")

    # Import heavy dependencies only when needed
    from sentence_transformers import SentenceTransformer
    import numpy as np
    import faiss

    # Load embedding model
    print("  Loading embedding model...", end="", flush=True)
    start = time.time()
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f" done ({time.time() - start:.1f}s)")

    # Generate embeddings
    print(f"  Generating embeddings for {len(chunks)} chunks...", end="", flush=True)
    start = time.time()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
    embeddings = np.array(embeddings, dtype=np.float32)
    print(f"  done ({time.time() - start:.1f}s)")

    # Normalize embeddings for cosine similarity
    faiss.normalize_L2(embeddings)

    # Build FAISS index (Inner Product = cosine similarity after normalization)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)

    print(f"\n  Index built: {index.ntotal} vectors, {dimension} dimensions")

    # Save index and chunk metadata
    os.makedirs(VECTORSTORE_DIR, exist_ok=True)

    faiss.write_index(index, FAISS_INDEX_PATH)
    print(f"  Saved FAISS index: {FAISS_INDEX_PATH}")

    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)
    print(f"  Saved chunk metadata: {CHUNKS_PATH}")

    return index, chunks


def main():
    print("=" * 60)
    print("  Dr. B. R. Ambedkar — RAG Index Builder")
    print("=" * 60)
    print()

    # Step 1: Extract and chunk PDFs
    chunks = build_chunks_from_pdfs()

    if not chunks:
        print("\n❌ No text chunks were extracted from any PDF.")
        print("   This could mean all PDFs are scanned images.")
        print("   OCR support is not yet implemented.")
        sys.exit(1)

    # Step 2: Build FAISS index
    index, stored_chunks = build_faiss_index(chunks)

    print(f"\n{'═' * 60}")
    print(f"  ✅ RAG INDEX BUILT SUCCESSFULLY")
    print(f"     Chunks indexed: {len(stored_chunks)}")
    print(f"     FAISS index:    {FAISS_INDEX_PATH}")
    print(f"     Metadata:       {CHUNKS_PATH}")
    print(f"{'═' * 60}")
    print(f"\n  The server will now use this index for retrieval.")
    print(f"  Restart the server to load the new index.")


if __name__ == "__main__":
    main()
