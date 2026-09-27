"""
Simulador de sensores da Cervejaria Byte (empresa fictícia).

Finge ser os sensores da fábrica: a cada INTERVALO_SEGUNDOS grava no PostgreSQL
uma leitura de cada tanque de fermentação e a produção de cada linha de envase.

Na primeira execução também gera HORAS_HISTORICO horas de dados passados, para
os gráficos do Grafana não começarem vazios.
"""

import math
import os
import random
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psycopg

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://cervejaria:cervejaria@localhost:5432/cervejaria"
)
INTERVALO_SEGUNDOS = float(os.environ.get("INTERVALO_SEGUNDOS", "5"))
HORAS_HISTORICO = float(os.environ.get("HORAS_HISTORICO", "6"))

TEMPERATURA_AMBIENTE_C = 26.0
AQUECIMENTO_C_POR_MINUTO = 2.5  # quanto um tanque esquenta com a refrigeração desligada
TEMPO_RESFRIAMENTO_S = 30.0  # quão rápido a refrigeração traz o tanque de volta ao alvo

PRODUCAO_POR_MINUTO = {"L1": 360, "L2": 600}  # unidades envasadas por minuto em cada linha
TAXA_REJEICAO = 0.02  # ~2% das garrafas/latas saem com defeito


@dataclass
class Tanque:
    id: int
    codigo: str
    temp_alvo_c: float
    refrigeracao_ligada: bool
    temperatura_c: float
    ph_base: float


@dataclass
class Linha:
    id: int
    codigo: str


# --- Física de mentirinha ----------------------------------------------------


def avancar_temperatura(tanque: Tanque, segundos: float) -> None:
    """Com refrigeração, a temperatura converge para o alvo; sem ela, sobe até a do ambiente."""
    if tanque.refrigeracao_ligada:
        fator = 1 - math.exp(-segundos / TEMPO_RESFRIAMENTO_S)
        tanque.temperatura_c += (tanque.temp_alvo_c - tanque.temperatura_c) * fator
    else:
        tanque.temperatura_c += AQUECIMENTO_C_POR_MINUTO * segundos / 60
        tanque.temperatura_c = min(tanque.temperatura_c, TEMPERATURA_AMBIENTE_C)
    tanque.temperatura_c += random.gauss(0, 0.05)  # ruído do sensor


def ler_tanque(tanque: Tanque, momento: datetime) -> tuple:
    # Cerveja mais quente fermenta mais rápido e libera mais CO2, então a pressão sobe junto
    pressao = 1.2 + 0.08 * (tanque.temperatura_c - tanque.temp_alvo_c) + random.gauss(0, 0.02)
    ph = tanque.ph_base + random.gauss(0, 0.02)
    return (momento, tanque.id, round(tanque.temperatura_c, 2), round(pressao, 2), round(ph, 2))


def ler_linha(linha: Linha, momento: datetime, segundos: float) -> tuple:
    total = round(PRODUCAO_POR_MINUTO[linha.codigo] * segundos / 60 * random.uniform(0.9, 1.05))
    rejeitadas = round(total * TAXA_REJEICAO * random.uniform(0.3, 1.7))
    return (momento, linha.id, total - rejeitadas, rejeitadas)


# --- Banco de dados ------------------------------------------------------------


def carregar_tanques(conn: psycopg.Connection) -> list[Tanque]:
    # Retoma da última temperatura gravada; sem leituras ainda, começa na temperatura alvo
    linhas = conn.execute(
        """
        SELECT t.id, t.codigo, t.temp_alvo_c, t.refrigeracao_ligada,
               COALESCE(ultima.temperatura_c, t.temp_alvo_c)
        FROM tanques t
        LEFT JOIN LATERAL (
            SELECT temperatura_c FROM leituras_tanque
            WHERE tanque_id = t.id ORDER BY momento DESC LIMIT 1
        ) ultima ON true
        ORDER BY t.codigo
        """
    ).fetchall()
    return [
        Tanque(id_, codigo, float(alvo), ligada, float(temperatura), random.uniform(4.2, 4.6))
        for id_, codigo, alvo, ligada, temperatura in linhas
    ]


def carregar_linhas(conn: psycopg.Connection) -> list[Linha]:
    linhas = conn.execute("SELECT id, codigo FROM linhas_envase ORDER BY codigo").fetchall()
    return [Linha(id_, codigo) for id_, codigo in linhas]


def atualizar_refrigeracao(conn: psycopg.Connection, tanques: list[Tanque]) -> None:
    """Relê o estado da refrigeração, que o refrigeracao.py pode ter mudado."""
    estados = dict(conn.execute("SELECT id, refrigeracao_ligada FROM tanques").fetchall())
    for tanque in tanques:
        tanque.refrigeracao_ligada = estados[tanque.id]


def gravar(conn: psycopg.Connection, leituras: list[tuple], producao: list[tuple]) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO leituras_tanque (momento, tanque_id, temperatura_c, pressao_bar, ph)"
            " VALUES (%s, %s, %s, %s, %s)",
            leituras,
        )
        cur.executemany(
            "INSERT INTO producao_envase (momento, linha_id, unidades_ok, unidades_rejeitadas)"
            " VALUES (%s, %s, %s, %s)",
            producao,
        )


def gerar_historico(conn: psycopg.Connection, tanques: list[Tanque], linhas: list[Linha]) -> None:
    """Preenche as últimas horas com dados, incluindo uma falha passada no TQ-03."""
    if conn.execute("SELECT EXISTS (SELECT 1 FROM leituras_tanque)").fetchone()[0]:
        return

    agora = datetime.now(timezone.utc)
    momento = agora - timedelta(hours=HORAS_HISTORICO)
    passo = 60.0
    falha_inicio, falha_fim = agora - timedelta(minutes=45), agora - timedelta(minutes=37)
    tanque_falha = next(t for t in tanques if t.codigo == "TQ-03")

    leituras, producao = [], []
    while momento < agora:
        tanque_falha.refrigeracao_ligada = not (falha_inicio <= momento < falha_fim)
        for tanque in tanques:
            avancar_temperatura(tanque, passo)
            leituras.append(ler_tanque(tanque, momento))
        producao.extend(ler_linha(linha, momento, passo) for linha in linhas)
        momento += timedelta(seconds=passo)
    tanque_falha.refrigeracao_ligada = True

    gravar(conn, leituras, producao)
    conn.execute(
        "INSERT INTO eventos (momento, tanque_id, tipo, descricao) VALUES"
        " (%s, %s, 'falha', 'TQ-03: compressor da refrigeração parou'),"
        " (%s, %s, 'normalizado', 'TQ-03: refrigeração religada pela manutenção')",
        (falha_inicio, tanque_falha.id, falha_fim, tanque_falha.id),
    )
    print(f"Histórico gerado: {len(leituras)} leituras de tanque, {len(producao)} de envase")


# --- Laço principal ----------------------------------------------------------


def main() -> None:
    # O Docker manda SIGTERM ao parar o container; encerramos sem stack trace
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        tanques = carregar_tanques(conn)
        linhas = carregar_linhas(conn)
        gerar_historico(conn, tanques, linhas)
        print(f"Simulando {len(tanques)} tanques e {len(linhas)} linhas a cada {INTERVALO_SEGUNDOS:g}s")

        while True:
            inicio = time.monotonic()
            momento = datetime.now(timezone.utc)

            atualizar_refrigeracao(conn, tanques)
            for tanque in tanques:
                avancar_temperatura(tanque, INTERVALO_SEGUNDOS)
            leituras = [ler_tanque(tanque, momento) for tanque in tanques]
            producao = [ler_linha(linha, momento, INTERVALO_SEGUNDOS) for linha in linhas]
            gravar(conn, leituras, producao)

            temperaturas = "  ".join(
                f"{t.codigo} {t.temperatura_c:5.1f}°C{'' if t.refrigeracao_ligada else ' (SEM REFRIGERAÇÃO)'}"
                for t in tanques
            )
            envase = "  ".join(f"{l.codigo} +{p[2]}" for l, p in zip(linhas, producao))
            print(f"{momento.astimezone():%H:%M:%S}  {temperaturas}  |  {envase}")

            time.sleep(max(0.0, INTERVALO_SEGUNDOS - (time.monotonic() - inicio)))


if __name__ == "__main__":
    main()
