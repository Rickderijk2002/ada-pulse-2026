FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8081

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY pulse_oi/ ./pulse_oi/

EXPOSE 8081

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port \"${PORT}\""]
