
    
    

with all_values as (

    select
        finalidade_credito as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by finalidade_credito

)

select *
from all_values
where value_field not in (
    'CUSTEIO_SAFRA','INVESTIMENTO_MAQUINARIO','AMPLIACAO_AREA','OUTROS'
)


