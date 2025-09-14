#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import time
from glob import glob
from collections import Counter
from itertools import combinations
from datetime import datetime, timezone

STATUS_DIR = "/shared/status"
PROCESSED_DIR = "/shared/processed"
ANALYSIS_DIR = "/shared/analysis"

PROCESS_DONE_FILE = os.path.join(STATUS_DIR, "process_complete.json")
FINAL_REPORT_FILE = os.path.join(ANALYSIS_DIR, "final_report.json")


# ----------------------- helpers -----------------------
def tokenize_words(text: str):
    """Lowercase tokenization on word characters."""
    return [w.lower() for w in re.findall(r"\b\w+\b", text)]


def split_sentences(text: str):
    """Very simple sentence splitter by punctuation."""
    return [s for s in re.split(r"[.!?]+", text) if s.strip()]


def ngrams(words, n):
    """Return contiguous n-grams joined by a single space."""
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


def jaccard_similarity(doc1_words, doc2_words) -> float:
    """Calculate Jaccard similarity between two documents."""
    set1 = set(doc1_words)
    set2 = set(doc2_words)
    union = set1.union(set2)
    return (len(set1.intersection(set2)) / len(union)) if union else 0.0


# ----------------------- core --------------------------
def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer starting", flush=True)

    # 1) Wait for /shared/status/process_complete.json
    while not os.path.exists(PROCESS_DONE_FILE):
        print(f"Waiting for {PROCESS_DONE_FILE} ...", flush=True)
        time.sleep(2)

    # 2) Read all processed JSON files
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    processed_files = sorted(glob(os.path.join(PROCESSED_DIR, "*.json")))
    print(f"Found {len(processed_files)} processed JSON files", flush=True)

    docs = []              # [{name, words}]
    all_words = []         # corpus words
    all_bigrams = []       # corpus bigrams
    all_trigrams = []      # corpus trigrams
    total_word_chars = 0
    total_sentences = 0

    for path in processed_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Skip unreadable file {path}: {e}", flush=True)
            continue

        text = data.get("text", "") or ""
        words = tokenize_words(text)
        sentences = split_sentences(text)

        docs.append({
            "name": os.path.basename(path),
            "words": words,
        })

        # accumulate corpus-level stats
        all_words.extend(words)
        total_word_chars += sum(len(w) for w in words)
        total_sentences += len(sentences)
        all_bigrams.extend(ngrams(words, 2))
        all_trigrams.extend(ngrams(words, 3))

    # Handle empty corpus safely
    total_words = len(all_words)
    unique_words = len(set(all_words))

    if total_words == 0:
        report = {
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "documents_processed": len(docs),
            "total_words": 0,
            "unique_words": 0,
            "top_100_words": [],
            "document_similarity": [],
            "top_bigrams": [],
            "readability": {
                "avg_sentence_length": 0.0,
                "avg_word_length": 0.0,
                "complexity_score": 0.0
            }
        }
        with open(FINAL_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer complete (empty corpus)", flush=True)
        return

    # 3) Compute global statistics

    # 3.1 Word frequency (top 100)
    word_counter = Counter(all_words)
    top_100_words = [
        {"word": w, "count": c, "frequency": round(c / total_words, 6)}
        for w, c in word_counter.most_common(100)
    ]

    # 3.2 Document similarity (pairwise Jaccard)
    similarities = []
    for d1, d2 in combinations(docs, 2):
        sim = jaccard_similarity(d1["words"], d2["words"])
        similarities.append({
            "doc1": d1["name"],
            "doc2": d2["name"],
            "similarity": round(sim, 6)
        })

    # 3.3 N-grams (bigrams & trigrams)
    bigram_counter = Counter(all_bigrams)
    trigram_counter = Counter(all_trigrams)
    top_bigrams = [{"bigram": g, "count": c} for g, c in bigram_counter.most_common(50)]
    top_trigrams = [{"trigram": g, "count": c} for g, c in trigram_counter.most_common(50)]

    # 3.4 Readability metrics (corpus-level)
    avg_sentence_length = (total_words / total_sentences) if total_sentences else float(total_words)
    avg_word_length = total_word_chars / total_words if total_words else 0.0
    complexity_score = round(avg_sentence_length * avg_word_length, 6)

    # 4) Save final report
    report = {
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "documents_processed": len(docs),
        "total_words": total_words,
        "unique_words": unique_words,
        "top_100_words": top_100_words,
        "document_similarity": similarities,
        "top_bigrams": top_bigrams,
        "top_trigrams": top_trigrams,
        "readability": {
            "avg_sentence_length": round(avg_sentence_length, 6),
            "avg_word_length": round(avg_word_length, 6),
            "complexity_score": complexity_score
        }
    }

    with open(FINAL_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now(timezone.utc).isoformat()}] Analyzer complete", flush=True)


if __name__ == "__main__":
    main()
