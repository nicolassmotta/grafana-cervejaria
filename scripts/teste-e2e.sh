#!/usr/bin/env bash
# Teste de ponta a ponta: sobe o ambiente e confere se tudo funciona de verdade,
# do sensor simulado até a notificação de alerta.
#
#   ./scripts/teste-e2e.sh
#
# Não apaga dados. Roda também no GitHub Actions a cada push (.github/workflows/e2e.yml).

set -euo pipefail
cd "$(dirname "$0")/.."

GRAFANA="http://localhost:3000"
AUTH="admin:cervejaria"
TANQUE="TQ-02"

passo() { printf '\n==> %s\n' "$*"; }
ok() { printf '    OK: %s\n' "$*"; }
falha() {
  printf '    FALHOU: %s\n' "$*" >&2
  exit 1
}

# Repete um comando até ele dar certo ou o tempo acabar
esperar() {
  local descricao=$1 limite=$2
  shift 2
  for ((i = 0; i < limite; i += 2)); do
    if "$@" >/dev/null 2>&1; then
      ok "$descricao"
      return 0
    fi
    sleep 2
  done
  falha "$descricao (esperou ${limite}s)"
}

api() { curl -fsS -u "$AUTH" "$GRAFANA$1"; }
estado_alerta() {
  api /api/prometheus/grafana/api/v1/rules | python3 -c "
import json, sys
regras = json.load(sys.stdin)['data']['groups']
print(next(a['state'] for g in regras for r in g['rules'] for a in r.get('alerts', []) if a['labels'].get('tanque') == '$TANQUE'))"
}
alerta_em() { [ "$(estado_alerta)" = "$1" ]; }
tem_leituras() { [ "$(docker compose exec -T postgres psql -U cervejaria -tAc 'SELECT count(*) FROM leituras_tanque')" -gt 0 ]; }
# Só olha logs deste teste, para uma execução anterior não gerar falso positivo
notificou() { docker compose logs --since "$INICIO" notificador | grep -q "\[$1\] $TANQUE"; }

passo "Subindo o ambiente"
docker compose build --quiet
docker compose up -d

passo "Serviços"
esperar "Grafana respondendo" 120 api /api/health
esperar "simulador gravando leituras no PostgreSQL" 60 tem_leituras

passo "Provisionamento do Grafana"
esperar "fonte de dados conectada ao banco" 30 sh -c "curl -fsS -u $AUTH $GRAFANA/api/datasources/uid/cervejaria-pg/health | grep -q '\"status\":\"OK\"'"
esperar "dashboard carregado" 30 api /api/dashboards/uid/cervejaria

passo "Estado inicial"
# Garante o ponto de partida, caso um teste manual tenha deixado o tanque desligado
docker compose exec -T simulador python refrigeracao.py ligar "$TANQUE"
esperar "alerta do $TANQUE em Normal" 120 alerta_em Normal
INICIO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

passo "Simulando falha na refrigeração do $TANQUE"
docker compose exec -T simulador python refrigeracao.py desligar "$TANQUE"
esperar "alerta ficou Pendente" 120 alerta_em Pending
esperar "alerta disparou" 60 alerta_em Alerting
esperar "notificador recebeu o aviso de alerta disparado" 30 notificou "ALERTA DISPARADO"

passo "Religando a refrigeração do $TANQUE"
docker compose exec -T simulador python refrigeracao.py ligar "$TANQUE"
esperar "alerta voltou ao normal" 120 alerta_em Normal
esperar "notificador recebeu o aviso de alerta resolvido" 60 notificou "ALERTA RESOLVIDO"

printf '\nTudo certo: sensores -> PostgreSQL -> Grafana -> alerta -> notificação.\n'
