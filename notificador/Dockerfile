FROM python:3.13-slim

# Só usa a biblioteca padrão do Python, nenhuma dependência extra
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY notificador.py .

CMD ["python", "notificador.py"]
