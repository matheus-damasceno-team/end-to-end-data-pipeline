select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."accepted_values_silver_dados_p_b5b1b95c0c1a169a7c112b782ea393ae"
    
      
    ) dbt_internal_test