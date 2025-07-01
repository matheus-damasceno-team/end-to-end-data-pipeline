-- tests/singular/test_incremental_integrity_trino.sql



-- Teste: Verifica se há gaps na carga incremental
WITH time_gaps AS (
    SELECT 
        ingestion_timestamp,
        LAG(ingestion_timestamp) OVER (ORDER BY ingestion_timestamp) as prev_timestamp,
        ingestion_timestamp - LAG(ingestion_timestamp) OVER (ORDER BY ingestion_timestamp) as time_diff
    FROM "iceberg"."silver"."silver_dados_produtores_agro_trino"
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