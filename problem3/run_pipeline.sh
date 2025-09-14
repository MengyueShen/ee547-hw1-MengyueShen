#!/bin/bash

if [ $# -lt 1 ]; then
  echo "Usage: $0 <url1> [url2] ..."
  echo "Example: $0 https://example.com https://wikipedia.org"
  exit 1
fi

echo "Starting Multi-Container Pipeline"
echo "================================="

# Clean previous runs
docker-compose down >/dev/null 2>/dev/null

# Create temporary directory
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Create URL list
for url in "$@"; do
  echo "$url" >> "$TEMP_DIR/urls.txt"
done

echo "URLs to process:"
cat "$TEMP_DIR/urls.txt"
echo ""

# Build containers
echo "Building containers..."
docker-compose build --quiet

# Start pipeline
echo "Starting pipeline..."
docker-compose up -d

# Wait for containers to initialize
sleep 3

# Ensure the shared input dir exists inside the named volume
docker exec pipeline-fetcher sh -lc 'mkdir -p /shared/input'

# Inject URLs (copy the file into the container volume)
echo "Injecting URLs..."
docker cp "$TEMP_DIR/urls.txt" pipeline-fetcher:/shared/input/urls.txt

# -------- Monitor completion (CHECK THE VOLUME, NOT THE CONTAINER) --------
echo "Processing..."
MAX_WAIT=300 # 5 minutes timeout
ELAPSED=0
# This name must match the one in docker-compose.yml:
#   volumes: { pipeline-data: { name: pipeline-shared-data } }
VOLUME_NAME="pipeline-shared-data"

while [ $ELAPSED -lt $MAX_WAIT ]; do
  if docker run --rm -v ${VOLUME_NAME}:/shared alpine sh -lc 'test -f /shared/analysis/final_report.json'; then
    echo "Pipeline complete"
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  echo "Pipeline timeout after ${MAX_WAIT} seconds"
  docker-compose logs
  docker-compose down
  exit 1
fi

# -------- Extract results (COPY FROM THE VOLUME TO HOST, Windows-safe) --------
mkdir -p output
VOLUME_NAME="pipeline-shared-data"

# create a tiny helper container with the volume attached
docker create --name volcopy -v ${VOLUME_NAME}:/shared alpine:3.19 >/dev/null

# copy files out of the volume
docker cp volcopy:/shared/analysis/final_report.json output/ 2>/dev/null || true
mkdir -p output/status
docker cp volcopy:/shared/status/. output/status/ 2>/dev/null || true

# cleanup helper
docker rm -f volcopy >/dev/null


# Cleanup
docker-compose down

# Display summary
if [ -f "output/final_report.json" ]; then
  echo ""
  echo "Results saved to output/final_report.json"
  python3 -m json.tool output/final_report.json | head -20
else
  echo "Pipeline failed - no output generated"
  exit 1
fi
