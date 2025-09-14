FROM python:3.11-slim

WORKDIR /app
COPY process.py /app/

# -u for unbuffered stdout so logs stream live
CMD ["python", "-u", "/app/process.py"]
