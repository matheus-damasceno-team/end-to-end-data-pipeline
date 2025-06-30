import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.types import LongType

# Kafka and Iceberg Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')
ICEBERG_WAREHOUSE = os.getenv('ICEBERG_WAREHOUSE', 's3a://warehouse')
ICEBERG_TABLE_NAME = os.getenv('ICEBERG_TABLE_NAME', 'bronze.dados_produtores_agro')

# Load Avro schema from file
def load_avro_schema(schema_path):
    with open(schema_path, 'r') as f:
        return f.read()

def create_spark_session():
    """Creates and configures a SparkSession for Iceberg and Kafka."""
    return SparkSession.builder \
        .appName("KafkaToIcebergFinal") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hive") \
        .config("spark.sql.catalog.spark_catalog.uri", "thrift://metastore:9083") \
        .config("spark.sql.catalog.spark_catalog.warehouse", ICEBERG_WAREHOUSE) \
        .config("spark.sql.catalog.spark_catalog.io-impl", "org.apache.iceberg.hadoop.HadoopFileIO") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "admin") \
        .config("spark.hadoop.fs.s3a.secret.key", "password") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
        .config("spark.hadoop.fs.s3a.region", "us-east-1") \
        .config("spark.hadoop.fs.s3a.bucket.all.region.lookup.disable", "true") \
        .config("spark.hadoop.fs.s3a.signer.override", "S3SignerType") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.hadoop.fs.s3a.fast.upload", "true") \
        .config("spark.hadoop.fs.s3a.multipart.size", "134217728") \
        .config("spark.hadoop.fs.s3a.fast.upload.buffer", "disk") \
        .config("spark.hadoop.fs.s3a.block.size", "134217728") \
        .config("spark.hadoop.fs.s3a.buffer.dir", "/tmp") \
        .config("spark.hadoop.fs.s3a.retry.limit", "3") \
        .config("spark.hadoop.fs.s3a.retry.interval", "500ms") \
        .config("spark.hadoop.fs.s3a.connection.timeout", "10000") \
        .config("spark.hadoop.fs.s3a.socket.timeout", "10000") \
        .getOrCreate()

def create_namespace_safe(spark, namespace):
    """Create namespace using the safest method."""
    try:
        spark.sql(f"CREATE DATABASE IF NOT EXISTS {namespace}")
        print(f"Namespace {namespace} created successfully.")
        return True
    except Exception as e:
        print(f"Error creating namespace {namespace}: {e}")
        return False

def main():
    # Set environment variables
    os.environ['AWS_REGION'] = 'us-east-1'
    os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
    os.environ['AWS_ACCESS_KEY_ID'] = 'admin'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'password'
    
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("INFO")

    # Load Avro schema
    avro_schema_path = "/opt/bitnami/spark/jobs/producer_schema.avsc"
    try:
        avro_schema_str = load_avro_schema(avro_schema_path)
        print(f"Avro schema loaded successfully from {avro_schema_path}")
    except FileNotFoundError:
        print(f"Schema file not found at {avro_schema_path}. Exiting.")
        return

    # Test connectivity
    try:
        databases = spark.sql("SHOW DATABASES")
        databases.show()
        print("Successfully connected to Hive Metastore")
    except Exception as e:
        print(f"Error connecting to Hive Metastore: {e}")
        return

    # Create namespace
    namespace = ICEBERG_TABLE_NAME.split('.')[0]
    if not create_namespace_safe(spark, namespace):
        print(f"Failed to create namespace {namespace}. Exiting.")
        return

    # Drop and recreate table
    try:
        spark.sql(f"DROP TABLE IF EXISTS {ICEBERG_TABLE_NAME}")
        print(f"Dropped existing table {ICEBERG_TABLE_NAME} if it existed.")
    except Exception as e:
        print(f"Note: Could not drop table {ICEBERG_TABLE_NAME}: {e}")

    # Define Iceberg table schema
    table_schema = """
        proponente_id STRING,
        data_solicitacao LONG,
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
        metadata_evento STRUCT<versao_schema: STRING, origem_dados: STRING, timestamp_geracao_evento: LONG>,
        ingestion_timestamp TIMESTAMP
    """

    # Create Iceberg table
    try:
        spark.sql(f"""
            CREATE TABLE {ICEBERG_TABLE_NAME} ({table_schema})
            USING iceberg
            PARTITIONED BY (months(ingestion_timestamp), tipo_pessoa)
            TBLPROPERTIES (
                'write.format.default'='parquet',
                'write.parquet.compression-codec'='zstd'
            )
        """)
        print(f"Iceberg table {ICEBERG_TABLE_NAME} created successfully.")
    except Exception as e:
        print(f"Error creating Iceberg table {ICEBERG_TABLE_NAME}: {e}")
        return

    # Create checkpoint directory
    checkpoint_dir = f"/tmp/checkpoints/{ICEBERG_TABLE_NAME.replace('.', '_')}"
    os.makedirs(checkpoint_dir, exist_ok=True)
    print(f"Checkpoint directory created: {checkpoint_dir}")

    # Read from Kafka
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # Parse Avro data
    parsed_df = kafka_df.select(
        from_avro(col("value"), avro_schema_str).alias("data")
    ).select("data.*")

    # Transform data to match table schema
    final_df = parsed_df.filter(col("proponente_id").isNotNull()) \
        .withColumn(
            "ingestion_timestamp",
            col("data_solicitacao")  # Copy timestamp for ingestion
        ).withColumn(
            "data_solicitacao",
            (col("data_solicitacao").cast(LongType()) / 1000).cast(LongType())  # Convert to seconds
        ).withColumn(
            "metadata_evento",
            col("metadata_evento").withField(
                "timestamp_geracao_evento",
                (col("metadata_evento.timestamp_geracao_evento").cast(LongType()) / 1000).cast(LongType())
            )
        )

    # Write to Iceberg table with local checkpoint
    query = final_df.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .trigger(processingTime="60 seconds") \
        .option("checkpointLocation", checkpoint_dir) \
        .toTable(ICEBERG_TABLE_NAME)

    print(f"Streaming query started for Iceberg table {ICEBERG_TABLE_NAME}. Waiting for termination...")
    query.awaitTermination()

if __name__ == "__main__":
    main()