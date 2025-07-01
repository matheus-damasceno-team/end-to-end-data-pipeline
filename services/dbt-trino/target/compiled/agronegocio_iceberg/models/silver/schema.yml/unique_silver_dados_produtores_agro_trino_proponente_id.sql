
    
    

select
    proponente_id as unique_field,
    count(*) as n_records

from "iceberg"."silver"."silver_dados_produtores_agro_trino"
where proponente_id is not null
group by proponente_id
having count(*) > 1


