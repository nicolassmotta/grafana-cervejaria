-- Estrutura do banco da Cervejaria Byte (empresa fictícia).
-- Roda automaticamente na primeira vez que o container do PostgreSQL sobe.

-- Cadastros ---------------------------------------------------------------

-- Tanques de fermentação. Cada estilo de cerveja fermenta numa temperatura diferente.
CREATE TABLE tanques (
    id                  SERIAL PRIMARY KEY,
    codigo              TEXT          NOT NULL UNIQUE,  -- ex.: TQ-01
    estilo              TEXT          NOT NULL,         -- ex.: Pilsen
    capacidade_l        INTEGER       NOT NULL,
    temp_alvo_c         NUMERIC(4, 1) NOT NULL,         -- temperatura ideal de fermentação
    temp_max_c          NUMERIC(4, 1) NOT NULL,         -- acima disso o Grafana dispara alerta
    refrigeracao_ligada BOOLEAN       NOT NULL DEFAULT true
);

-- Linhas de envase: onde a cerveja pronta vai para garrafas ou latas.
CREATE TABLE linhas_envase (
    id        SERIAL PRIMARY KEY,
    codigo    TEXT NOT NULL UNIQUE,  -- ex.: L1
    embalagem TEXT NOT NULL          -- ex.: Garrafa 600 ml
);

-- Séries temporais (uma linha por leitura) ----------------------------------

CREATE TABLE leituras_tanque (
    momento       TIMESTAMPTZ   NOT NULL DEFAULT now(),
    tanque_id     INTEGER       NOT NULL REFERENCES tanques (id),
    temperatura_c NUMERIC(5, 2) NOT NULL,
    pressao_bar   NUMERIC(4, 2) NOT NULL,
    ph            NUMERIC(3, 2) NOT NULL
);
CREATE INDEX ON leituras_tanque (momento);
CREATE INDEX ON leituras_tanque (tanque_id, momento DESC);

CREATE TABLE producao_envase (
    momento             TIMESTAMPTZ NOT NULL DEFAULT now(),
    linha_id            INTEGER     NOT NULL REFERENCES linhas_envase (id),
    unidades_ok         INTEGER     NOT NULL,
    unidades_rejeitadas INTEGER     NOT NULL
);
CREATE INDEX ON producao_envase (momento);

-- Acontecimentos importantes (falhas, normalizações). Viram marcações nos gráficos.
CREATE TABLE eventos (
    id        SERIAL PRIMARY KEY,
    momento   TIMESTAMPTZ NOT NULL DEFAULT now(),
    tanque_id INTEGER REFERENCES tanques (id),
    tipo      TEXT        NOT NULL CHECK (tipo IN ('falha', 'normalizado')),
    descricao TEXT        NOT NULL
);
CREATE INDEX ON eventos (momento);
