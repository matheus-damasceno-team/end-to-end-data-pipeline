# Feast Feature Definitions
# PATH: feast_repo/definitions.py

from datetime import timedelta
from feast import Entity, FeatureView, Field
from feast.types import Float64, String
from feast.data_source import FileSource

# Define farm entity
farm = Entity(
    name="farm_id",
    description="Farm identifier"
)

# Simple file source for demo
farm_features_source = FileSource(
    name="farm_features_source",
    path="/tmp/farm_features.parquet",  # Placeholder path
    timestamp_field="event_timestamp",
)

# Feature view for farm metrics
farm_features_fv = FeatureView(
    name="farm_features",
    entities=[farm],
    ttl=timedelta(days=1),
    schema=[
        Field(name="avg_temperature", dtype=Float64),
        Field(name="avg_humidity", dtype=Float64),
        Field(name="avg_soil_moisture", dtype=Float64),
        Field(name="farm_region", dtype=String),
    ],
    source=farm_features_source,
    tags={"team": "agri"},
)