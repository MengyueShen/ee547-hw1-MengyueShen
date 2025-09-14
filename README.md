# EE547 Homework 1

## Student Information
- **Name**: MengyueShen  
- **USC Email**: mengyues@usc.edu  

---

## External Libraries
- None (only Python standard libraries specified in the assignment are used)

---

## Problem 1: HTTP Fetcher
**Description**:  
Fetches content from a list of URLs, processes responses, and writes outputs (`responses.json`, `summary.json`, `errors.log`).

**How to Run**:  
Same as assignment specification.  
1. Build the Docker image:  
   ```bash
   ./build.sh
2. Run with input file and output directory:
   ./run.sh test_urls.txt output
3. Verify outputs in output/.


## Problem 2: ArXiv Paper Metadata Processor
**Description**: 
Queries the ArXiv API for paper metadata, processes abstracts, computes statistics, and writes structured outputs (papers.json, corpus_analysis.json, processing.log).

**How to Run**:  
Same as assignment specification.
1. Build the Docker image:
./build.sh
2. Run with search query, max results, and output directory:
./run.sh "cat:cs.LG" 10 output
3. Verify outputs in the specified output directory.