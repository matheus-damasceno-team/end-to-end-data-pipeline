
    
    

with all_values as (

    select
        faixa_risco_credito as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by faixa_risco_credito

)

select *
from all_values
where value_field not in (
    'SEM_SCORE','MUITO_ALTO','ALTO','MEDIO','BAIXO'
)


