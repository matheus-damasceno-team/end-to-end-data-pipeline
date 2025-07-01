
    
    

with all_values as (

    select
        cultura_principal as value_field,
        count(*) as n_records

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by cultura_principal

)

select *
from all_values
where value_field not in (
    'SOJA','MILHO','CAFE','CANA_DE_ACUCAR','ALGODAO','FRUTICULTURA','TRIGO','ARROZ','FEIJAO','EUCALIPTO'
)


