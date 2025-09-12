#!/usr/bin/env python3
"""
fetch_and_process.py
Fetch URLs and compute response statistics.

Usage:
    python fetch_and_process.py <input_urls_file> <output_dir>
"""

import sys
import os
import json
import time
import re
import datetime
from urllib import request, error

# -------- Helpers --------

def iso_utc_now() -> str:
    """Return ISO-8601 UTC timestamp with 'Z' suffix (seconds precision)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def count_words(text: str) -> int:
    """Count words as any sequence of alphanumeric characters."""
    return len(re.findall(r'[A-Za-z0-9]+', text))

def ensure_outdir(path: str) -> None:
    """Create output directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def parse_charset(content_type: str) -> str:
    """Extract charset from Content-Type; default to utf-8."""
    if not content_type:
        return "utf-8"
    m = re.search(r'charset=([^\s;]+)', content_type, re.I)
    return m.group(1) if m else "utf-8"

# -------- Core fetch logic --------

def fetch_one(url: str, timeout: int = 10) -> dict:
    """Fetch a single URL with GET using urllib.request."""
    start_ns = time.monotonic_ns()
    status = 0
    content_len = 0
    word_count = None
    err_msg = None

    req = request.Request(url=url, method="GET",
                          headers={"User-Agent": "Homework-HTTP-Fetcher/1.0 (urllib)"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            status = resp.getcode() or 0
            content_len = len(data)
            ctype = resp.headers.get("Content-Type", "")
            if "text" in ctype.lower():
                charset = parse_charset(ctype)
                text = data.decode(charset, errors="replace")
                word_count = count_words(text)
    except error.HTTPError as e:
        status = e.code or 0
        try:
            data = e.read() or b""
            content_len = len(data)
            ctype = e.headers.get("Content-Type", "") if e.headers else ""
            if "text" in ctype.lower():
                charset = parse_charset(ctype)
                text = data.decode(charset, errors="replace")
                word_count = count_words(text)
        except Exception:
            content_len = 0
            word_count = None
        err_msg = f"HTTPError {e.code}: {e.reason}"
    except error.URLError as e:
        err_msg = f"URLError: {getattr(e, 'reason', str(e))}"
    except Exception as e:
        err_msg = f"Exception: {str(e)}"
    finally:
        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000.0
        ts = iso_utc_now()

    return {
        "url": url,
        "status_code": int(status),
        "response_time_ms": float(round(elapsed_ms, 3)),
        "content_length": int(content_len),
        "word_count": word_count if isinstance(word_count, int) else None,
        "timestamp": ts,
        "error": None if err_msg is None else str(err_msg),
    }

# -------- Main --------

def main():
    if len(sys.argv) != 3:
        print("Usage: python fetch_and_process.py <input_urls_file> <output_dir>")
        sys.exit(1)

    input_file = sys.argv[1]
    out_dir = sys.argv[2]
    ensure_outdir(out_dir)

    processing_start = iso_utc_now()

    with open(input_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    results, errors_lines = [], []

    for url in urls:
        res = fetch_one(url)
        results.append(res)
        if res["error"]:
            errors_lines.append(f"[{res['timestamp']}] [{res['url']}]: {res['error']}")

    summary = {
        "total_urls": len(results),
        "successful_requests": sum(1 for r in results if 200 <= r["status_code"] < 400 and not r["error"]),
        "failed_requests": sum(1 for r in results if r["error"]),
        "average_response_time_ms": float(round(sum(r["response_time_ms"] for r in results) / len(results), 3)),
        "total_bytes_downloaded": sum(r["content_length"] for r in results),
        "status_code_distribution": {str(r["status_code"]): sum(1 for x in results if x["status_code"] == r["status_code"])
                                     for r in results},
        "processing_start": processing_start,
        "processing_end": iso_utc_now(),
    }

    with open(os.path.join(out_dir, "responses.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "errors.log"), "w", encoding="utf-8") as f:
        for line in errors_lines:
            f.write(line + "\n")

    print(f"Processed {len(results)} URL(s).")
    print(f"Outputs written to: {os.path.abspath(out_dir)}")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        input_file = os.path.join("problem1", "test_urls.txt")
        out_dir = os.path.join("problem1", "out")
        print(f"⚠️ No arguments provided, using defaults: {input_file} -> {out_dir}")
        main_args = [input_file, out_dir]
    else:
        main_args = sys.argv[1:]
    sys.argv = [sys.argv[0]] + main_args
    main()
