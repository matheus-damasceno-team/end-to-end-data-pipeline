



select
    *
from (select * from "iceberg"."silver"."silver_dados_produtores_agro_trino" where localizacao_longitude IS NOT NULL) dbt_subquery

where not(localizacao_longitude BETWEEN -180 AND 180)

