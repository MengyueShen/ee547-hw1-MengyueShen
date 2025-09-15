# EE547 Homework 1

## Student Information
- **Name**: MengyueShen  
- **USC Email**: mengyues@usc.edu  

---

## External Libraries
- None (only Python standard libraries specified in the assignment are used)

---

## Problem 1
**How to Run**:  
Same as assignment specification.  
1. Build the Docker image:  
   ```bash
   ./build.sh
2. Run with input file and output directory:
   ```bash
   ./run.sh test_urls.txt output
3. Verify outputs in output/.


## Problem 2
**How to Run**:  
Same as assignment specification.
1. Build the Docker image:
   ```bash
   ./build.sh
2. Run with search query, max results, and output directory:
   ```bash
   $ ./run.sh "cat:cs.LG" 10 ./out
3. Verify outputs in the specified output directory.

## Problem 3

**How to Run**  
_Same as assignment specification._ For convenience:
1. Build services  
   ```bash
   docker compose build       

2. Run the pipeline with one or more URLs
   ```bash
   ./run_pipeline.sh $(cat test_urls.txt)  

3. Outputs will be copied to:
   ```bash
   problem3/output/final_report.json
   problem3/output/status/{fetch_complete.json, process_complete.json}

4.  Inspect shared volume: docker run --rm -v pipeline-shared-data:/shared alpine ls -la /shared/
if use git bash:
    ```bash
    MSYS_NO_PATHCONV=1 docker run --rm -v pipeline-shared-data:/shared alpine ls -la /shared/

