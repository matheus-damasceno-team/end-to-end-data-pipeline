{{
  config(
    materialized='incremental',
    unique_key='proponente_id',
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    tags=['gold', 'features', 'feast']
  )
}}

WITH silver_base AS (
    SELECT *
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE registro_valido = true
      AND proponente_id IS NOT NULL
      AND TRIM(proponente_id) != ''
    
    {% if is_incremental() %}
        AND processed_at > (SELECT COALESCE(MAX(feature_timestamp), TIMESTAMP '1970-01-01 00:00:00') FROM {{ this }})
    {% endif %}
),

-- Features de agregação por proponente
proponente_aggregations AS (
    SELECT 
        proponente_id,
        COUNT(*) as total_solicitacoes,
        SUM(valor_solicitado_credito) as valor_total_solicitado,
        AVG(valor_solicitado_credito) as valor_medio_solicitado,
        MAX(valor_solicitado_credito) as valor_maximo_solicitado,
        MIN(valor_solicitado_credito) as valor_minimo_solicitado,
        STDDEV(CAST(valor_solicitado_credito AS DOUBLE)) as valor_desvio_padrao,
        
        -- Features temporais
        MAX(data_solicitacao) as ultima_solicitacao,
        MIN(data_solicitacao) as primeira_solicitacao,
        DATE_DIFF('day', MIN(data_solicitacao), MAX(data_solicitacao)) as dias_entre_primeira_ultima,
        
        -- Features de risco
        AVG(CAST(serasa_score AS DOUBLE)) as serasa_score_medio,
        MAX(serasa_score) as serasa_score_maximo,
        MIN(serasa_score) as serasa_score_minimo,
        
        -- Features de localização
        AVG(CAST(localizacao_latitude AS DOUBLE)) as latitude_media,
        AVG(CAST(localizacao_longitude AS DOUBLE)) as longitude_media,
        AVG(CAST(area_total_hectares AS DOUBLE)) as area_media_hectares,
        
        -- Features categóricas (simplificado para Trino)
        ARBITRARY(finalidade_credito) as finalidade_mais_comum,
        ARBITRARY(cultura_principal) as cultura_mais_comum,
        ARBITRARY(classificacao_propriedade) as classificacao_mais_comum,
        ARBITRARY(faixa_risco_credito) as faixa_risco_mais_comum,
        
        -- Features de diversificação
        COUNT(DISTINCT finalidade_credito) as diversidade_finalidades,
        COUNT(DISTINCT cultura_principal) as diversidade_culturas,
        COUNT(DISTINCT localizacao_uf) as diversidade_ufs,
        
        -- Features de experiência
        AVG(CAST(anos_experiencia AS DOUBLE)) as anos_experiencia_medio,
        MAX(anos_experiencia) as anos_experiencia_maximo,
        
        -- Features de regularidade
        CAST(SUM(CASE WHEN ibama_autuacoes_ativas = true THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_autuacoes_ibama,
        
        -- Timestamp para controle
        MAX(processed_at) as ultima_atualizacao
        
    FROM silver_base
    GROUP BY proponente_id
),

-- Features derivadas e calculadas
enhanced_features AS (
    SELECT 
        proponente_id,
        
        -- Features básicas
        total_solicitacoes,
        valor_total_solicitado,
        valor_medio_solicitado,
        valor_maximo_solicitado,
        valor_minimo_solicitado,
        valor_desvio_padrao,
        
        -- Features temporais
        ultima_solicitacao,
        primeira_solicitacao,
        dias_entre_primeira_ultima,
        
        -- Features de risco
        serasa_score_medio,
        serasa_score_maximo,
        serasa_score_minimo,
        
        -- Features de localização
        latitude_media,
        longitude_media,
        area_media_hectares,
        
        -- Features categóricas
        finalidade_mais_comum,
        cultura_mais_comum,
        classificacao_mais_comum,
        faixa_risco_mais_comum,
        
        -- Features de diversificação
        diversidade_finalidades,
        diversidade_culturas,
        diversidade_ufs,
        
        -- Features de experiência
        anos_experiencia_medio,
        anos_experiencia_maximo,
        
        -- Features de regularidade
        taxa_autuacoes_ibama,
        
        -- Features derivadas
        CASE 
            WHEN total_solicitacoes = 1 THEN 'NOVO'
            WHEN total_solicitacoes <= 5 THEN 'RECORRENTE'
            WHEN total_solicitacoes <= 10 THEN 'FREQUENTE'
            ELSE 'MUITO_FREQUENTE'
        END as perfil_frequencia,
        
        CASE 
            WHEN valor_desvio_padrao IS NULL OR valor_desvio_padrao = 0 THEN 'CONSISTENTE'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.2 THEN 'ESTAVEL'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.5 THEN 'MODERADO'
            ELSE 'VOLATIL'
        END as perfil_volatilidade,
        
        CASE 
            WHEN diversidade_finalidades = 1 THEN 'ESPECIALIZADO'
            WHEN diversidade_finalidades <= 2 THEN 'FOCADO'
            ELSE 'DIVERSIFICADO'
        END as perfil_diversificacao,
        
        -- Indicadores de risco
        CASE 
            WHEN serasa_score_medio IS NULL THEN 1
            WHEN serasa_score_medio < 300 THEN 1
            WHEN serasa_score_medio < 500 THEN 0.8
            WHEN serasa_score_medio < 700 THEN 0.6
            ELSE 0.3
        END as indicador_risco_score,
        
        CASE 
            WHEN taxa_autuacoes_ibama > 0.5 THEN 1
            WHEN taxa_autuacoes_ibama > 0.2 THEN 0.8
            WHEN taxa_autuacoes_ibama > 0 THEN 0.6
            ELSE 0.3
        END as indicador_risco_ambiental,
        
        -- Métricas de produtividade
        valor_total_solicitado / NULLIF(area_media_hectares, 0) as valor_por_hectare,
        
        -- Features de sazonalidade (baseado na última solicitação)
        EXTRACT(MONTH FROM ultima_solicitacao) as mes_ultima_solicitacao,
        EXTRACT(QUARTER FROM ultima_solicitacao) as trimestre_ultima_solicitacao,
        
        -- Timestamp para Feast
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) as feature_timestamp,
        
        ultima_atualizacao
        
    FROM proponente_aggregations
)

SELECT 
    -- Chave primária (garantindo que não seja null)
    COALESCE(proponente_id, 'UNKNOWN') as proponente_id,
    
    -- Features numéricas
    total_solicitacoes,
    valor_total_solicitado,
    valor_medio_solicitado,
    valor_maximo_solicitado,
    valor_minimo_solicitado,
    valor_desvio_padrao,
    dias_entre_primeira_ultima,
    serasa_score_medio,
    serasa_score_maximo,
    serasa_score_minimo,
    latitude_media,
    longitude_media,
    area_media_hectares,
    diversidade_finalidades,
    diversidade_culturas,
    diversidade_ufs,
    anos_experiencia_medio,
    anos_experiencia_maximo,
    taxa_autuacoes_ibama,
    indicador_risco_score,
    indicador_risco_ambiental,
    valor_por_hectare,
    mes_ultima_solicitacao,
    trimestre_ultima_solicitacao,
    
    -- Features categóricas
    finalidade_mais_comum,
    cultura_mais_comum,
    classificacao_mais_comum,
    faixa_risco_mais_comum,
    perfil_frequencia,
    perfil_volatilidade,
    perfil_diversificacao,
    
    -- Features temporais
    ultima_solicitacao,
    primeira_solicitacao,
    
    -- Metadados
    feature_timestamp,
    ultima_atualizacao
    
FROM enhanced_features