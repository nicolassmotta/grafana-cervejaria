"""
Central de avisos da Cervejaria Byte (empresa fictícia).

Servidor HTTP mínimo que recebe as notificações de alerta do Grafana
(contact point do tipo webhook) e as mostra no terminal. Numa fábrica de
verdade, o mesmo webhook poderia ir para Slack, Teams, Telegram, e-mail etc.

Para acompanhar:
    docker compose logs -f notificador
"""

import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PORTA = int(os.environ.get("PORTA", "8000"))


def formatar(alerta: dict) -> str:
    rotulos = alerta.get("labels", {})
    anotacoes = alerta.get("annotations", {})
    agora = f"{datetime.now():%H:%M:%S}"
    disparado = alerta.get("status") == "firing"

    # Alertas que o próprio Grafana cria quando a consulta da regra falha ou volta vazia
    if rotulos.get("alertname") == "DatasourceNoData":
        if disparado:
            return f"{agora}  [SEM DADOS] Nenhuma leitura dos tanques no último minuto. O simulador está rodando?"
        return f"{agora}  [DADOS NORMALIZADOS] As leituras dos tanques voltaram a chegar"
    if rotulos.get("alertname") == "DatasourceError":
        if disparado:
            return f"{agora}  [ERRO] O Grafana não conseguiu consultar o banco de dados"
        return f"{agora}  [ERRO RESOLVIDO] O Grafana voltou a consultar o banco de dados"

    if disparado:
        return (
            f"{agora}  [ALERTA DISPARADO] {anotacoes.get('summary', rotulos.get('alertname', ''))}\n"
            f"          {anotacoes.get('description', '')}\n"
            f"          severidade: {rotulos.get('severidade', '-')}"
        )
    return f"{agora}  [ALERTA RESOLVIDO] {rotulos.get('tanque', '')} ({rotulos.get('estilo', '')}) voltou ao normal"


class Receptor(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        tamanho = int(self.headers.get("Content-Length", 0))
        notificacao = json.loads(self.rfile.read(tamanho) or b"{}")
        # O Grafana agrupa alertas: uma notificação pode trazer vários
        for alerta in notificacao.get("alerts", []):
            print(formatar(alerta), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        pass  # esconde o log padrão de cada requisição HTTP


if __name__ == "__main__":
    print(f"Central de avisos ouvindo na porta {PORTA}", flush=True)
    HTTPServer(("0.0.0.0", PORTA), Receptor).serve_forever()
