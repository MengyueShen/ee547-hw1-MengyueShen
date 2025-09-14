#!/usr/bin/env python3
"""
arxiv_processor.py
Query ArXiv API, extract paper metadata, and write structured outputs.

Usage:
    python arxiv_processor.py "<search_query>" <max_results (1-100)> <output_dir>

Example:
    python arxiv_processor.py "cat:cs.LG" 10 out
"""

import sys
import os
import json
import re
import time
import datetime
from urllib import request, parse, error
import xml.etree.ElementTree as ET

ARXIV_API = "http://export.arxiv.org/api/query"
RETRY_MAX = 3
RETRY_WAIT_SECONDS = 3
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}  # ArXiv uses Atom XML

# ---- Stopwords from the assignment ----
STOPWORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of',
    'with','by','from','up','about','into','through','during','is','are',
    'was','were','be','been','being','have','has','had','do','does','did',
    'will','would','could','should','may','might','can','this','that',
    'these','those','i','you','he','she','it','we','they','what','which',
    'who','when','where','why','how','all','each','every','both','few',
    'more','most','other','some','such','as','also','very','too','only',
    'so','than','not'
}

# keep hyphen so that state-of-the-art stays one token for tech-term extraction
_TOKEN_RE = re.compile(r"[A-Za-z0-9-]+")
_UPPER_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")

# ---------------- Utilities ----------------

def iso_utc_now() -> str:
    """ISO-8601 UTC timestamp with 'Z' suffix."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def log_line(lines: list[str], msg: str) -> None:
    """Append a timestamped line into the in-memory log list."""
    lines.append(f"[{iso_utc_now()}] {msg}")

def lower_tokens(words: list[str]) -> list[str]:
    return [w.lower() for w in words if w]

def ensure_outdir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

_word_re = re.compile(r"[A-Za-z0-9]+")

def word_count(text: str) -> int:
    """Count words as sequences of alphanumeric chars."""
    if not text:
        return 0
    return len(_word_re.findall(text))

def build_query_url(search_query: str, start: int, max_results: int) -> str:
    """Compose ArXiv API query URL."""
    qs = parse.urlencode({
        "search_query": search_query,
        "start": str(start),
        "max_results": str(max_results),
    })
    return f"{ARXIV_API}?{qs}"

def fetch_with_retries(url: str, timeout: int, proc_log: list[str]) -> bytes:
    """
    GET with retry for HTTP 429. Other HTTP errors are raised to caller.
    Network errors (URLError) are also raised (caller decides to exit 1).
    """
    req = request.Request(
        url=url,
        method="GET",
        headers={"User-Agent": "EE547-HW1-ArXivBot/1.0 (urllib)"},
    )
    for attempt in range(1, RETRY_MAX + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except error.HTTPError as e:
            if e.code == 429 and attempt < RETRY_MAX:
                wait_s = RETRY_WAIT_SECONDS
                log_line(proc_log, f"HTTP 429 received. Waiting {wait_s}s then retry ({attempt}/{RETRY_MAX - 1})")
                time.sleep(wait_s)
                continue
            # re-raise other HTTPError or final 429
            raise


def parse_arxiv_xml(xml_bytes: bytes, proc_log: list[str]) -> list[dict]:
    """
    Parse Atom XML feed and return a list of papers.
    Required fields: id, title, summary. If missing -> warn & skip.
    Invalid XML -> log error and return empty list.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        log_line(proc_log, f"Invalid XML: {str(e)}")
        return []

    papers = []
    for entry in root.findall("atom:entry", ATOM_NS):
        # id (last path segment)
        id_url = (entry.findtext("atom:id", default="", namespaces=ATOM_NS) or "").strip()
        paper_id = id_url.rsplit("/", 1)[-1] if id_url else ""

        title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
        summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ATOM_NS) or "").strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=ATOM_NS) or "").strip()

        # authors
        authors = []
        for a in entry.findall("atom:author", ATOM_NS):
            name = a.findtext("atom:name", default="", namespaces=ATOM_NS)
            name = name.strip() if name else ""
            if name:
                authors.append(name)

        # categories (term attribute)
        categories = []
        for c in entry.findall("atom:category", ATOM_NS):
            term = c.attrib.get("term", "").strip()
            if term:
                categories.append(term)

        # ---- required fields check ----
        missing = []
        if not paper_id: missing.append("id")
        if not title:    missing.append("title")
        if not summary:  missing.append("summary")
        if missing:
            log_line(proc_log, f"Warning: missing {','.join(missing)}; skipping one entry.")
            continue

        paper = {
            "arxiv_id": paper_id,
            "title": title,
            "authors": authors,
            "abstract": summary,
            "categories": categories,
            "published": published,
            "updated": updated,
            "abstract_stats": abstract_stats_for_papers_json(summary)
        }
        papers.append(paper)

    return papers



def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return _TOKEN_RE.findall(text)

def sentence_split(text: str) -> list[str]:
    if not text:
        return []
    # split on one or more of . ! ?
    parts = re.split(r"[.!?]+", text)
    # strip and drop empties
    return [p.strip() for p in parts if p.strip()]

def top_k_freq(words: list[str], k: int = 20) -> list[list]:
    """lowercase for counting; exclude stopwords; return [[word, count], ...]."""
    freq = {}
    for w in words:
        wl = w.lower()
        if wl in STOPWORDS:
            continue
        if not wl:
            continue
        freq[wl] = freq.get(wl, 0) + 1
    # sort by count desc then alphabetically
    top = sorted(freq.items(), key=lambda x: (-x[1], x[0]))[:k]
    # to stable JSON list
    return [[w, c] for w, c in top]

def compute_abstract_analysis(abstract: str) -> dict:
    """
    Compute word frequency, sentence stats, and technical term extraction
    for a single abstract string.
    """
    words = tokenize(abstract)                              # keep original case for tech extraction
    total_wc = len(words)
    unique_wc = len(set(w.lower() for w in words))          # unique by lowercase

    # average word length (letters+digits+hyphen length)
    avg_wlen = round((sum(len(w) for w in words) / total_wc), 3) if total_wc else 0.0

    # top-20 words (exclude stopwords; by lowercase)
    top20 = top_k_freq(words, 20)

    # sentence analysis
    sents = sentence_split(abstract)
    sent_counts = [len(tokenize(s)) for s in sents]
    total_sents = len(sents)
    avg_w_per_sent = round((sum(sent_counts) / total_sents), 3) if total_sents else 0.0

    # longest / shortest sentence by word count（返回句子文本）
    if total_sents:
        max_idx = max(range(total_sents), key=lambda i: sent_counts[i])
        min_idx = min(range(total_sents), key=lambda i: sent_counts[i])
        longest = {"text": sents[max_idx], "word_count": sent_counts[max_idx]}
        shortest = {"text": sents[min_idx], "word_count": sent_counts[min_idx]}
    else:
        longest = {"text": "", "word_count": 0}
        shortest = {"text": "", "word_count": 0}

    # technical terms
    # use original-case tokens; de-duplicate preserving first appearance
    seen = set()
    def uniq_keep_order(seq):
        out = []
        for x in seq:
            if x not in seen:
                out.append(x); seen.add(x)
        return out

    uppercase_terms = uniq_keep_order([w for w in words if _UPPER_RE.search(w)])
    seen.clear()
    numeric_terms   = uniq_keep_order([w for w in words if _DIGIT_RE.search(w)])
    seen.clear()
    hyphen_terms    = uniq_keep_order([w for w in words if "-" in w and len(w) > 1])

    return {
        "word_frequency": {
            "total_word_count": total_wc,
            "unique_word_count": unique_wc,
            "top_20_words": top20,                # [[word, count], ...]
            "average_word_length": avg_wlen
        },
        "sentence_analysis": {
            "total_sentence_count": total_sents,
            "average_words_per_sentence": avg_w_per_sent,
            "longest_sentence": longest,          # {"text": "...", "word_count": N}
            "shortest_sentence": shortest
        },
        "technical_terms": {
            "uppercase_terms": uppercase_terms,
            "numeric_terms": numeric_terms,
            "hyphenated_terms": hyphen_terms
        }
    }

def abstract_stats_for_papers_json(abstract: str) -> dict:
    """Return only the fields required by papers.json: totals/unique/sentences/averages."""
    words = tokenize(abstract)
    total_words = len(words)
    unique_words = len(set(w.lower() for w in words))
    sents = sentence_split(abstract)
    sent_counts = [len(tokenize(s)) for s in sents]
    total_sentences = len(sents)
    avg_words_per_sentence = round((sum(sent_counts) / total_sentences), 3) if total_sentences else 0.0
    avg_word_length = round((sum(len(w) for w in words) / total_words), 3) if total_words else 0.0
    return {
        "total_words": total_words,
        "unique_words": unique_words,
        "total_sentences": total_sentences,
        "avg_words_per_sentence": avg_words_per_sentence,
        "avg_word_length": avg_word_length,
    }


def aggregate_stats(papers: list[dict]) -> dict:
    """Compute simple text statistics and aggregates."""
    total = len(papers)

    # author frequency
    author_counts = {}
    for p in papers:
        for a in p.get("authors", []):
            author_counts[a] = author_counts.get(a, 0) + 1
    top_authors = sorted(author_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

    # category frequency
    cat_counts = {}
    for p in papers:
        for c in p.get("categories", []):
            cat_counts[c] = cat_counts.get(c, 0) + 1
    top_categories = sorted(cat_counts.items(), key=lambda x: (-x[1], x[0]))[:10]

    # title / summary word counts
    title_counts = [word_count(p.get("title", "")) for p in papers]
    summary_counts = [word_count(p.get("summary", "")) for p in papers]
    avg_title_wc = round(sum(title_counts) / total, 3) if total else 0.0
    avg_summary_wc = round(sum(summary_counts) / total, 3) if total else 0.0

    # earliest published / latest updated (as ISO strings)
    # Keep strings but try to compute min/max robustly
    def to_dt(s: str):
        # arXiv timestamps look like 2007-12-03T20:21:00Z
        try:
            # handle both with/without 'Z'
            if s.endswith("Z"):
                return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
            return datetime.datetime.fromisoformat(s)
        except Exception:
            return None

    published_dts = [to_dt(p.get("published", "")) for p in papers if p.get("published")]
    updated_dts = [to_dt(p.get("updated", "")) for p in papers if p.get("updated")]
    earliest_published = min(published_dts).isoformat().replace("+00:00","Z") if published_dts else None
    latest_updated = max(updated_dts).isoformat().replace("+00:00","Z") if updated_dts else None

    return {
        "total_papers": total,
        "unique_authors": len(author_counts),
        "unique_categories": len(cat_counts),
        "top_authors": top_authors,
        "top_categories": top_categories,
        "average_title_word_count": avg_title_wc,
        "average_abstract_word_count": avg_summary_wc,
        "earliest_published": earliest_published,
        "latest_updated": latest_updated,
        "processing_time_utc": iso_utc_now(),
    }

# ---------------- Main ----------------
def main():
    if len(sys.argv) != 4:
        print('Usage: python arxiv_processor.py "<search_query>" <max_results (1-100)> <output_dir>')
        sys.exit(1)

    search_query = sys.argv[1]
    try:
        max_results = int(sys.argv[2])
    except ValueError:
        print("max_results must be an integer.")
        sys.exit(1)
    if not (1 <= max_results <= 100):
        print("max_results must be between 1 and 100.")
        sys.exit(1)

    out_dir = sys.argv[3]
    ensure_outdir(out_dir)

    proc_log: list[str] = []
    t0 = time.monotonic()
    log_line(proc_log, f"Starting ArXiv query: {search_query}")

    # ---- fetch & parse with required error handling ----
    try:
        url = build_query_url(search_query, start=0, max_results=max_results)
        raw = fetch_with_retries(url, timeout=20, proc_log=proc_log)
        papers = parse_arxiv_xml(raw, proc_log)  # each has abstract_stats already
        log_line(proc_log, f"Fetched {len(papers)} results from ArXiv API")
    except error.URLError as e:
        # Network unreachable -> log & EXIT 1
        log_line(proc_log, f"Network error (URLError): {getattr(e, 'reason', str(e))}")
        # write log then exit 1
        with open(os.path.join(out_dir, "processing.log"), "w", encoding="utf-8") as f:
            for line in proc_log:
                f.write(line + "\n")
        sys.exit(1)
    except error.HTTPError as e:
        # Non-429 HTTP errors -> log and continue with zero papers
        log_line(proc_log, f"HTTPError {e.code}: {e.reason}")
        papers = []
    except Exception as e:
        # Other unexpected issues -> log and continue (no exit)
        log_line(proc_log, f"Exception: {str(e)}")
        papers = []

    # ---- corpus_analysis.json (global statistics) ----
    from collections import Counter

    total_abstracts = len(papers)
    total_words = 0
    unique_global = set()
    abs_lengths = []
    longest_abs = 0
    shortest_abs = 10**9

    global_tf = Counter()   # term frequency across abstracts (lowercased, stopwords excluded)
    global_df = Counter()   # in how many abstracts the term appears
    upper_terms_set = set()
    numeric_terms_set = set()
    hyphen_terms_set = set()
    category_counts = Counter()

    for p in papers:
        log_line(proc_log, f"Processing paper: {p.get('arxiv_id','')}")
        abstract = p.get("abstract", "")

        tokens = tokenize(abstract)
        abs_len = len(tokens)
        abs_lengths.append(abs_len)
        total_words += abs_len
        unique_global.update(w.lower() for w in tokens if w)

        if abs_len > longest_abs: longest_abs = abs_len
        if abs_len < shortest_abs: shortest_abs = abs_len

        doc_terms = set()
        for w in tokens:
            wl = w.lower()
            if not wl or wl in STOPWORDS:
                continue
            global_tf[wl] += 1
            doc_terms.add(wl)
        for wl in doc_terms:
            global_df[wl] += 1

        upper_terms_set.update([w for w in tokens if _UPPER_RE.search(w)])
        numeric_terms_set.update([w for w in tokens if _DIGIT_RE.search(w)])
        hyphen_terms_set.update([w for w in tokens if "-" in w and len(w) > 1])

        for c in p.get("categories", []):
            if c:
                category_counts[c] += 1

    avg_abstract_len = round((sum(abs_lengths) / total_abstracts), 3) if total_abstracts else 0.0
    top_50 = [{"word": w, "frequency": int(tf), "documents": int(global_df[w])}
              for w, tf in global_tf.most_common(50)]

    corpus_analysis = {
        "query": search_query,
        "papers_processed": total_abstracts,
        "processing_timestamp": iso_utc_now(),
        "corpus_stats": {
            "total_abstracts": total_abstracts,
            "total_words": int(total_words),
            "unique_words_global": int(len(unique_global)),
            "avg_abstract_length": float(avg_abstract_len),
            "longest_abstract_words": int(longest_abs if total_abstracts else 0),
            "shortest_abstract_words": int(shortest_abs if total_abstracts else 0)
        },
        "top_50_words": top_50,
        "technical_terms": {
            "uppercase_terms": sorted(upper_terms_set),
            "numeric_terms": sorted(numeric_terms_set),
            "hyphenated_terms": sorted(hyphen_terms_set)
        },
        "category_distribution": {k: int(v) for k, v in sorted(category_counts.items())}
    }

    # ---- write outputs ----
    with open(os.path.join(out_dir, "papers.json"), "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "corpus_analysis.json"), "w", encoding="utf-8") as f:
        json.dump(corpus_analysis, f, ensure_ascii=False, indent=2)

    # processing.log
    t1 = time.monotonic()
    log_line(proc_log, f"Completed processing: {len(papers)} papers in {round(t1 - t0, 2)} seconds")
    with open(os.path.join(out_dir, "processing.log"), "w", encoding="utf-8") as f:
        for line in proc_log:
            f.write(line + "\n")

    print(f"Processed {len(papers)} paper(s). Outputs -> {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
