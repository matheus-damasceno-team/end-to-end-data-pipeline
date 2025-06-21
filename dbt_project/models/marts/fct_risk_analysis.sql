{{
  config(
    materialized='table',
    schema='analytics',  -- Ensures this table is created in the 'analytics' schema
    engine='MergeTree()', -- Example ClickHouse engine, choose appropriately
    order_by='(proponent_id, analysis_date)', -- Example ordering key for MergeTree
    settings={
      'allow_nullable_key': 1 -- Example setting if your order_by key can be nullable
    }
  )
}}

-- This is a placeholder model for fct_risk_analysis.
-- In a real scenario, this model would perform complex joins and aggregations
-- from various source tables (e.g., staging tables populated from MinIO/Feast).

-- For demonstration, let's assume there's a source table named 'stg_proponent_features'
-- in the 'agri_db' database (or the default schema defined in profiles.yml).
-- This table would ideally be created by another dbt model or an external process
-- that loads data from your 'gold' MinIO layer or Feast offline store.

WITH proponent_features AS (
    -- Replace this with a valid source() or ref() to your actual source table
    -- For example: SELECT * FROM {{ source('staging', 'stg_proponent_features') }}
    -- Or: SELECT * FROM {{ ref('int_proponent_data_enriched') }}

    -- Dummy data for illustration if no source table exists yet:
    SELECT
        'prop_123' AS proponent_id,
        toDate('2023-10-26') AS analysis_date,
        750 AS credit_score,
        0.65 AS avg_ndvi_90d,
        150.5 AS distance_to_port_km,
        250000.00 AS requested_loan_amount,
        'pending_approval' AS loan_status,
        map('land_type', 'arable', 'soil_quality', 'good') AS additional_attributes, -- ClickHouse Map type
        array(10.0, 12.5, 11.0) AS monthly_rainfall_last_3m -- ClickHouse Array type
    UNION ALL
    SELECT
        'prop_456' AS proponent_id,
        toDate('2023-10-27') AS analysis_date,
        680 AS credit_score,
        0.55 AS avg_ndvi_90d,
        320.0 AS distance_to_port_km,
        150000.00 AS requested_loan_amount,
        'approved' AS loan_status,
        map('land_type', 'pasture', 'irrigation', 'yes') AS additional_attributes,
        array(8.0, 9.5, 10.0) AS monthly_rainfall_last_3m
    UNION ALL
    SELECT
        'prop_789' AS proponent_id,
        toDate('2023-10-28') AS analysis_date,
        810 AS credit_score,
        0.72 AS avg_ndvi_90d,
        80.2 AS distance_to_port_km,
        500000.00 AS requested_loan_amount,
        'rejected' AS loan_status,
        map('crop_type', 'soy', 'has_storage', 'no') AS additional_attributes,
        array(15.0, 14.5, 16.0) AS monthly_rainfall_last_3m
),

risk_calculation AS (
    SELECT
        proponent_id,
        analysis_date,
        credit_score,
        avg_ndvi_90d,
        distance_to_port_km,
        requested_loan_amount,
        loan_status,
        additional_attributes,
        monthly_rainfall_last_3m,

        -- Example risk scoring logic (highly simplified)
        CASE
            WHEN credit_score > 700 AND avg_ndvi_90d > 0.6 AND distance_to_port_km < 200 THEN 'Low Risk'
            WHEN credit_score > 650 AND avg_ndvi_90d > 0.5 THEN 'Medium Risk'
            ELSE 'High Risk'
        END AS calculated_risk_category,

        (credit_score * 0.4) + (avg_ndvi_90d * 100 * 0.3) + ((1/distance_to_port_km) * 100 * 0.3) AS composite_score_example,
        arraySum(monthly_rainfall_last_3m) as total_rainfall_last_3m

    FROM proponent_features
)

SELECT
    proponent_id,
    analysis_date,
    credit_score,
    avg_ndvi_90d,
    distance_to_port_km,
    requested_loan_amount,
    loan_status,
    calculated_risk_category,
    composite_score_example,
    total_rainfall_last_3m,
    additional_attributes,
    monthly_rainfall_last_3m,
    now() as dbt_last_updated_at -- Timestamp of when dbt ran this model

FROM risk_calculation

-- To run this model:
-- 1. Ensure ClickHouse is running and accessible by the dbt_service.
-- 2. Ensure your profiles.yml is correctly configured for ClickHouse.
-- 3. Run `dbt run --select fct_risk_analysis` or `dbt run` from the dbt_service container
--    or via `docker-compose run dbt_service run --select fct_risk_analysis`.

-- This will create/replace a table named 'fct_risk_analysis' in the 'analytics' schema
-- (or your default schema if 'analytics' is not specified/supported as schema for the connection)
-- in your ClickHouse database.
-- The schema is defined in the config block at the top or in dbt_project.yml.
-- The database is defined in your profiles.yml.
-- For ClickHouse, "schema" in dbt typically translates to "database" in ClickHouse terms,
-- so this table might be created as `analytics.fct_risk_analysis` if your connection
-- points to a default database and `analytics` is treated as a separate ClickHouse database,
-- or `your_default_db.fct_risk_analysis` if `schema` config in dbt is not creating a new DB.
-- The dbt-clickhouse adapter handles this translation. Often, `schema` in dbt will become
-- the database name, e.g., `CREATE TABLE analytics.fct_risk_analysis ...`.
-- If your ClickHouse user has permissions, dbt can create the database (schema) if it doesn't exist.
