-- back compat for old kwarg name
  
  
        
            
            
        

        

        merge into "iceberg"."silver"."silver_dados_produtores_agro_trino" as DBT_INTERNAL_DEST
            using "iceberg"."silver"."silver_dados_produtores_agro_trino__dbt_tmp" as DBT_INTERNAL_SOURCE
            on (
                DBT_INTERNAL_SOURCE.proponente_id = DBT_INTERNAL_DEST.proponente_id
            )

        
        when matched then update set
            "proponente_id" = DBT_INTERNAL_SOURCE."proponente_id","data_solicitacao" = DBT_INTERNAL_SOURCE."data_solicitacao","cpf_cnpj" = DBT_INTERNAL_SOURCE."cpf_cnpj","nome_razao_social" = DBT_INTERNAL_SOURCE."nome_razao_social","tipo_pessoa" = DBT_INTERNAL_SOURCE."tipo_pessoa","renda_bruta_anual_declarada" = DBT_INTERNAL_SOURCE."renda_bruta_anual_declarada","valor_solicitado_credito" = DBT_INTERNAL_SOURCE."valor_solicitado_credito","finalidade_credito" = DBT_INTERNAL_SOURCE."finalidade_credito","latitude" = DBT_INTERNAL_SOURCE."latitude","longitude" = DBT_INTERNAL_SOURCE."longitude","municipio" = DBT_INTERNAL_SOURCE."municipio","uf" = DBT_INTERNAL_SOURCE."uf","area_total_hectares" = DBT_INTERNAL_SOURCE."area_total_hectares","cultura_principal" = DBT_INTERNAL_SOURCE."cultura_principal","possui_experiencia_atividade" = DBT_INTERNAL_SOURCE."possui_experiencia_atividade","anos_experiencia" = DBT_INTERNAL_SOURCE."anos_experiencia","serasa_score" = DBT_INTERNAL_SOURCE."serasa_score","ibama_autuacoes_ativas" = DBT_INTERNAL_SOURCE."ibama_autuacoes_ativas","numero_matricula_imovel" = DBT_INTERNAL_SOURCE."numero_matricula_imovel","versao_schema" = DBT_INTERNAL_SOURCE."versao_schema","origem_dados" = DBT_INTERNAL_SOURCE."origem_dados","timestamp_geracao_evento" = DBT_INTERNAL_SOURCE."timestamp_geracao_evento","ingestion_timestamp" = DBT_INTERNAL_SOURCE."ingestion_timestamp","tipo_pessoa_desc" = DBT_INTERNAL_SOURCE."tipo_pessoa_desc","porte_produtor" = DBT_INTERNAL_SOURCE."porte_produtor","classificacao_area" = DBT_INTERNAL_SOURCE."classificacao_area","percentual_credito_renda" = DBT_INTERNAL_SOURCE."percentual_credito_renda","classificacao_risco" = DBT_INTERNAL_SOURCE."classificacao_risco","regiao" = DBT_INTERNAL_SOURCE."regiao","data_processamento_silver" = DBT_INTERNAL_SOURCE."data_processamento_silver"
        

        when not matched then insert
            ("proponente_id", "data_solicitacao", "cpf_cnpj", "nome_razao_social", "tipo_pessoa", "renda_bruta_anual_declarada", "valor_solicitado_credito", "finalidade_credito", "latitude", "longitude", "municipio", "uf", "area_total_hectares", "cultura_principal", "possui_experiencia_atividade", "anos_experiencia", "serasa_score", "ibama_autuacoes_ativas", "numero_matricula_imovel", "versao_schema", "origem_dados", "timestamp_geracao_evento", "ingestion_timestamp", "tipo_pessoa_desc", "porte_produtor", "classificacao_area", "percentual_credito_renda", "classificacao_risco", "regiao", "data_processamento_silver")
        values
            (DBT_INTERNAL_SOURCE."proponente_id", DBT_INTERNAL_SOURCE."data_solicitacao", DBT_INTERNAL_SOURCE."cpf_cnpj", DBT_INTERNAL_SOURCE."nome_razao_social", DBT_INTERNAL_SOURCE."tipo_pessoa", DBT_INTERNAL_SOURCE."renda_bruta_anual_declarada", DBT_INTERNAL_SOURCE."valor_solicitado_credito", DBT_INTERNAL_SOURCE."finalidade_credito", DBT_INTERNAL_SOURCE."latitude", DBT_INTERNAL_SOURCE."longitude", DBT_INTERNAL_SOURCE."municipio", DBT_INTERNAL_SOURCE."uf", DBT_INTERNAL_SOURCE."area_total_hectares", DBT_INTERNAL_SOURCE."cultura_principal", DBT_INTERNAL_SOURCE."possui_experiencia_atividade", DBT_INTERNAL_SOURCE."anos_experiencia", DBT_INTERNAL_SOURCE."serasa_score", DBT_INTERNAL_SOURCE."ibama_autuacoes_ativas", DBT_INTERNAL_SOURCE."numero_matricula_imovel", DBT_INTERNAL_SOURCE."versao_schema", DBT_INTERNAL_SOURCE."origem_dados", DBT_INTERNAL_SOURCE."timestamp_geracao_evento", DBT_INTERNAL_SOURCE."ingestion_timestamp", DBT_INTERNAL_SOURCE."tipo_pessoa_desc", DBT_INTERNAL_SOURCE."porte_produtor", DBT_INTERNAL_SOURCE."classificacao_area", DBT_INTERNAL_SOURCE."percentual_credito_renda", DBT_INTERNAL_SOURCE."classificacao_risco", DBT_INTERNAL_SOURCE."regiao", DBT_INTERNAL_SOURCE."data_processamento_silver")

    
