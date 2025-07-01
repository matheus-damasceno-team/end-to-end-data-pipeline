select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."accepted_values_silver_dados_p_619e803404c908fd439a10e67aa3eb88"
    
      
    ) dbt_internal_test