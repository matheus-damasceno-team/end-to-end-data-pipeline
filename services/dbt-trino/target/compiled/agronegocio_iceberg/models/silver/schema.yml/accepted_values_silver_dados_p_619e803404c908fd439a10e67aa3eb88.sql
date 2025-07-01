
    
    

with all_values as (

    select
        tipo_pessoa as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by tipo_pessoa

)

select *
from all_values
where value_field not in (
    'FISICA','JURIDICA'
)


