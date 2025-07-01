





with validation_errors as (

    select
        proponente_id, data_solicitacao
    from "iceberg"."silver"."silver_dados_produtores_agro_trino"
    group by proponente_id, data_solicitacao
    having count(*) > 1

)

select *
from validation_errors


