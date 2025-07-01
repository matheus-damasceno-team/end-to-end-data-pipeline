-- tests/singular/test_incremental_integrity_trino.sql

{{ config(
    tags=['incremental', 'silver', 'trino'],
    severity='error',
    error_if='>0'
) }}

-- Teste: Verifica se há gaps na carga incremental
WITH time_gaps AS (
    SELECT 
        ingestion_timestamp,
        LAG(ingestion_timestamp) OVER (ORDER BY ingestion_timestamp) as prev_timestamp,
        ingestion_timestamp - LAG(ingestion_timestamp) OVER (ORDER BY ingestion_timestamp) as time_diff
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE processed_at >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR
),
large_gaps AS (
    SELECT 
        ingestion_timestamp,
        prev_timestamp,
        time_diff
    FROM time_gaps
    WHERE time_diff > INTERVAL '5' MINUTE  -- Gap maior que 5 minutos é suspeito
)
SELECT * FROM large_gaps