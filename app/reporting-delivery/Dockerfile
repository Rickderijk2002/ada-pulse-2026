FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8082

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py renderer.py email_sender.py ./

EXPOSE 8082

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port \"${PORT}\""]
