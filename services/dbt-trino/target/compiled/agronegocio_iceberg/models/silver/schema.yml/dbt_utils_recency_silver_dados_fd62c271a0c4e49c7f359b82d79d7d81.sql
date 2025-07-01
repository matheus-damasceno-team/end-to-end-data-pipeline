






with recency as (

    select 

      
      
        max(processed_at) as most_recent

    from "iceberg"."silver"."silver_dados_produtores_agro_trino"

    

)

select

    
    most_recent,
    cast(date_add('hour', -24, current_timestamp) as timestamp) as threshold

from recency
where most_recent < cast(date_add('hour', -24, current_timestamp) as timestamp)

