select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
        select *
        from "iceberg"."silver_dbt_test__audit"."dbt_utils_unique_combination_o_21ab17eecd767bb91bd0b03d651fdd82"
    
      
    ) dbt_internal_test