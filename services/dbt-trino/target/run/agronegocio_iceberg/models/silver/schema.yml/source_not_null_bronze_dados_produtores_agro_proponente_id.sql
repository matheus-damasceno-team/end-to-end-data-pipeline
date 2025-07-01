select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."source_not_null_bronze_dados_produtores_agro_proponente_id"
    
      
    ) dbt_internal_test