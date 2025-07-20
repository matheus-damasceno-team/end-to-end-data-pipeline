-- macros/trino_iceberg_utils.sql

-- Macro para criar schema se não existir
{% macro create_schema_if_not_exists(schema_name) %}
  {% set create_schema_query %}
    CREATE SCHEMA IF NOT EXISTS {{ var('iceberg_catalog') }}.{{ schema_name }}
  {% endset %}
  
  {% if execute %}
    {% do run_query(create_schema_query) %}
    {{ log("Schema " ~ schema_name ~ " criado/verificado", info=True) }}
  {% endif %}
{% endmacro %}

-- Macro para otimizar tabelas Iceberg no Trino
{% macro optimize_iceberg_table_trino(table_name) %}
  {% if execute %}
    {% set optimize_query %}
      ALTER TABLE {{ table_name }} EXECUTE optimize(file_size_threshold => '100MB')
    {% endset %}
    
    {% do run_query(optimize_query) %}
    {{ log("Tabela " ~ table_name ~ " otimizada", info=True) }}
  {% endif %}
{% endmacro %}

-- Macro para configuração incremental com Iceberg no Trino
{% macro iceberg_incremental_config(
    unique_key='proponente_id',
    partition_by=none,
    cluster_by=none
) %}
  {{
    config(
      materialized='incremental',
      unique_key=unique_key,
      incremental_strategy='merge',
      on_schema_change='append_new_columns',
      partition_by=partition_by,
      cluster_by=cluster_by
    )
  }}
{% endmacro %}

-- Macro para extrair campos de structs (equivalente ao safe_json_extract)
{% macro extract_struct_field(struct_field, field_name, data_type='varchar') %}
  CAST({{ struct_field }}.{{ field_name }} AS {{ data_type }})
{% endmacro %}

-- Macro para logging de estatísticas
{% macro log_table_stats(table_name) %}
  {% if execute %}
    {% set stats_query %}
      SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT proponente_id) as unique_proponentes,
        MIN(data_solicitacao) as min_date,
        MAX(data_solicitacao) as max_date,
        APPROX_DISTINCT(uf) as unique_states
      FROM {{ table_name }}
    {% endset %}
    
    {% set results = run_query(stats_query) %}
    {% if results %}
      {% set stats = results.rows[0] %}
      {{ log("===== Estatísticas de " ~ table_name ~ " =====", info=True) }}
      {{ log("Total de linhas: " ~ stats[0], info=True) }}
      {{ log("Proponentes únicos: " ~ stats[1], info=True) }}
      {{ log("Data mínima: " ~ stats[2], info=True) }}
      {{ log("Data máxima: " ~ stats[3], info=True) }}
      {{ log("Estados únicos: " ~ stats[4], info=True) }}
      {{ log("=====================================", info=True) }}
    {% endif %}
  {% endif %}
{% endmacro %}

-- Macro para validar integridade incremental
{% macro validate_incremental_load(this_table, source_table) %}
  {% if execute and is_incremental() %}
    {% set validation_query %}
      WITH source_max AS (
        SELECT MAX(ingestion_timestamp) as max_timestamp
        FROM {{ source_table }}
      ),
      target_max AS (
        SELECT MAX(ingestion_timestamp) as max_timestamp
        FROM {{ this_table }}
      )
      SELECT 
        s.max_timestamp as source_max,
        t.max_timestamp as target_max,
        s.max_timestamp > t.max_timestamp as has_new_data
      FROM source_max s, target_max t
    {% endset %}
    
    {% set results = run_query(validation_query) %}
    {% if results %}
      {% set validation = results.rows[0] %}
      {{ log("Validação Incremental:", info=True) }}
      {{ log("  - Último timestamp na origem: " ~ validation[0], info=True) }}
      {{ log("  - Último timestamp no destino: " ~ validation[1], info=True) }}
      {{ log("  - Há novos dados: " ~ validation[2], info=True) }}
    {% endif %}
  {% endif %}
{% endmacro %}

-- Macro para criar partições dinâmicas
{% macro create_dynamic_partitions() %}
  {% set partition_list = [] %}
  
  {% do partition_list.append("year(data_solicitacao)") %}
  {% do partition_list.append("month(data_solicitacao)") %}
  {% do partition_list.append("tipo_pessoa") %}
  
  {% if partition_list|length > 0 %}
    {{ return(partition_list) }}
  {% else %}
    {{ return([]) }}
  {% endif %}
{% endmacro %}

-- alteração de nome padrão

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}

        {{ default_schema }}

    {%- else -%}

        {{ custom_schema_name | trim }}

    {%- endif -%}

{%- endmacro %}