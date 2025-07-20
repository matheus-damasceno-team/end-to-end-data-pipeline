{{
  config(
    materialized='incremental',
    unique_key=['proponente_id', 'data_solicitacao', 'valor_solicitado_credito'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns'
  )
}}

WITH bronze_data AS (
    SELECT 
        proponente_id,
        data_solicitacao,
        cpf_cnpj,
        nome_razao_social,
        tipo_pessoa,
        renda_bruta_anual_declarada,
        valor_solicitado_credito,
        finalidade_credito,
        -- Extraindo campos da estrutura localizacao_propriedade
        localizacao_propriedade.latitude AS latitude,
        localizacao_propriedade.longitude AS longitude,
        localizacao_propriedade.municipio AS municipio,
        localizacao_propriedade.uf AS uf,
        area_total_hectares,
        cultura_principal,
        possui_experiencia_atividade,
        anos_experiencia,
        -- Extraindo campos da estrutura fontes_dados_adicionais
        fontes_dados_adicionais.serasa_score AS serasa_score,
        fontes_dados_adicionais.ibama_autuacoes_ativas AS ibama_autuacoes_ativas,
        fontes_dados_adicionais.numero_matricula_imovel AS numero_matricula_imovel,
        -- Extraindo campos da estrutura metadata_evento
        metadata_evento.versao_schema AS versao_schema,
        metadata_evento.origem_dados AS origem_dados,
        metadata_evento.timestamp_geracao_evento AS timestamp_geracao_evento,
        ingestion_timestamp
    FROM {{ source('bronze', 'dados_produtores_agro') }}
    
    {% if is_incremental() %}
        WHERE ingestion_timestamp > (SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP '1970-01-01 00:00:00') FROM {{ this }})
    {% endif %}
),

silver_transformations AS (
    SELECT 
        proponente_id,
        -- Conversão correta de bigint (Unix timestamp em milissegundos) para timestamp
        CASE 
            WHEN data_solicitacao IS NOT NULL 
            THEN CAST(FROM_UNIXTIME(data_solicitacao / 1000) AS TIMESTAMP(6) WITH TIME ZONE)
            ELSE NULL 
        END AS data_solicitacao,
        cpf_cnpj,
        nome_razao_social,
        tipo_pessoa,
        renda_bruta_anual_declarada,
        valor_solicitado_credito,
        finalidade_credito,
        
        -- Campos de localização com aliases corretos para os testes
        latitude AS localizacao_latitude,
        longitude AS localizacao_longitude,
        municipio AS localizacao_municipio,
        uf AS localizacao_uf,
        
        area_total_hectares,
        cultura_principal,
        possui_experiencia_atividade,
        anos_experiencia,
        serasa_score,
        ibama_autuacoes_ativas,
        numero_matricula_imovel,
        versao_schema,
        origem_dados,
        
        -- Conversão correta de bigint para timestamp
        CASE 
            WHEN timestamp_geracao_evento IS NOT NULL 
            THEN CAST(FROM_UNIXTIME(timestamp_geracao_evento / 1000) AS TIMESTAMP(6) WITH TIME ZONE)
            ELSE NULL 
        END AS timestamp_geracao_evento,
        
        CAST(ingestion_timestamp AS TIMESTAMP(6) WITH TIME ZONE) AS ingestion_timestamp,
        
        -- Campos adicionais exigidos pelos testes
        CASE 
            WHEN area_total_hectares < 50 THEN 'MINIFUNDIO'
            WHEN area_total_hectares < 200 THEN 'PEQUENA'
            WHEN area_total_hectares < 1000 THEN 'MEDIA'
            ELSE 'GRANDE'
        END AS classificacao_propriedade,
        
        CASE 
            WHEN serasa_score IS NULL THEN 'SEM_SCORE'
            WHEN serasa_score >= 700 THEN 'BAIXO'
            WHEN serasa_score >= 500 THEN 'MEDIO'
            WHEN serasa_score >= 300 THEN 'ALTO'
            ELSE 'MUITO_ALTO'
        END AS faixa_risco_credito,
        
        -- Campo de validação
        CASE 
            WHEN cpf_cnpj IS NOT NULL 
                AND valor_solicitado_credito > 0 
                AND area_total_hectares > 0 
                AND uf IS NOT NULL 
            THEN TRUE 
            ELSE FALSE 
        END AS registro_valido,
        
        -- Timestamp de processamento
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) AS processed_at,
        
        -- Hash para detecção de mudanças
        TO_HEX(MD5(
            TO_UTF8(CONCAT(
                COALESCE(CAST(proponente_id AS VARCHAR), ''),
                COALESCE(CAST(data_solicitacao AS VARCHAR), ''),
                COALESCE(CAST(valor_solicitado_credito AS VARCHAR), ''),
                COALESCE(CAST(area_total_hectares AS VARCHAR), ''),
                COALESCE(uf, '')
            ))
        )) AS row_hash
        
    FROM bronze_data
    WHERE proponente_id IS NOT NULL
)

SELECT * FROM silver_transformations