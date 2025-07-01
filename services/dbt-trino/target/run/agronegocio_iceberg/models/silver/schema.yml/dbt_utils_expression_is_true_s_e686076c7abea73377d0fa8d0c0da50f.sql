select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."dbt_utils_expression_is_true_s_e686076c7abea73377d0fa8d0c0da50f"
    
      
    ) dbt_internal_test