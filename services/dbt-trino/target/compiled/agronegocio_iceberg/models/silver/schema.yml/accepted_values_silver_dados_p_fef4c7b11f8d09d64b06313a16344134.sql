
    
    

with all_values as (

    select
        classificacao_propriedade as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by classificacao_propriedade

)

select *
from all_values
where value_field not in (
    'MINIFUNDIO','PEQUENA','MEDIA','GRANDE'
)


