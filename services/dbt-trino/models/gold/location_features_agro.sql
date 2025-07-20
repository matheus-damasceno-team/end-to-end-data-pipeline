{{
  config(
    materialized='incremental',
    unique_key=['localizacao_uf', 'localizacao_municipio'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    tags=['gold', 'features', 'feast', 'location']
  )
}}

WITH silver_base AS (
    SELECT *
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE registro_valido = true
      AND localizacao_uf IS NOT NULL
      AND localizacao_municipio IS NOT NULL
      AND TRIM(localizacao_uf) != ''
      AND TRIM(localizacao_municipio) != ''
    
    {% if is_incremental() %}
        AND processed_at > (SELECT COALESCE(MAX(feature_timestamp), TIMESTAMP '1970-01-01 00:00:00') FROM {{ this }})
    {% endif %}
),

-- Features de localização por UF e município
location_aggregations AS (
    SELECT 
        localizacao_uf,
        localizacao_municipio,
        
        -- Features de volume
        COUNT(*) as total_proponentes,
        COUNT(DISTINCT proponente_id) as proponentes_unicos,
        
        -- Features de crédito
        SUM(valor_solicitado_credito) as valor_total_solicitado,
        AVG(valor_solicitado_credito) as valor_medio_solicitado,
        COALESCE(STDDEV(CAST(valor_solicitado_credito AS DOUBLE)), 0.0) as valor_desvio_padrao,
        APPROX_PERCENTILE(valor_solicitado_credito, 0.5) as valor_mediano_solicitado,
        
        -- Features de área
        SUM(area_total_hectares) as area_total_hectares,
        AVG(area_total_hectares) as area_media_hectares,
        COALESCE(STDDEV(CAST(area_total_hectares AS DOUBLE)), 0.0) as area_desvio_padrao,
        
        -- Features de localização geográfica
        AVG(CAST(localizacao_latitude AS DOUBLE)) as latitude_media,
        AVG(CAST(localizacao_longitude AS DOUBLE)) as longitude_media,
        COALESCE(STDDEV(CAST(localizacao_latitude AS DOUBLE)), 0.0) as latitude_desvio_padrao,
        COALESCE(STDDEV(CAST(localizacao_longitude AS DOUBLE)), 0.0) as longitude_desvio_padrao,
        
        -- Features de risco
        COALESCE(AVG(CAST(serasa_score AS DOUBLE)), 0.0) as serasa_score_medio,
        COALESCE(STDDEV(CAST(serasa_score AS DOUBLE)), 0.0) as serasa_score_desvio_padrao,
        
        -- Features de experiência
        AVG(CAST(anos_experiencia AS DOUBLE)) as anos_experiencia_medio,
        
        -- Features de diversificação de culturas
        COUNT(DISTINCT cultura_principal) as diversidade_culturas,
        ARBITRARY(cultura_principal) as cultura_dominante,
        
        -- Features de finalidade
        COUNT(DISTINCT finalidade_credito) as diversidade_finalidades,
        ARBITRARY(finalidade_credito) as finalidade_dominante,
        
        -- Features de classificação de propriedade
        COUNT(DISTINCT classificacao_propriedade) as diversidade_classificacoes,
        ARBITRARY(classificacao_propriedade) as classificacao_dominante,
        
        -- Features de risco ambiental
        CAST(SUM(CASE WHEN ibama_autuacoes_ativas = true THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_autuacoes_ibama,
        
        -- Features temporais
        MAX(data_solicitacao) as ultima_solicitacao,
        MIN(data_solicitacao) as primeira_solicitacao,
        
        -- Features de distribuição por faixa de risco
        CAST(SUM(CASE WHEN faixa_risco_credito = 'BAIXO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_risco_baixo,
        CAST(SUM(CASE WHEN faixa_risco_credito = 'MEDIO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_risco_medio,
        CAST(SUM(CASE WHEN faixa_risco_credito = 'ALTO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_risco_alto,
        CAST(SUM(CASE WHEN faixa_risco_credito = 'MUITO_ALTO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_risco_muito_alto,
        
        -- Features de tipo de pessoa
        CAST(SUM(CASE WHEN tipo_pessoa = 'JURIDICA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_pessoa_juridica,
        
        MAX(processed_at) as ultima_atualizacao
        
    FROM silver_base
    GROUP BY localizacao_uf, localizacao_municipio
),

-- Features derivadas e calculadas
enhanced_location_features AS (
    SELECT 
        localizacao_uf,
        localizacao_municipio,
        
        -- Features básicas
        total_proponentes,
        proponentes_unicos,
        valor_total_solicitado,
        valor_medio_solicitado,
        valor_desvio_padrao,
        valor_mediano_solicitado,
        area_total_hectares,
        area_media_hectares,
        area_desvio_padrao,
        latitude_media,
        longitude_media,
        latitude_desvio_padrao,
        longitude_desvio_padrao,
        serasa_score_medio,
        serasa_score_desvio_padrao,
        anos_experiencia_medio,
        
        -- Features de diversificação
        diversidade_culturas,
        cultura_dominante,
        diversidade_finalidades,
        finalidade_dominante,
        diversidade_classificacoes,
        classificacao_dominante,
        
        -- Features de risco
        taxa_autuacoes_ibama,
        taxa_risco_baixo,
        taxa_risco_medio,
        taxa_risco_alto,
        taxa_risco_muito_alto,
        taxa_pessoa_juridica,
        
        -- Features temporais
        ultima_solicitacao,
        primeira_solicitacao,
        
        -- Features derivadas
        CASE 
            WHEN total_proponentes < 10 THEN 'BAIXA'
            WHEN total_proponentes < 50 THEN 'MEDIA'
            WHEN total_proponentes < 200 THEN 'ALTA'
            ELSE 'MUITO_ALTA'
        END as densidade_proponentes,
        
        CASE 
            WHEN valor_desvio_padrao IS NULL OR valor_desvio_padrao = 0 THEN 'HOMOGENEA'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.3 THEN 'ESTAVEL'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.6 THEN 'MODERADA'
            ELSE 'HETEROGENEA'
        END as homogeneidade_credito,
        
        CASE 
            WHEN diversidade_culturas = 1 THEN 'MONOCULTURA'
            WHEN diversidade_culturas <= 3 THEN 'POUCO_DIVERSIFICADA'
            WHEN diversidade_culturas <= 5 THEN 'MODERADAMENTE_DIVERSIFICADA'
            ELSE 'ALTAMENTE_DIVERSIFICADA'
        END as perfil_diversificacao_culturas,
        
        -- Indicadores de concentração
        valor_total_solicitado / NULLIF(area_total_hectares, 0) as intensidade_credito_por_hectare,
        CAST(proponentes_unicos AS DOUBLE) / NULLIF(total_proponentes, 0) as taxa_recorrencia,
        
        -- Features de posicionamento geográfico
        CASE 
            WHEN latitude_media > -10 THEN 'NORTE'
            WHEN latitude_media > -20 THEN 'NORDESTE'
            WHEN latitude_media > -30 THEN 'CENTRO_OESTE_SUDESTE'
            ELSE 'SUL'
        END as regiao_geografica,
        
        -- Indicador de risco regional
        (taxa_risco_alto + taxa_risco_muito_alto) as taxa_risco_elevado,
        
        -- Timestamp para Feast
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) as feature_timestamp,
        
        ultima_atualizacao
        
    FROM location_aggregations
)

SELECT 
    -- Chaves de localização (garantindo que não sejam null)
    COALESCE(localizacao_uf, 'UNKNOWN') as localizacao_uf,
    COALESCE(localizacao_municipio, 'UNKNOWN') as localizacao_municipio,
    CONCAT(COALESCE(localizacao_uf, 'UNKNOWN'), '-', COALESCE(localizacao_municipio, 'UNKNOWN')) as localizacao_key,
    
    -- Features numéricas
    total_proponentes,
    proponentes_unicos,
    valor_total_solicitado,
    valor_medio_solicitado,
    valor_desvio_padrao,
    valor_mediano_solicitado,
    area_total_hectares,
    area_media_hectares,
    area_desvio_padrao,
    latitude_media,
    longitude_media,
    latitude_desvio_padrao,
    longitude_desvio_padrao,
    serasa_score_medio,
    serasa_score_desvio_padrao,
    anos_experiencia_medio,
    diversidade_culturas,
    diversidade_finalidades,
    diversidade_classificacoes,
    taxa_autuacoes_ibama,
    taxa_risco_baixo,
    taxa_risco_medio,
    taxa_risco_alto,
    taxa_risco_muito_alto,
    taxa_pessoa_juridica,
    intensidade_credito_por_hectare,
    taxa_recorrencia,
    taxa_risco_elevado,
    
    -- Features categóricas
    cultura_dominante,
    finalidade_dominante,
    classificacao_dominante,
    densidade_proponentes,
    homogeneidade_credito,
    perfil_diversificacao_culturas,
    regiao_geografica,
    
    -- Features temporais
    ultima_solicitacao,
    primeira_solicitacao,
    
    -- Metadados
    feature_timestamp,
    ultima_atualizacao
    
FROM enhanced_location_features