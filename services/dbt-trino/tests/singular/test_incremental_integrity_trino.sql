-- tests/singular/test_incremental_integrity_trino.sql

{{ config(
    tags=['incremental', 'silver', 'trino'],
    severity='error',
    error_if='>0'
) }}

-- Teste: Verifica se há gaps na carga incremental usando timestamps
WITH time_gaps AS (
    SELECT 
        ingestion_timestamp,
        LAG(ingestion_timestamp) OVER (ORDER BY ingestion_timestamp) as prev_timestamp
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE processed_at >= CURRENT_TIMESTAMP - INTERVAL '1' HOUR
),
large_gaps AS (
    SELECT 
        ingestion_timestamp,
        prev_timestamp,
        DATE_DIFF('minute', prev_timestamp, ingestion_timestamp) as minutes_diff
    FROM time_gaps
    WHERE prev_timestamp IS NOT NULL
      AND DATE_DIFF('minute', prev_timestamp, ingestion_timestamp) > 5
)
SELECT * FROM large_gaps