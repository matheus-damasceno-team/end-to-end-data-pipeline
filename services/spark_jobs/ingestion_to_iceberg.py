import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import StructType, StringType, DoubleType, BooleanType, IntegerType, TimestampType, MapType

# Kafka and Schema Registry Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')
SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', 'http://schema-registry:8081')
ICEBERG_WAREHOUSE = os.getenv('ICEBERG_WAREHOUSE', 's3a://warehouse/iceberg_data')
ICEBERG_TABLE_NAME = os.getenv('ICEBERG_TABLE_NAME', 'bronze.dados_produtores')

# Avro Schema (should match the producer's schema)
# This schema is simplified for demonstration. In a real scenario, you'd load it from a file or Schema Registry.
# For this Spark job, we'll define it directly or fetch from Schema Registry if the Avro deserializer supports it.
# For simplicity, let's define a basic schema that matches the producer's output structure.
# In a production scenario, you'd typically fetch this from the Schema Registry.
# However, for `from_avro` function, it expects the schema as a string.
# We'll use a simplified version for now, assuming the full schema is available.

# Define the schema for the incoming Kafka Avro message payload
# This should precisely match the 'DadosProdutor' schema defined in producer_schema.avsc
AVRO_SCHEMA = """
{
  "type": "record",
  "name": "DadosProdutor",
  "namespace": "com.example.produtor",
  "fields": [
    {"name": "proponente_id", "type": "string"},
    {"name": "data_solicitacao", "type": "string"},
    {"name": "cpf_cnpj", "type": "string"},
    {"name": "nome_razao_social", "type": "string"},
    {"name": "tipo_pessoa", "type": "string"},
    {"name": "renda_bruta_anual_declarada", "type": "double"},
    {"name": "valor_solicitado_credito", "type": "double"},
    {"name": "finalidade_credito", "type": "string"},
    {
      "name": "localizacao_propriedade",
      "type": {
        "type": "record",
        "name": "LocalizacaoPropriedade",
        "fields": [
          {"name": "latitude", "type": "double"},
          {"name": "longitude", "type": "double"},
          {"name": "municipio", "type": "string"},
          {"name": "uf", "type": "string"}
        ]
      }
    },
    {"name": "area_total_hectares", "type": "double"},
    {"name": "cultura_principal", "type": "string"},
    {"name": "possui_experiencia_atividade", "type": "boolean"},
    {"name": "anos_experiencia", "type": "int"},
    {
      "name": "fontes_dados_adicionais",
      "type": {
        "type": "record",
        "name": "FontesDadosAdicionais",
        "fields": [
          {"name": "serasa_score", "type": ["null", "int"], "default": null},
          {"name": "ibama_autuacoes_ativas", "type": ["null", "boolean"], "default": null},
          {"name": "numero_matricula_imovel", "type": "string"}
        ]
      }
    },
    {
      "name": "metadata_evento",
      "type": {
        "type": "record",
        "name": "MetadataEvento",
        "fields": [
          {"name": "versao_schema", "type": "string"},
          {"name": "origem_dados", "type": "string"},
          {"name": "timestamp_geracao_evento", "type": "double"}
        ]
      }
    }
  ]
}
"""

def create_spark_session():
    """Creates and configures a SparkSession for Iceberg and Kafka."""
    spark = SparkSession.builder \
        .appName("KafkaToIcebergIngestion") \
        .config("spark.sql.catalog.hive_catalog", "org.apache.iceberg.spark.SparkSessionCatalog") \
        .config("spark.sql.catalog.hive_catalog.type", "hive") \
        .config("spark.sql.catalog.hive_catalog.uri", "thrift://hive-metastore:9083") \
        .config("spark.sql.catalog.hive_catalog.warehouse", ICEBERG_WAREHOUSE) \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.jars.packages", "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.apache.spark:spark-avro_2.12:3.5.0,org.apache.hadoop:hadoop-aws:3.3.1,com.amazonaws:aws-java-sdk-bundle:1.11.901") \
        .config("spark.sql.shuffle.partitions", "200") \
        .config("spark.default.parallelism", "200") \
        .config("spark.sql.files.maxRecordsPerFile", "1000000")\
        .getOrCreate()
    return spark

def main():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN") # Reduce verbosity

    print(f"Starting Kafka to Iceberg ingestion for topic: {KAFKA_TOPIC}")

    # Read from Kafka
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # Deserialize Avro messages
    # The 'value' column from Kafka is binary. Use from_avro to parse it.
    # We need to provide the schema registry URL for from_avro to fetch the schema.
    # Note: spark-avro's from_avro can directly fetch from schema registry if configured.
    # For simplicity, we're providing the schema string directly here.
    # In a production setup, you'd configure the schema registry client for spark-avro.
    # Example: .option("avroSchema", AVRO_SCHEMA) or .option("schema.registry.url", SCHEMA_REGISTRY_URL)
    # The `from_avro` function in Spark 3.x can take a schema string directly.
    # If using a schema registry, you might need to use `confluent-kafka-avro` library in a UDF
    # or ensure your Spark-Avro connector is configured to use it.
    # For now, let's assume the schema is known and provided.

    # If the Avro messages are produced with Confluent Schema Registry, the `from_avro` function
    # from `spark-avro` library can be configured to fetch the schema from the registry.
    # However, the `spark-avro` library's `from_avro` function in Spark 3.5 does not directly
    # support `schema.registry.url` option. It expects the schema as a string or a path.
    # For a full integration with Confluent Schema Registry, you might need to use a custom UDF
    # or a different connector.
    # For simplicity and direct use of `from_avro`, we'll provide the schema string.
    # This assumes the Avro messages are self-contained or the schema is known beforehand.

    parsed_df = kafka_df.select(from_avro(col("value"), AVRO_SCHEMA).alias("data")) \
                        .select("data.*") \
                        .withColumn("ingestion_timestamp", col("data_solicitacao").cast(TimestampType())) # Add ingestion timestamp

    # Create the Iceberg table if it doesn't exist
    # This is a one-time operation. In a production setup, you'd manage table creation separately.
    # We'll try to create it if it doesn't exist.
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {ICEBERG_TABLE_NAME} (
            proponente_id STRING,
            data_solicitacao STRING,
            cpf_cnpj STRING,
            nome_razao_social STRING,
            tipo_pessoa STRING,
            renda_bruta_anual_declarada DOUBLE,
            valor_solicitado_credito DOUBLE,
            finalidade_credito STRING,
            localizacao_propriedade STRUCT<latitude: DOUBLE, longitude: DOUBLE, municipio: STRING, uf: STRING>,
            area_total_hectares DOUBLE,
            cultura_principal STRING,
            possui_experiencia_atividade BOOLEAN,
            anos_experiencia INT,
            fontes_dados_adicionais STRUCT<serasa_score: INT, ibama_autuacoes_ativas: BOOLEAN, numero_matricula_imovel: STRING>,
            metadata_evento STRUCT<versao_schema: STRING, origem_dados: STRING, timestamp_geracao_evento: DOUBLE>,
            ingestion_timestamp TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (years(ingestion_timestamp), tipo_pessoa)
        LOCATION '{ICEBERG_WAREHOUSE}/{ICEBERG_TABLE_NAME.replace('.', '/')}'
        TBLPROPERTIES (
            'write.format.default'='parquet',
            'write.parquet.compression-codec'='zstd',
            'write.metadata.delete-after-commit.enabled'='true',
            'write.metadata.previous-versions-max'='100',
            'commit.retry.num-retries'='10'
        )
    """)
    print(f"Iceberg table {ICEBERG_TABLE_NAME} ensured to exist.")

    # Write to Iceberg table in append mode
    # Use 'append' mode for streaming ingestion.
    # For production, consider 'complete' or 'update' if your logic requires it.
    query = parsed_df.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .trigger(processingTime="30 seconds") \
        .option("checkpointLocation", f"{ICEBERG_WAREHOUSE}/_checkpoints/{ICEBERG_TABLE_NAME.replace('.', '_')}") \
        .option("fanout.enabled", "true") \
        .option("path", ICEBERG_WAREHOUSE) \
        .toTable(ICEBERG_TABLE_NAME)

    print(f"Streaming query started for {ICEBERG_TABLE_NAME}. Waiting for termination...")
    query.awaitTermination()

if __name__ == "__main__":
    main()
