select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."not_null_silver_dados_produtor_595551ef13797787e76116376ea69d73"
    
      
    ) dbt_internal_test