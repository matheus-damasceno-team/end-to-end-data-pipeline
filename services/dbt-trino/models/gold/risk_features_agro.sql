{{
  config(
    materialized='incremental',
    unique_key=['faixa_risco_credito', 'cultura_principal'],
    incremental_strategy='merge',
    on_schema_change='append_new_columns',
    tags=['gold', 'features', 'feast', 'risk']
  )
}}

WITH silver_base AS (
    SELECT *
    FROM {{ ref('silver_dados_produtores_agro_trino') }}
    WHERE registro_valido = true
      AND faixa_risco_credito IS NOT NULL
      AND cultura_principal IS NOT NULL
      AND TRIM(faixa_risco_credito) != ''
      AND TRIM(cultura_principal) != ''
    
    {% if is_incremental() %}
        AND processed_at > (SELECT COALESCE(MAX(feature_timestamp), TIMESTAMP '1970-01-01 00:00:00') FROM {{ this }})
    {% endif %}
),

-- Features de risco por faixa de risco e cultura
risk_aggregations AS (
    SELECT 
        faixa_risco_credito,
        cultura_principal,
        
        -- Features de volume
        COUNT(*) as total_solicitacoes,
        COUNT(DISTINCT proponente_id) as proponentes_unicos,
        
        -- Features de crédito
        SUM(valor_solicitado_credito) as valor_total_solicitado,
        AVG(valor_solicitado_credito) as valor_medio_solicitado,
        STDDEV(CAST(valor_solicitado_credito AS DOUBLE)) as valor_desvio_padrao,
        APPROX_PERCENTILE(valor_solicitado_credito, 0.25) as valor_p25,
        APPROX_PERCENTILE(valor_solicitado_credito, 0.5) as valor_mediano,
        APPROX_PERCENTILE(valor_solicitado_credito, 0.75) as valor_p75,
        APPROX_PERCENTILE(valor_solicitado_credito, 0.9) as valor_p90,
        
        -- Features de área
        SUM(area_total_hectares) as area_total_hectares,
        AVG(area_total_hectares) as area_media_hectares,
        STDDEV(CAST(area_total_hectares AS DOUBLE)) as area_desvio_padrao,
        
        -- Features de score de crédito
        AVG(CAST(serasa_score AS DOUBLE)) as serasa_score_medio,
        STDDEV(CAST(serasa_score AS DOUBLE)) as serasa_score_desvio_padrao,
        MIN(serasa_score) as serasa_score_minimo,
        MAX(serasa_score) as serasa_score_maximo,
        
        -- Features de experiência
        AVG(CAST(anos_experiencia AS DOUBLE)) as anos_experiencia_medio,
        STDDEV(CAST(anos_experiencia AS DOUBLE)) as anos_experiencia_desvio_padrao,
        
        -- Features de distribuição por tipo de pessoa
        CAST(SUM(CASE WHEN tipo_pessoa = 'JURIDICA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_pessoa_juridica,
        
        -- Features de distribuição por classificação de propriedade
        CAST(SUM(CASE WHEN classificacao_propriedade = 'MINIFUNDIO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_minifundio,
        CAST(SUM(CASE WHEN classificacao_propriedade = 'PEQUENA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_pequena,
        CAST(SUM(CASE WHEN classificacao_propriedade = 'MEDIA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_media,
        CAST(SUM(CASE WHEN classificacao_propriedade = 'GRANDE' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_grande,
        
        -- Features de distribuição por finalidade
        CAST(SUM(CASE WHEN finalidade_credito = 'CUSTEIO_SAFRA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_custeio_safra,
        CAST(SUM(CASE WHEN finalidade_credito = 'INVESTIMENTO_MAQUINARIO' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_investimento_maquinario,
        CAST(SUM(CASE WHEN finalidade_credito = 'AMPLIACAO_AREA' THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_ampliacao_area,
        
        -- Features de risco ambiental
        CAST(SUM(CASE WHEN ibama_autuacoes_ativas = true THEN 1 ELSE 0 END) AS DOUBLE) / COUNT(*) as taxa_autuacoes_ibama,
        
        -- Features de distribuição geográfica
        COUNT(DISTINCT localizacao_uf) as diversidade_ufs,
        COUNT(DISTINCT localizacao_municipio) as diversidade_municipios,
        
        -- Features temporais
        MAX(data_solicitacao) as ultima_solicitacao,
        MIN(data_solicitacao) as primeira_solicitacao,
        
        MAX(processed_at) as ultima_atualizacao
        
    FROM silver_base
    GROUP BY faixa_risco_credito, cultura_principal
),

-- Features derivadas e calculadas
enhanced_risk_features AS (
    SELECT 
        faixa_risco_credito,
        cultura_principal,
        
        -- Features básicas
        total_solicitacoes,
        proponentes_unicos,
        valor_total_solicitado,
        valor_medio_solicitado,
        valor_desvio_padrao,
        valor_p25,
        valor_mediano,
        valor_p75,
        valor_p90,
        area_total_hectares,
        area_media_hectares,
        area_desvio_padrao,
        serasa_score_medio,
        serasa_score_desvio_padrao,
        serasa_score_minimo,
        serasa_score_maximo,
        anos_experiencia_medio,
        anos_experiencia_desvio_padrao,
        
        -- Features de distribuição
        taxa_pessoa_juridica,
        taxa_minifundio,
        taxa_pequena,
        taxa_media,
        taxa_grande,
        taxa_custeio_safra,
        taxa_investimento_maquinario,
        taxa_ampliacao_area,
        taxa_autuacoes_ibama,
        diversidade_ufs,
        diversidade_municipios,
        
        -- Features temporais
        ultima_solicitacao,
        primeira_solicitacao,
        
        -- Features derivadas
        CASE 
            WHEN total_solicitacoes < 10 THEN 'BAIXO_VOLUME'
            WHEN total_solicitacoes < 50 THEN 'MEDIO_VOLUME'
            WHEN total_solicitacoes < 200 THEN 'ALTO_VOLUME'
            ELSE 'MUITO_ALTO_VOLUME'
        END as volume_solicitacoes,
        
        CASE 
            WHEN valor_desvio_padrao IS NULL OR valor_desvio_padrao = 0 THEN 'HOMOGENEO'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.3 THEN 'ESTAVEL'
            WHEN valor_desvio_padrao / valor_medio_solicitado < 0.6 THEN 'MODERADO'
            ELSE 'VOLATIL'
        END as volatilidade_credito,
        
        -- Indicadores de risco derivados
        CASE 
            WHEN faixa_risco_credito = 'BAIXO' THEN 0.1
            WHEN faixa_risco_credito = 'MEDIO' THEN 0.3
            WHEN faixa_risco_credito = 'ALTO' THEN 0.6
            WHEN faixa_risco_credito = 'MUITO_ALTO' THEN 0.9
            ELSE 0.5
        END as peso_risco_base,
        
        -- Ajuste de risco por cultura
        CASE 
            WHEN cultura_principal IN ('SOJA', 'MILHO', 'CAFE') THEN 0.9  -- Culturas mais estáveis
            WHEN cultura_principal IN ('CANA_DE_ACUCAR', 'ALGODAO') THEN 1.0  -- Culturas médias
            WHEN cultura_principal IN ('FRUTICULTURA', 'TRIGO') THEN 1.1  -- Culturas mais voláteis
            ELSE 1.0
        END as fator_risco_cultura,
        
        -- Indicadores de concentração
        valor_total_solicitado / NULLIF(area_total_hectares, 0) as intensidade_credito_por_hectare,
        CAST(proponentes_unicos AS DOUBLE) / NULLIF(total_solicitacoes, 0) as taxa_recorrencia,
        
        -- Features de perfil por faixa de risco
        CASE 
            WHEN taxa_pessoa_juridica > 0.7 THEN 'PREDOMINANTEMENTE_JURIDICA'
            WHEN taxa_pessoa_juridica > 0.3 THEN 'MISTA'
            ELSE 'PREDOMINANTEMENTE_FISICA'
        END as perfil_tipo_pessoa,
        
        CASE 
            WHEN taxa_custeio_safra > 0.6 THEN 'FOCO_CUSTEIO'
            WHEN taxa_investimento_maquinario > 0.4 THEN 'FOCO_INVESTIMENTO'
            WHEN taxa_ampliacao_area > 0.3 THEN 'FOCO_EXPANSAO'
            ELSE 'DIVERSIFICADO'
        END as perfil_finalidade,
        
        -- Indicador de risco final
        CASE 
            WHEN faixa_risco_credito = 'BAIXO' THEN 0.1
            WHEN faixa_risco_credito = 'MEDIO' THEN 0.3
            WHEN faixa_risco_credito = 'ALTO' THEN 0.6
            WHEN faixa_risco_credito = 'MUITO_ALTO' THEN 0.9
            ELSE 0.5
        END * 
        CASE 
            WHEN cultura_principal IN ('SOJA', 'MILHO', 'CAFE') THEN 0.9
            WHEN cultura_principal IN ('CANA_DE_ACUCAR', 'ALGODAO') THEN 1.0
            WHEN cultura_principal IN ('FRUTICULTURA', 'TRIGO') THEN 1.1
            ELSE 1.0
        END * 
        CASE 
            WHEN taxa_autuacoes_ibama > 0.3 THEN 1.2
            WHEN taxa_autuacoes_ibama > 0.1 THEN 1.1
            ELSE 1.0
        END as score_risco_ajustado,
        
        -- Timestamp para Feast
        CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6) WITH TIME ZONE) as feature_timestamp,
        
        ultima_atualizacao
        
    FROM risk_aggregations
)

SELECT 
    -- Chaves de risco (garantindo que não sejam null)
    COALESCE(faixa_risco_credito, 'UNKNOWN') as faixa_risco_credito,
    COALESCE(cultura_principal, 'UNKNOWN') as cultura_principal,
    CONCAT(COALESCE(faixa_risco_credito, 'UNKNOWN'), '-', COALESCE(cultura_principal, 'UNKNOWN')) as risco_cultura_key,
    
    -- Features numéricas
    total_solicitacoes,
    proponentes_unicos,
    valor_total_solicitado,
    valor_medio_solicitado,
    valor_desvio_padrao,
    valor_p25,
    valor_mediano,
    valor_p75,
    valor_p90,
    area_total_hectares,
    area_media_hectares,
    area_desvio_padrao,
    serasa_score_medio,
    serasa_score_desvio_padrao,
    serasa_score_minimo,
    serasa_score_maximo,
    anos_experiencia_medio,
    anos_experiencia_desvio_padrao,
    taxa_pessoa_juridica,
    taxa_minifundio,
    taxa_pequena,
    taxa_media,
    taxa_grande,
    taxa_custeio_safra,
    taxa_investimento_maquinario,
    taxa_ampliacao_area,
    taxa_autuacoes_ibama,
    diversidade_ufs,
    diversidade_municipios,
    peso_risco_base,
    fator_risco_cultura,
    intensidade_credito_por_hectare,
    taxa_recorrencia,
    score_risco_ajustado,
    
    -- Features categóricas
    volume_solicitacoes,
    volatilidade_credito,
    perfil_tipo_pessoa,
    perfil_finalidade,
    
    -- Features temporais
    ultima_solicitacao,
    primeira_solicitacao,
    
    -- Metadados
    feature_timestamp,
    ultima_atualizacao
    
FROM enhanced_risk_features