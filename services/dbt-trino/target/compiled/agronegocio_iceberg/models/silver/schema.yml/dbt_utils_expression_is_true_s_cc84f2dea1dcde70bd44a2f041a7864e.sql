



select
    *
from "iceberg"."silver"."silver_dados_produtores_agro_trino"

where not(valor_solicitado_credito > 0)

