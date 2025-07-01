



select
    *
from (select * from "iceberg"."silver"."silver_dados_produtores_agro_trino" where localizacao_latitude IS NOT NULL) dbt_subquery

where not(localizacao_latitude BETWEEN -90 AND 90)

