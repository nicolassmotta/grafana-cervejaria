-- Cadastros fixos da fábrica. As leituras são geradas pelo simulador em Python.

INSERT INTO tanques (codigo, estilo, capacidade_l, temp_alvo_c, temp_max_c) VALUES
    ('TQ-01', 'Pilsen', 5000, 11.0, 13.0),
    ('TQ-02', 'IPA',    3000, 19.0, 21.0),
    ('TQ-03', 'Weiss',  3000, 20.0, 22.0),
    ('TQ-04', 'Stout',  2000, 18.0, 20.0);

INSERT INTO linhas_envase (codigo, embalagem) VALUES
    ('L1', 'Garrafa 600 ml'),
    ('L2', 'Lata 350 ml');
