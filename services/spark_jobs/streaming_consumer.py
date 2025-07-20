from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, current_timestamp, expr
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, BooleanType, IntegerType, TimestampType
import os

# Configurações
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')
BRONZE_ICEBERG_TABLE = "bronze.dados_produtores_raw"
CHECKPOINT_LOCATION = "s3a://bronze/checkpoints/streaming_consumer"

def create_spark_session():
    """Cria e retorna uma sessão Spark configurada para Iceberg."""
    
    spark = SparkSession.builder \
        .appName("KafkaAvroToBronzeIceberg") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hive") \
        .config("spark.sql.catalog.spark_catalog.uri", "thrift://metastore:9083") \
        .config("spark.sql.catalog.spark_catalog.warehouse", "s3a://warehouse/") \
        .config("spark.sql.catalog.spark_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO") \
        .config("spark.sql.catalog.spark_catalog.s3.endpoint", "http://minio:9000") \
        .config("spark.sql.catalog.spark_catalog.s3.path-style-access", "true") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .enableHiveSupport() \
        .getOrCreate()

    # Set log level to reduce noise
    spark.sparkContext.setLogLevel("WARN")
    
    print("Spark session created successfully with Iceberg support")
    return spark

def define_avro_schema():
    """Define o schema Spark equivalente ao schema Avro."""
    
    # Schema que corresponde aos dados Avro do producer
    schema = StructType([
        StructField("proponente_id", StringType(), True),
        StructField("data_solicitacao", TimestampType(), True),
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
            StructField("timestamp_geracao_evento", TimestampType(), True)
        ]), True)
    ])
    
    return schema

def create_bronze_table_if_not_exists(spark):
    """Cria a tabela Iceberg na camada bronze se não existir."""
    
    try:
        # Verificar se o database bronze existe
        spark.sql("CREATE DATABASE IF NOT EXISTS bronze")
        
        # DDL para criar a tabela Iceberg com particionamento otimizado
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {BRONZE_ICEBERG_TABLE} (
            proponente_id STRING,
            data_solicitacao TIMESTAMP,
            cpf_cnpj STRING,
            nome_razao_social STRING,
            tipo_pessoa STRING,
            renda_bruta_anual_declarada DOUBLE,
            valor_solicitado_credito DOUBLE,
            finalidade_credito STRING,
            localizacao_latitude DOUBLE,
            localizacao_longitude DOUBLE,
            localizacao_municipio STRING,
            localizacao_uf STRING,
            area_total_hectares DOUBLE,
            cultura_principal STRING,
            possui_experiencia_atividade BOOLEAN,
            anos_experiencia INT,
            serasa_score INT,
            ibama_autuacoes_ativas BOOLEAN,
            numero_matricula_imovel STRING,
            versao_schema STRING,
            origem_dados STRING,
            timestamp_geracao_evento TIMESTAMP,
            data_ingestao TIMESTAMP,
            ano_particao INT,
            mes_particao INT,
            dia_particao INT
        ) USING ICEBERG
        PARTITIONED BY (ano_particao, mes_particao, dia_particao)
        TBLPROPERTIES (
            'write.format.default' = 'parquet',
            'write.parquet.compression-codec' = 'snappy',
            'write.merge.mode' = 'merge-on-read',
            'write.update.mode' = 'merge-on-read',
            'write.delete.mode' = 'merge-on-read',
            'format-version' = '2'
        )
        """
        
        spark.sql(create_table_sql)
        print(f"Tabela Iceberg {BRONZE_ICEBERG_TABLE} criada/verificada com sucesso")
        
    except Exception as e:
        print(f"Erro ao criar tabela Iceberg: {e}")
        raise

def process_kafka_stream(spark, schema):
    """Processa o stream do Kafka e escreve na tabela Iceberg."""
    
    # Ler stream do Kafka com deserialização Avro
    kafka_df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()

    print("Kafka stream reader configured")

    # Para dados Avro, precisamos usar um deserializador específico
    # Por simplicidade, vamos assumir que os dados chegam como JSON após conversão
    # Em produção, usaria confluent-kafka-python ou spark-avro
    
    # Processar os dados do Kafka
    processed_df = kafka_df.select(
        col("key").cast("string").alias("kafka_key"),
        col("value").cast("string").alias("kafka_value"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp")
    )

    # Parse do JSON (assumindo conversão de Avro para JSON)
    # Em ambiente real, usaria deserializador Avro apropriado
    parsed_df = processed_df.select(
        "*",
        from_json(col("kafka_value"), schema).alias("data")
    ).select(
        col("kafka_key"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("kafka_timestamp"),
        col("data.*")
    )

    # Transformar e enriquecer os dados para a camada bronze
    bronze_df = parsed_df.select(
        col("proponente_id"),
        col("data_solicitacao"),
        col("cpf_cnpj"),
        col("nome_razao_social"),
        col("tipo_pessoa"),
        col("renda_bruta_anual_declarada"),
        col("valor_solicitado_credito"),
        col("finalidade_credito"),
        col("localizacao_propriedade.latitude").alias("localizacao_latitude"),
        col("localizacao_propriedade.longitude").alias("localizacao_longitude"),
        col("localizacao_propriedade.municipio").alias("localizacao_municipio"),
        col("localizacao_propriedade.uf").alias("localizacao_uf"),
        col("area_total_hectares"),
        col("cultura_principal"),
        col("possui_experiencia_atividade"),
        col("anos_experiencia"),
        col("fontes_dados_adicionais.serasa_score").alias("serasa_score"),
        col("fontes_dados_adicionais.ibama_autuacoes_ativas").alias("ibama_autuacoes_ativas"),
        col("fontes_dados_adicionais.numero_matricula_imovel").alias("numero_matricula_imovel"),
        col("metadata_evento.versao_schema").alias("versao_schema"),
        col("metadata_evento.origem_dados").alias("origem_dados"),
        col("metadata_evento.timestamp_geracao_evento").alias("timestamp_geracao_evento"),
        current_timestamp().alias("data_ingestao"),
        # Colunas de particionamento baseadas na data de solicitação
        expr("year(data_solicitacao)").alias("ano_particao"),
        expr("month(data_solicitacao)").alias("mes_particao"),
        expr("dayofmonth(data_solicitacao)").alias("dia_particao")
    )

    print("Data transformation configured")

    return bronze_df

def write_to_iceberg(df, table_name, checkpoint_location):
    """Escreve o dataframe para a tabela Iceberg usando structured streaming."""
    
    print(f"Starting write to Iceberg table: {table_name}")
    
    query = df.writeStream \
        .format("iceberg") \
        .outputMode("append") \
        .option("checkpointLocation", checkpoint_location) \
        .option("fanout-enabled", "true") \
        .option("merge-schema", "true") \
        .trigger(processingTime="30 seconds") \
        .toTable(table_name)
    
    return query

def main():
    print("Iniciando PySpark Streaming Consumer para Iceberg...")
    
    # Criar sessão Spark
    spark = create_spark_session()
    
    try:
        # Definir schema dos dados
        schema = define_avro_schema()
        
        # Criar tabela Iceberg se não existir
        create_bronze_table_if_not_exists(spark)
        
        # Processar stream do Kafka
        bronze_df = process_kafka_stream(spark, schema)
        
        # Escrever para Iceberg
        streaming_query = write_to_iceberg(
            bronze_df, 
            BRONZE_ICEBERG_TABLE, 
            CHECKPOINT_LOCATION
        )
        
        print("Streaming query iniciada. Aguardando dados...")
        print(f"Monitorando tópico: {KAFKA_TOPIC}")
        print(f"Escrevendo para: {BRONZE_ICEBERG_TABLE}")
        
        # Aguardar termino
        streaming_query.awaitTermination()
        
    except Exception as e:
        print(f"Erro no streaming consumer: {e}")
        raise
    finally:
        print("Encerrando Spark session...")
        spark.stop()

if __name__ == "__main__":
    main()