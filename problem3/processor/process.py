#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import re
import time
from glob import glob
from datetime import datetime, timezone

STATUS_DIR = "/shared/status"
RAW_DIR = "/shared/raw"
PROCESSED_DIR = "/shared/processed"

FETCH_DONE_FILE = os.path.join(STATUS_DIR, "fetch_complete.json")
PROCESS_DONE_FILE = os.path.join(STATUS_DIR, "process_complete.json")


def strip_html(html_content: str):
    """Remove HTML tags and extract text, links and images via regex."""
    # Remove script and style elements
    html_content = re.sub(r"<script[^>]*>.*?</script>", "", html_content,
                          flags=re.DOTALL | re.IGNORECASE)
    html_content = re.sub(r"<style[^>]*>.*?</style>", "", html_content,
                          flags=re.DOTALL | re.IGNORECASE)

    # Extract links/images BEFORE removing tags
    links = re.findall(r'href=[\'"]?([^\'"\s>]+)', html_content, flags=re.IGNORECASE)
    images = re.findall(r'src=[\'"]?([^\'"\s>]+)', html_content, flags=re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html_content)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text, links, images


def text_statistics(text: str):
    """Compute basic text statistics."""
    # words: group of letters/digits/underscore (ASCII-ish)
    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)

    # sentences: split on ., ?, !
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    sentence_count = len(sentences)

    # paragraphs: split on double newlines OR (fallback) chunks by period groups
    # Since we collapsed whitespace, we approximate paragraphs by large breaks
    # If you prefer, treat every 3+ sentences as a paragraph-like group.
    paragraphs = [p for p in re.split(r"(?:\s{2,}|\n{2,})", text) if p.strip()]
    paragraph_count = len(paragraphs) if paragraphs else max(1, sentence_count // 3)

    avg_word_length = (sum(len(w) for w in words) / word_count) if word_count else 0.0

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "paragraph_count": paragraph_count,
        "avg_word_length": round(avg_word_length, 3),
    }


def process_one_html(html_path: str):
    """Process a single HTML file -> JSON dict."""
    with open(html_path, "r", encoding="utf-8", errors="ignore") as f:
        html = f.read()

    text, links, images = strip_html(html)
    stats = text_statistics(text)

    result = {
        "source_file": os.path.basename(html_path),
        "text": text,
        "statistics": stats,
        "links": links,
        "images": images,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    return result


def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Processor starting", flush=True)

    # 1) Wait for fetch completion marker
    while not os.path.exists(FETCH_DONE_FILE):
        print(f"Waiting for {FETCH_DONE_FILE} ...", flush=True)
        time.sleep(2)

    # 2) Ensure output dirs
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(STATUS_DIR, exist_ok=True)

    # 3) Read all html files from /shared/raw
    html_files = sorted(glob(os.path.join(RAW_DIR, "*.html")))
    print(f"Found {len(html_files)} html files", flush=True)

    processed_files = []
    successes = 0
    failures = 0

    # 4) Process each HTML -> write /shared/processed/page_N.json
    for idx, html_path in enumerate(html_files, 1):
        try:
            data = process_one_html(html_path)
            out_name = os.path.splitext(os.path.basename(html_path))[0] + ".json"
            out_path = os.path.join(PROCESSED_DIR, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            processed_files.append(out_name)
            successes += 1
            print(f"Processed {html_path} -> {out_name}", flush=True)
        except Exception as e:
            failures += 1
            print(f"Failed to process {html_path}: {e}", flush=True)

        time.sleep(0.2)

    # 5) Write process completion marker
    status = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "inputs_detected": len(html_files),
        "processed_success": successes,
        "processed_failed": failures,
        "outputs": processed_files,
    }
    with open(PROCESS_DONE_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now(timezone.utc).isoformat()}] Processor complete", flush=True)


if __name__ == "__main__":
    main()
