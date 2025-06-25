from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, lit, year, month, dayofmonth, current_timestamp, udf
from pyspark.sql.types import FloatType, StringType, StructType, StructField, TimestampType, IntegerType, DoubleType, BooleanType
import os
from datetime import datetime

# MinIO/S3 Configuration (passed via spark-defaults.conf or environment variables)
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "admin")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "password")
# MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")

# Hive Metastore Configuration (passed via spark-defaults.conf)
# HIVE_METASTORE_URIS = os.getenv("HIVE_METASTORE_URIS", "thrift://hive-metastore:9083")

# Define input and output paths (conceptual MinIO paths)
# Spark will use s3a:// protocol to interact with MinIO
SILVER_DATA_PATH = "s3a://silver/enriched_producer_data/" # Data from ingestion consumer + initial enrichment
GOLD_FEATURES_PATH = "s3a://gold/proponente_features_parquet/" # Output for Feast FileSource
GOLD_CLICKHOUSE_TABLE_PATH = "s3a://gold/proponente_features_clickhouse/" # Output for ClickHouse external table or direct load

# Define table names for Hive Metastore registration
GOLD_HIVE_TABLE_NAME = "gold_agri_features" # For Trino/Superset access via Hive
CLICKHOUSE_TARGET_TABLE_NAME = "gold_proponente_features" # Table in ClickHouse (dbt source)

def create_spark_session():
    """Creates and returns a Spark session configured for MinIO and Hive Metastore."""
    spark = SparkSession.builder \
        .appName("AgronegocioFeatureEngineering") \
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic") \
        .config("spark.hadoop.fs.s3a.endpoint", os.getenv("MINIO_ENDPOINT", "http://minio:9000")) \
        .config("spark.hadoop.fs.s3a.access.key", os.getenv("AWS_ACCESS_KEY_ID", "admin")) \
        .config("spark.hadoop.fs.s3a.secret.key", os.getenv("AWS_SECRET_ACCESS_KEY", "password")) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.sql.catalogImplementation", "hive") \
        .config("spark.hive.metastore.uris", os.getenv("HIVE_METASTORE_URIS", "thrift://hive-metastore:9083")) \
        .enableHiveSupport() \
        .getOrCreate()
    print("Spark session created with Hive support and S3A configured.")
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

    print(f"Reading data from Silver layer: {SILVER_DATA_PATH}")
    try:
        # Assuming silver data is partitioned by date of ingestion or event date
        # For this example, let's assume it's not explicitly partitioned in the read path
        # but the data contains relevant date columns.
        # The schema should ideally be predefined or inferred correctly.
        # This schema should match what the ingestion_consumer.py (or a previous Spark job) creates in Silver.
        silver_df_schema = StructType([
            StructField("proponente_id", StringType(), True),
            StructField("data_solicitacao", TimestampType(), True), # Changed from String to Timestamp
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
                StructField("serasa_score", IntegerType(), True),
                StructField("ibama_autuacoes_ativas", BooleanType(), True),
                StructField("numero_matricula_imovel", StringType(), True)
            ]), True),
            StructField("metadata_evento", StructType([
                StructField("versao_schema", StringType(), True),
                StructField("origem_dados", StringType(), True),
                StructField("timestamp_geracao_evento", TimestampType(), True) # Changed
            ]), True),
            # Add partition columns if Silver data is partitioned, e.g.,
            # StructField("year", IntegerType(), True),
            # StructField("month", IntegerType(), True),
            # StructField("day", IntegerType(), True)
        ])

        silver_df = spark.read.format("parquet") \
            .schema(silver_df_schema) \
            .load(SILVER_DATA_PATH)

        print("Silver data schema:")
        silver_df.printSchema()
        silver_df.show(5, truncate=False)

    except Exception as e:
        print(f"Error reading from Silver layer {SILVER_DATA_PATH}: {e}")
        spark.stop()
        return

    # --- Feature Engineering ---
    print("Starting feature engineering...")

    features_df = silver_df.withColumn(
        "avg_ndvi_90d",
        calculate_ndvi_udf(
            col("localizacao_propriedade.latitude"),
            col("localizacao_propriedade.longitude"),
            col("data_solicitacao") # Assuming NDVI is relevant around solicitation date
        )
    ).withColumn(
        "distancia_porto_km",
        calculate_distance_to_port_udf(
            col("localizacao_propriedade.latitude"),
            col("localizacao_propriedade.longitude")
        )
    ).withColumn( # Example features for Feast schema
        "score_credito_externo", col("fontes_dados_adicionais.serasa_score").cast(IntegerType())
    ).withColumn(
        "idade_cultura_predominante_dias", (rand() * 180 + 30).cast(IntegerType()) # Mock: 30-210 days
    ).withColumn(
        "area_total_propriedade_ha", col("area_total_hectares").cast(FloatType())
    ).withColumn(
        "percentual_endividamento_total",
        (rand() * 0.8 + 0.1).cast(FloatType()) # Mock: 10-90%
    ).withColumn( # Timestamps for Feast
        "data_snapshot", col("data_solicitacao").cast(TimestampType()) # Use solicitation date as snapshot time
    ).withColumn(
        "data_carga_gold", current_timestamp() # Timestamp for when this Gold record is created
    )

    # Select only the columns required for the Gold layer / Feast
    # Ensure these match the schema in feast_repo/definitions.py
    gold_df = features_df.select(
        "proponente_id",
        "avg_ndvi_90d",
        "distancia_porto_km",
        "score_credito_externo",
        "idade_cultura_predominante_dias",
        "area_total_propriedade_ha",
        "percentual_endividamento_total",
        "data_snapshot", # Event timestamp for Feast
        "data_carga_gold"  # Created timestamp for Feast
    )

    print("Engineered features schema (for Feast and ClickHouse):")
    gold_df.printSchema()
    gold_df.show(5, truncate=False)

    # --- Write to Gold Layer (MinIO as Parquet for Feast FileSource) ---
    print(f"Writing features to Gold layer (Parquet for Feast): {GOLD_FEATURES_PATH}")
    try:
        gold_df.write \
            .mode("overwrite") \
            .format("parquet") \
            .save(GOLD_FEATURES_PATH)
        print(f"Successfully wrote Parquet features to {GOLD_FEATURES_PATH}")
    except Exception as e:
        print(f"Error writing Parquet features to {GOLD_FEATURES_PATH}: {e}")
        # spark.stop() # Decide if to stop or continue if other writes are pending
        # return

    # --- Write to Gold Layer (MinIO as Parquet for ClickHouse external table or direct load) ---
    # This could be the same data, or formatted differently if needed.
    # For simplicity, let's write the same gold_df.
    # dbt will then pick this up from ClickHouse (assuming ClickHouse table points to this S3 path or data is loaded).
    print(f"Writing features to Gold layer (Parquet for ClickHouse): {GOLD_CLICKHOUSE_TABLE_PATH}")
    try:
        gold_df.write \
            .partitionBy("year", "month", "day") # Example partitioning for ClickHouse table
            .mode("overwrite") \
            .format("parquet") \
            .save(GOLD_CLICKHOUSE_TABLE_PATH)
        print(f"Successfully wrote Parquet features for ClickHouse to {GOLD_CLICKHOUSE_TABLE_PATH}")
    except Exception as e:
        print(f"Error writing Parquet features for ClickHouse to {GOLD_CLICKHOUSE_TABLE_PATH}: {e}")

    # --- Optional: Register Gold table in Hive Metastore for Trino/Superset ---
    # This makes the data at GOLD_FEATURES_PATH queryable via SQL engines like Trino.
    print(f"Registering Gold table '{GOLD_HIVE_TABLE_NAME}' in Hive Metastore...")
    try:
        # For external tables, schema must be provided if not inferring
        # Construct DDL for creating an external table
        # This is a simplified example; column types should be precise
        # gold_df_for_hive = spark.read.parquet(GOLD_FEATURES_PATH) # Re-read to get schema for DDL

        # It's often better to manage Hive table DDL separately or use Spark's saveAsTable for managed tables.
        # For external tables on S3, ensure location is correct.
        # spark.sql(f"DROP TABLE IF EXISTS default.{GOLD_HIVE_TABLE_NAME}") # Use database name if not default
        # gold_df.write.mode("overwrite").saveAsTable(f"default.{GOLD_HIVE_TABLE_NAME}", format="parquet", path=GOLD_FEATURES_PATH)

        # A common way to create an external table if it doesn't exist:
        if not spark.catalog.tableExists(f"default.{GOLD_HIVE_TABLE_NAME}"):
             spark.catalog.createExternalTable(
                 tableName=f"default.{GOLD_HIVE_TABLE_NAME}",
                 path=GOLD_FEATURES_PATH, # Path to the Parquet data for Feast (not the ClickHouse one)
                 source="parquet"
                 # schema=gold_df.schema # Provide schema if needed, or let it infer
             )
             print(f"External table default.{GOLD_HIVE_TABLE_NAME} created in Hive Metastore pointing to {GOLD_FEATURES_PATH}")
        else:
            # If table exists, refresh partitions if it's partitioned, or simply note it.
            # For non-partitioned external Parquet, just ensure data is updated at path.
            # For partitioned tables: spark.sql(f"MSCK REPAIR TABLE default.{GOLD_HIVE_TABLE_NAME}")
            print(f"Table default.{GOLD_HIVE_TABLE_NAME} already exists in Hive Metastore.")
            # Consider refreshing table metadata if data path content changes:
            spark.sql(f"REFRESH TABLE default.{GOLD_HIVE_TABLE_NAME}")
            print(f"Refreshed table default.{GOLD_HIVE_TABLE_NAME}.")


    except Exception as e:
        print(f"Error registering table in Hive Metastore: {e}")

    print("Feature engineering job finished.")
    spark.stop()

if __name__ == "__main__":
    # Add random import for UDF mocks if not already present
    import random

    # Add year, month, dayofmonth functions to main scope if used in partitionBy directly on DataFrame
    from pyspark.sql.functions import year, month, dayofmonth, rand

    main()
