FROM python:3.11-slim

WORKDIR /app
COPY analyze.py /app/

# -u ensures unbuffered output for real-time logging
CMD ["python", "-u", "/app/analyze.py"]
