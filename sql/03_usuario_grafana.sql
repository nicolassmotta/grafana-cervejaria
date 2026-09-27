-- Usuário exclusivo do Grafana, só com permissão de leitura.
-- Boa prática recomendada na documentação do Grafana: um painel nunca deve
-- conseguir alterar ou apagar dados, mesmo que alguém escreva um DELETE numa query.

CREATE ROLE grafana_leitor WITH LOGIN PASSWORD 'leitor';

GRANT USAGE ON SCHEMA public TO grafana_leitor;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_leitor;
