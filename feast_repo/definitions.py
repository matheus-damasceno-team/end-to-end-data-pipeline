from datetime import timedelta
from feast import Entity, FeatureView, FileSource, Field
from feast.types import Float64, Int64, String
from feast.data_format import ParquetFormat

# Definição das entidades
proponente = Entity(
    name="proponente",
    join_keys=["proponente_id"],
    description="Entidade representando um proponente de crédito agrícola"
)

localizacao = Entity(
    name="localizacao",
    join_keys=["localizacao_key"],
    description="Entidade representando uma localização"
)

risco_cultura = Entity(
    name="risco_cultura", 
    join_keys=["risco_cultura_key"],
    description="Entidade representando uma combinação de faixa de risco e cultura"
)

# Fonte de dados para features do proponente
proponente_source = FileSource(
    name="proponente_features_source",
    path="/feast_repo/data/gold_proponente_features.parquet",
    timestamp_field="feature_timestamp",
    file_format=ParquetFormat(),
)

# Fonte de dados para features de localização
location_source = FileSource(
    name="location_features_source", 
    path="/feast_repo/data/gold_location_features.parquet",
    timestamp_field="feature_timestamp",
    file_format=ParquetFormat(),
)

# Fonte de dados para features de risco
risk_source = FileSource(
    name="risk_features_source",
    path="/feast_repo/data/gold_risk_features.parquet",
    timestamp_field="feature_timestamp", 
    file_format=ParquetFormat(),
)

# Feature View para features do proponente
proponente_features_view = FeatureView(
    name="proponente_features",
    entities=[proponente],
    ttl=timedelta(days=30),
    schema=[
        Field(name="total_solicitacoes", dtype=Int64),
        Field(name="valor_total_solicitado", dtype=Float64),
        Field(name="valor_medio_solicitado", dtype=Float64),
        Field(name="serasa_score_medio", dtype=Float64),
        Field(name="anos_experiencia_medio", dtype=Float64),
        Field(name="area_media_hectares", dtype=Float64),
    ],
    source=proponente_source,
    tags={"team": "data-science", "layer": "gold"},
)

# Feature View para features de localização
location_features_view = FeatureView(
    name="location_features",
    entities=[localizacao],
    ttl=timedelta(days=7),
    schema=[
        Field(name="total_proponentes", dtype=Int64),
        Field(name="valor_total_solicitado", dtype=Float64),
        Field(name="valor_medio_solicitado", dtype=Float64),
        Field(name="area_total_hectares", dtype=Float64),
        Field(name="serasa_score_medio", dtype=Float64),
    ],
    source=location_source,
    tags={"team": "data-science", "layer": "gold"},
)

# Feature View para features de risco
risk_features_view = FeatureView(
    name="risk_features",
    entities=[risco_cultura],
    ttl=timedelta(days=14),
    schema=[
        Field(name="total_solicitacoes", dtype=Int64),
        Field(name="valor_total_solicitado", dtype=Float64),
        Field(name="valor_medio_solicitado", dtype=Float64),
        Field(name="area_total_hectares", dtype=Float64),
        Field(name="serasa_score_medio", dtype=Float64),
    ],
    source=risk_source,
    tags={"team": "data-science", "layer": "gold"},
)