
    
    

with all_values as (

    select
        registro_valido as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by registro_valido

)

select *
from all_values
where value_field not in (
    'True'
)


