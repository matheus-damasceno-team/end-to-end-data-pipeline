select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."dbt_utils_expression_is_true_s_cc84f2dea1dcde70bd44a2f041a7864e"
    
      
    ) dbt_internal_test