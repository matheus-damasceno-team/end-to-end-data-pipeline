select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."not_null_silver_dados_produtores_agro_trino_cpf_cnpj"
    
      
    ) dbt_internal_test