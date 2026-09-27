"""
Liga ou desliga a refrigeração de um tanque, para simular uma falha na fábrica.

Uso (com o ambiente rodando):
    docker compose exec simulador python refrigeracao.py desligar TQ-02
    docker compose exec simulador python refrigeracao.py ligar TQ-02
    docker compose exec simulador python refrigeracao.py status

Com a refrigeração desligada, o simulador faz a temperatura do tanque subir
e, ao passar do limite, o alerta configurado no Grafana dispara.
"""

import sys

import psycopg

from simulador import DATABASE_URL

USO = "uso: python refrigeracao.py (ligar|desligar) TQ-XX  |  python refrigeracao.py status"


def mostrar_status(conn: psycopg.Connection) -> None:
    for codigo, estilo, ligada in conn.execute(
        "SELECT codigo, estilo, refrigeracao_ligada FROM tanques ORDER BY codigo"
    ):
        print(f"{codigo}  {estilo:<7} refrigeração {'ligada' if ligada else 'DESLIGADA'}")


def alterar(conn: psycopg.Connection, acao: str, codigo: str) -> None:
    ligar = acao == "ligar"
    tanque = conn.execute(
        "UPDATE tanques SET refrigeracao_ligada = %s WHERE codigo = %s RETURNING id",
        (ligar, codigo),
    ).fetchone()
    if tanque is None:
        sys.exit(f"Tanque {codigo} não existe. Use: TQ-01, TQ-02, TQ-03 ou TQ-04")

    tipo, descricao = (
        ("normalizado", f"{codigo}: refrigeração religada")
        if ligar
        else ("falha", f"{codigo}: refrigeração desligada")
    )
    # O evento vira uma marcação vertical (anotação) nos gráficos do Grafana
    conn.execute(
        "INSERT INTO eventos (tanque_id, tipo, descricao) VALUES (%s, %s, %s)",
        (tanque[0], tipo, descricao),
    )
    print(descricao)


def main() -> None:
    args = sys.argv[1:]
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        if args == ["status"]:
            mostrar_status(conn)
        elif len(args) == 2 and args[0] in ("ligar", "desligar"):
            alterar(conn, args[0], args[1].upper())
        else:
            sys.exit(USO)


if __name__ == "__main__":
    main()
