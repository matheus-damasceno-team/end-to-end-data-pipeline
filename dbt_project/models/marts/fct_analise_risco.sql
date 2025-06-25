-- fct_analise_risco.sql

-- This model represents the final analytical table for credit risk analysis.
-- It assumes that a 'gold_features' table exists in ClickHouse,
-- populated by a Spark job with engineered features.

-- Configuration block for dbt specific settings for this model.
{{
  config(
    materialized='table', -- or 'incremental' for large datasets
    alias='fct_analise_risco',
    schema='marts', -- Specifies the schema (database in ClickHouse terms)
    engine='MergeTree()', -- ClickHouse specific: Choose an appropriate engine
    order_by='(proponente_id, data_analise)', -- ClickHouse specific: Define sorting key
    partition_by='toYYYYMM(data_analise)',   -- ClickHouse specific: Define partitioning
    settings={
      'index_granularity': 8192
    }
    // For incremental models, you would also define:
    // unique_key='surrogate_key_column', // A unique key for identifying rows
    // incremental_strategy='append' // or 'delete+insert' or custom for ClickHouse
  )
}}

-- Common Table Expressions (CTEs) to structure the query

-- 1. Source Data: Select from the 'gold_features' table.
--    This table is assumed to be created and populated by an upstream Spark process.
--    It should contain one row per proponente (applicant) per analysis period,
--    with all relevant features.
with source_features as (
  select
    proponente_id, -- Unique identifier for the applicant
    data_snapshot as data_analise, -- Date of the feature snapshot or analysis

    -- Example features (these would come from your Spark job output)
    score_credito, -- A pre-calculated credit score
    renda_estimada_anual,
    divida_total_consolidada,
    avg_ndvi_90d, -- Average NDVI over the last 90 days
    distancia_porto_km, -- Distance to the nearest port/silo
    anos_experiencia_agricola,
    possui_seguro_agricola, -- Boolean or 0/1
    area_total_cultivada_ha,
    percentual_area_irrigada,
    historico_pagamentos_atrasados, -- Count of late payments
    consultas_credito_ultimos_6m, -- Number of credit inquiries

    -- Timestamps for tracking
    data_carga_gold -- Timestamp when data was loaded into gold layer

  from {{ source('clickhouse_gold', 'gold_proponente_features') }} -- Using dbt source macro
  -- Replace 'clickhouse_gold' with your source name and 'gold_proponente_features' with your actual table name.
  -- This source would be defined in a .yml file in the models/ directory (e.g., models/sources.yml)
  -- Example source.yml:
  -- version: 2
  -- sources:
  --   - name: clickhouse_gold
  --     database: default # Or your ClickHouse database name if not default
  --     schema: gold     # Schema where your gold tables reside
  --     tables:
  --       - name: gold_proponente_features

  -- Optional: Add a filter for incremental loads if this model is incremental
  {% if is_incremental() %}
    -- this filter will only be applied on an incremental run
    where data_carga_gold > (select max(data_carga_gold) from {{ this }})
  {% endif %}
),

-- 2. Risk Calculation Logic (Example)
--    This CTE applies business rules to calculate a risk score or category.
--    This is highly dependent on your specific credit risk model.
calculated_risk as (
  select
    sf.*, -- Select all columns from source_features

    -- Example: Simple risk categorization based on credit score and debt-to-income ratio
    case
      when sf.score_credito < 500 then 'ALTO_RISCO'
      when sf.score_credito < 650 or (sf.divida_total_consolidada / nullif(sf.renda_estimada_anual, 0) > 0.6) then 'MEDIO_RISCO'
      when sf.avg_ndvi_90d < 0.3 and sf.area_total_cultivada_ha > 100 then 'MEDIO_RISCO' -- Low NDVI on large area
      else 'BAIXO_RISCO'
    end as categoria_risco_calculada,

    -- Example: A more nuanced risk score (0-100, lower is better risk)
    -- This is a placeholder for a potentially complex scoring model
    ( (1 - (sf.score_credito / 1000.0)) * 50 + -- Max 50 points from credit score (assuming score is 0-1000)
      (sf.historico_pagamentos_atrasados * 5) + -- 5 points per late payment
      (sf.consultas_credito_ultimos_6m * 2)     -- 2 points per recent inquiry
      -- Add other factors...
    ) as score_risco_detalhado,

    -- NDVI based flag
    case
        when sf.avg_ndvi_90d < 0.25 then 'NDVI_MUITO_BAIXO'
        when sf.avg_ndvi_90d < 0.4 then 'NDVI_BAIXO'
        else 'NDVI_NORMAL'
    end as flag_ndvi_status

  from source_features sf
),

-- 3. Final Selection and Renaming
--    Select the columns for the final fact table.
--    Rename columns for clarity if needed.
final_selection as (
  select
    proponente_id,
    data_analise,

    -- Key metrics and features
    score_credito,
    renda_estimada_anual,
    divida_total_consolidada,
    avg_ndvi_90d,
    distancia_porto_km,
    anos_experiencia_agricola,
    possui_seguro_agricola,
    area_total_cultivada_ha,
    percentual_area_irrigada,
    historico_pagamentos_atrasados,
    consultas_credito_ultimos_6m,

    -- Calculated risk fields
    categoria_risco_calculada,
    round(score_risco_detalhado, 2) as score_risco_detalhado, -- Round to 2 decimal places
    flag_ndvi_status,

    -- Metadata / Timestamps
    data_carga_gold,
    now() as data_processamento_dbt -- Timestamp of dbt processing

  from calculated_risk
)

-- Final SELECT statement for the model
select * from final_selection

-- Note: For this model to work, you need to:
-- 1. Define the source 'clickhouse_gold.gold_proponente_features' in a schema.yml file
--    (e.g., dbt_project/models/sources.yml or within a marts.yml).
--    Example `sources.yml`:
--    ```yaml
--    version: 2
--    sources:
--      - name: clickhouse_gold # This is how you'll refer to the source in ref() or source()
--        # database: your_clickhouse_database # Optional: Defaults to profile target's database
--        schema: gold # The schema where the gold table exists
--        tables:
--          - name: gold_proponente_features # The actual table name in ClickHouse
--            # columns: # Optionally define columns for documentation and testing
--            #   - name: proponente_id
--            #     description: "Unique identifier for the applicant."
--            #     tests:
--            #       - unique
--            #       - not_null
--   ```
-- 2. Ensure the `gold_proponente_features` table is populated in ClickHouse by your Spark job
--    before this dbt model runs.
-- 3. Configure your `profiles.yml` for dbt to connect to your ClickHouse instance.
-- 4. If materializing as 'incremental', ensure your incremental strategy and `unique_key` are appropriate.
--    For ClickHouse, common incremental strategies might involve `append` or more complex logic using
--    engines like `ReplacingMergeTree` if you need to update existing records based on a key.
--    The provided example is for a table materialization.
--
-- To run this model: `dbt run --select fct_analise_risco`
-- To test (if tests are defined): `dbt test --select fct_analise_risco`
