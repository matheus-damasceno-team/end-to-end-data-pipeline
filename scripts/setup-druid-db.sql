-- Arquivo: scripts/setup-druid-db.sql
-- Script para configurar o banco de dados Druid no PostgreSQL

-- Criar usuário para Druid
CREATE USER druiduser WITH PASSWORD 'druidpassword';

-- Criar database para Druid
CREATE DATABASE druid WITH OWNER druiduser;

-- Conceder privilégios
GRANT ALL PRIVILEGES ON DATABASE druid TO druiduser;

-- Conectar ao database druid e configurar schema
\c druid;

-- Conceder privilégios no schema public
GRANT ALL ON SCHEMA public TO druiduser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO druiduser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO druiduser;