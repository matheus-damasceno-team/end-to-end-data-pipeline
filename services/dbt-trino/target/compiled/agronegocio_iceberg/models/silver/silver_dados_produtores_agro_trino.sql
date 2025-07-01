

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
    FROM "iceberg"."bronze"."dados_produtores_agro"
    
    
        WHERE ingestion_timestamp > (SELECT COALESCE(MAX(ingestion_timestamp), TIMESTAMP '1970-01-01 00:00:00') FROM "iceberg"."silver"."silver_dados_produtores_agro_trino")
    
),

silver_transformations AS (
    SELECT 
        proponente_id,
        -- Conversão correta de bigint (Unix timestamp) para timestamp
        FROM_UNIXTIME(data_solicitacao / 1000) AS data_solicitacao,
        cpf_cnpj,
        nome_razao_social,
        tipo_pessoa,
        renda_bruta_anual_declarada,
        valor_solicitado_credito,
        finalidade_credito,
        latitude,
        longitude,
        municipio,
        uf,
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
        FROM_UNIXTIME(timestamp_geracao_evento / 1000) AS timestamp_geracao_evento,
        ingestion_timestamp,
        
        -- Transformações e enriquecimentos
        CASE 
            WHEN tipo_pessoa = 'FISICA' THEN 'Pessoa Física'
            WHEN tipo_pessoa = 'JURIDICA' THEN 'Pessoa Jurídica'
            ELSE 'Não Informado'
        END AS tipo_pessoa_desc,
        
        CASE 
            WHEN renda_bruta_anual_declarada < 100000 THEN 'Pequeno'
            WHEN renda_bruta_anual_declarada < 500000 THEN 'Médio'
            ELSE 'Grande'
        END AS porte_produtor,
        
        CASE 
            WHEN area_total_hectares < 50 THEN 'Pequena Propriedade'
            WHEN area_total_hectares < 500 THEN 'Média Propriedade'
            ELSE 'Grande Propriedade'
        END AS classificacao_area,
        
        -- Cálculo do percentual de crédito em relação à renda
        CASE 
            WHEN renda_bruta_anual_declarada > 0 THEN 
                ROUND((valor_solicitado_credito / renda_bruta_anual_declarada) * 100, 2)
            ELSE 0
        END AS percentual_credito_renda,
        
        -- Score de risco simplificado
        CASE 
            WHEN serasa_score IS NULL THEN 'Sem Score'
            WHEN serasa_score >= 700 THEN 'Baixo Risco'
            WHEN serasa_score >= 500 THEN 'Médio Risco'
            ELSE 'Alto Risco'
        END AS classificacao_risco,
        
        -- Região baseada na UF
        CASE 
            WHEN uf IN ('SP', 'RJ', 'MG', 'ES') THEN 'Sudeste'
            WHEN uf IN ('PR', 'SC', 'RS') THEN 'Sul'
            WHEN uf IN ('GO', 'MT', 'MS', 'DF') THEN 'Centro-Oeste'
            WHEN uf IN ('BA', 'SE', 'AL', 'PE', 'PB', 'RN', 'CE', 'PI', 'MA') THEN 'Nordeste'
            WHEN uf IN ('AC', 'AM', 'AP', 'PA', 'RO', 'RR', 'TO') THEN 'Norte'
            ELSE 'Não Informado'
        END AS regiao,
        
        -- Timestamp de processamento
        CURRENT_TIMESTAMP AS data_processamento_silver
        
    FROM bronze_data
)

SELECT * FROM silver_transformations