



select
    *
from "iceberg"."silver"."silver_dados_produtores_agro_trino"

where not(area_total_hectares > 0)

