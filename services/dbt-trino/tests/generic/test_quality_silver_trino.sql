-- tests/generic/test_silver_quality_trino.sql

{{ config(
    tags=['data_quality', 'silver', 'trino'],
    severity='warn'
) }}

-- Teste: Verifica razão crédito/renda anormal
WITH ratio_check AS (
    SELECT 
        proponente_id,
        valor_solicitado_credito,
        renda_bruta_anual_declarada,
        razao_credito_renda,
        processed_at
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE razao_credito_renda IS NOT NULL
        AND razao_credito_renda > 10  -- Razão suspeita
        AND processed_at >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
)
SELECT * FROM ratio_check