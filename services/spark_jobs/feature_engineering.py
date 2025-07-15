from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit, year, month, dayofmonth, current_timestamp, udf
from pyspark.sql.types import FloatType, StringType, StructType, StructField, TimestampType, IntegerType, DoubleType, BooleanType
import os
from datetime import datetime

# MinIO/S3 Configuration will be picked from spark-defaults.conf which is mounted.
# Hive Metastore Configuration will be picked from spark-defaults.conf.

# Define input and output paths using s3a protocol for MinIO
BRONZE_DATA_PATH = "s3a://bronze/" # Raw JSON data from ingestion_consumer.py
# The ingestion_consumer.py writes data in subdirectories like YYYY/MM/DD/HH/*.json
# So, Spark will read all JSON files under the bronze bucket.
# Example: "s3a://bronze/*/*/*/*/*.json" or "s3a://bronze/" and Spark will scan recursively.

GOLD_FEATURES_PATH = "s3a://gold/proponente_features_parquet/" # Output for Feast FileSource
GOLD_CLICKHOUSE_TABLE_PATH = "s3a://gold/proponente_features_clickhouse/" # Output for ClickHouse table

# Define table names for Hive Metastore registration
GOLD_HIVE_TABLE_NAME = "gold_agri_features" # For Trino/Superset access via Hive (points to GOLD_FEATURES_PATH)

def create_spark_session():
    """Creates and returns a Spark session."""
    # Configurations for MinIO and Hive Metastore are expected to be in spark-defaults.conf
    spark = SparkSession.builder \
        .appName("AgronegocioFeatureEngineering") \
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic") \
        .enableHiveSupport() \
        .getOrCreate()

    # Log effective S3 endpoint for verification (optional)
    s3_endpoint = spark.sparkContext._jsc.hadoopConfiguration().get("fs.s3a.endpoint")
    hive_uris = spark.conf.get("spark.hive.metastore.uris")
    print(f"Spark session created. Effective S3A Endpoint: {s3_endpoint}, Hive URIs: {hive_uris}")
    return spark

# --- Mock UDFs for feature calculation (replace with real logic) ---
def calculate_ndvi_mock(latitude, longitude, date_solicitacao):
    # In a real scenario, this would query a geospatial service or raster data
    # For now, a mock value based on location/date components
    return round(random.uniform(0.1, 0.9), 4) if latitude and longitude else 0.5

def calculate_distance_to_port_mock(latitude, longitude):
    # Mock: calculate distance to a fixed port (e.g., Santos Port: -23.9875, -46.3039)
    # Real implementation would use a geocoding service or distance calculation library
    if latitude and longitude:
        # Simple mock, not actual Haversine
        return round(abs(latitude - (-23.9875)) * 100 + abs(longitude - (-46.3039)) * 100, 2)
    return 500.0 # Default distance

import random
calculate_ndvi_udf = udf(calculate_ndvi_mock, DoubleType())
calculate_distance_to_port_udf = udf(calculate_distance_to_port_mock, DoubleType())

# Example UDF for a simple credit score
def calculate_credit_score_mock(renda, historico_pagamentos, consultas_recentes):
    score = 600
    if renda:
        score += (renda / 10000) # income component
    if historico_pagamentos:
        score -= (historico_pagamentos * 20) # penalties
    if consultas_recentes:
        score -= (consultas_recentes * 10) # penalties
    return max(300, min(850, int(score))) # typical score range

calculate_credit_score_udf = udf(calculate_credit_score_mock, IntegerType())


def main():
    spark = create_spark_session()

    print(f"Reading data from Bronze layer: {BRONZE_DATA_PATH}")
    try:
        # Define the schema for the raw JSON data from the producer
        # This schema must match the structure of JSON files in the bronze bucket.
        bronze_schema = StructType([
            StructField("proponente_id", StringType(), True),
            StructField("data_solicitacao", StringType(), True), # Read as String, then convert to Timestamp
            StructField("cpf_cnpj", StringType(), True),
            StructField("nome_razao_social", StringType(), True),
            StructField("tipo_pessoa", StringType(), True),
            StructField("renda_bruta_anual_declarada", DoubleType(), True),
            StructField("valor_solicitado_credito", DoubleType(), True),
            StructField("finalidade_credito", StringType(), True),
            StructField("localizacao_propriedade", StructType([
                StructField("latitude", DoubleType(), True),
                StructField("longitude", DoubleType(), True),
                StructField("municipio", StringType(), True),
                StructField("uf", StringType(), True)
            ]), True),
            StructField("area_total_hectares", DoubleType(), True),
            StructField("cultura_principal", StringType(), True),
            StructField("possui_experiencia_atividade", BooleanType(), True),
            StructField("anos_experiencia", IntegerType(), True),
            StructField("fontes_dados_adicionais", StructType([
                StructField("serasa_score", IntegerType(), True), # Can be null
                StructField("ibama_autuacoes_ativas", BooleanType(), True), # Can be null
                StructField("numero_matricula_imovel", StringType(), True)
            ]), True),
            StructField("metadata_evento", StructType([
                StructField("versao_schema", StringType(), True),
                StructField("origem_dados", StringType(), True),
                StructField("timestamp_geracao_evento", DoubleType(), True) # Read as Double (Unix timestamp)
            ]), True)
        ])

        # Read all JSON files from the bronze path.
        # Spark can read partitioned data (YYYY/MM/DD/HH/*.json) by pointing to the base path.
        bronze_df = spark.read.format("json") \
            .schema(bronze_schema) \
            .load(BRONZE_DATA_PATH) \
            .withColumn("data_solicitacao_ts", col("data_solicitacao").cast(TimestampType())) \
            .withColumn("timestamp_geracao_evento_ts", col("metadata_evento.timestamp_geracao_evento").cast(TimestampType()))

        print("Bronze data schema after loading and timestamp conversion:")
        bronze_df.printSchema()
        bronze_df.show(5, truncate=False)

    except Exception as e:
        print(f"Error reading from Bronze layer {BRONZE_DATA_PATH}: {e}")
        spark.stop()
        return

    # --- Feature Engineering ---
    print("Starting feature engineering...")

    # Use the converted timestamp column for features
    features_df = bronze_df.withColumn(
        "avg_ndvi_90d",
        calculate_ndvi_udf(
            col("localizacao_propriedade.latitude"),
            col("localizacao_propriedade.longitude"),
            col("data_solicitacao_ts") # Use the converted timestamp
        )
    ).withColumn(
        "distancia_porto_km",
        calculate_distance_to_port_udf(
            col("localizacao_propriedade.latitude"),
            col("localizacao_propriedade.longitude")
        )
    ).withColumn(
        "score_credito_externo", col("fontes_dados_adicionais.serasa_score") # Already IntegerType
    ).withColumn(
        "idade_cultura_predominante_dias", (rand() * 180 + 30).cast(IntegerType()) # Mock
    ).withColumn(
        "area_total_propriedade_ha", col("area_total_hectares") # Already DoubleType, Feast expects Float32
    ).withColumn(
        "percentual_endividamento_total", (rand() * 0.8 + 0.1) # Mock, already DoubleType
    ).withColumn(
        "data_snapshot", col("data_solicitacao_ts") # Key timestamp for Feast
    ).withColumn(
        "data_carga_gold", current_timestamp() # Processing timestamp for Gold layer
    ).withColumn("year", year(col("data_snapshot"))) \
     .withColumn("month", month(col("data_snapshot"))) \
     .withColumn("day", dayofmonth(col("data_snapshot")))

    # Select and cast columns for the Gold layer to match Feast and ClickHouse expectations
    gold_df_selected = features_df.select(
        col("proponente_id").alias("proponente_id"), # String
        col("avg_ndvi_90d").cast(FloatType()).alias("avg_ndvi_90d"), # Float
        col("distancia_porto_km").cast(FloatType()).alias("distancia_porto_km"), # Float - Corrected alias
        col("score_credito_externo").cast(IntegerType()).alias("score_credito_externo"), # Int
        col("idade_cultura_predominante_dias").cast(IntegerType()).alias("idade_cultura_predominante_dias"), # Int
        col("area_total_propriedade_ha").cast(FloatType()).alias("area_total_propriedade_ha"), # Float
        col("percentual_endividamento_total").cast(FloatType()).alias("percentual_endividamento_total"), # Float
        col("data_snapshot").cast(TimestampType()).alias("data_snapshot"), # Timestamp for Feast event_timestamp
        col("data_carga_gold").cast(TimestampType()).alias("data_carga_gold"), # Timestamp for Feast created_timestamp
        # Partitioning columns for ClickHouse S3 table
        col("year").cast(IntegerType()).alias("year"),
        col("month").cast(IntegerType()).alias("month"),
        col("day").cast(IntegerType()).alias("day")
    )

    print("Engineered features schema for Gold Layer (Feast & ClickHouse):")
    gold_df_selected.printSchema()
    gold_df_selected.show(5, truncate=False)

    # --- Write to Gold Layer (MinIO as Parquet for Feast FileSource) ---
    # This output is NOT partitioned by date, as Feast FileSource usually expects a single directory or file pattern.
    # If partitioning is desired for Feast source, adjust FileSource path and this write operation.
    feast_output_df = gold_df_selected.drop("year", "month", "day") # Drop date partitions for this specific output
    print(f"Writing features to Gold layer (Parquet for Feast): {GOLD_FEATURES_PATH}")
    try:
        feast_output_df.write \
            .mode("overwrite") \
            .format("parquet") \
            .save(GOLD_FEATURES_PATH)
        print(f"Successfully wrote Parquet features for Feast to {GOLD_FEATURES_PATH}")
    except Exception as e:
        print(f"Error writing Parquet features for Feast to {GOLD_FEATURES_PATH}: {e}")

    # --- Write to Gold Layer (MinIO as Parquet, partitioned for ClickHouse) ---
    # This output IS partitioned by year, month, day for ClickHouse S3 table.
    clickhouse_output_df = gold_df_selected # Contains year, month, day columns
    print(f"Writing features to Gold layer (Partitioned Parquet for ClickHouse): {GOLD_CLICKHOUSE_TABLE_PATH}")
    try:
        clickhouse_output_df.write \
            .partitionBy("year", "month", "day") \
            .mode("overwrite") \
            .format("parquet") \
            .save(GOLD_CLICKHOUSE_TABLE_PATH)
        print(f"Successfully wrote Partitioned Parquet for ClickHouse to {GOLD_CLICKHOUSE_TABLE_PATH}")
    except Exception as e:
        print(f"Error writing Partitioned Parquet for ClickHouse to {GOLD_CLICKHOUSE_TABLE_PATH}: {e}")

    # --- Optional: Register Gold table in Hive Metastore for Trino/Superset ---
    # This Hive table will point to the non-partitioned Feast data path for simplicity,
    # as it's a common analytical access pattern for the latest features.
    # If partitioned access via Hive is needed, point to GOLD_CLICKHOUSE_TABLE_PATH and manage partitions.
    print(f"Registering Gold Hive table '{GOLD_HIVE_TABLE_NAME}' pointing to {GOLD_FEATURES_PATH}")
    try:
        # Use the schema from feast_output_df for the Hive table
        # Drop existing table if it exists to ensure schema consistency on overwrite
        spark.sql(f"DROP TABLE IF EXISTS default.{GOLD_HIVE_TABLE_NAME}")

        feast_output_df.write \
            .mode("overwrite") \
            .format("parquet") \
            .option("path", GOLD_FEATURES_PATH) \
            .saveAsTable(f"default.{GOLD_HIVE_TABLE_NAME}")

        print(f"Table default.{GOLD_HIVE_TABLE_NAME} created/updated in Hive Metastore, pointing to {GOLD_FEATURES_PATH}")

    except Exception as e:
        print(f"Error registering or updating table default.{GOLD_HIVE_TABLE_NAME} in Hive Metastore: {e}")

    print("Feature engineering job finished.")
    spark.stop()

if __name__ == "__main__":
    # Add random import for UDF mocks if not already present
    import random

    # Add year, month, dayofmonth functions to main scope if used in partitionBy directly on DataFrame
    from pyspark.sql.functions import year, month, dayofmonth, rand

    main()
