FROM python:3.13-slim

# Mostra os prints na hora no "docker compose logs", sem buffer
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py .

CMD ["python", "simulador.py"]
