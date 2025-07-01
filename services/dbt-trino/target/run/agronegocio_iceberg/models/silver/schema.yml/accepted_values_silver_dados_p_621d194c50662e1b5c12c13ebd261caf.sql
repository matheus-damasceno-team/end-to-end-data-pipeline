select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."accepted_values_silver_dados_p_621d194c50662e1b5c12c13ebd261caf"
    
      
    ) dbt_internal_test