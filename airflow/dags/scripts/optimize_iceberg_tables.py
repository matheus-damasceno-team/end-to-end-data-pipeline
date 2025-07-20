#!/usr/bin/env python3
"""
Script para otimizar tabelas Iceberg na camada Silver
Executado pelo Airflow após o dbt run
"""

from pyspark.sql import SparkSession
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Cria sessão Spark com configurações para Iceberg"""
    spark = SparkSession.builder \
        .appName("OptimizeSilverTables") \
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hive") \
        .config("spark.sql.catalog.spark_catalog.uri", "thrift://metastore:9083") \
        .config("spark.sql.catalog.spark_catalog.warehouse", "s3a://warehouse") \
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
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    return spark

def optimize_table(spark, table_name):
    """Otimiza uma tabela Iceberg específica"""
    try:
        logger.info(f"Iniciando otimização da tabela: {table_name}")
        
        # Reescrever arquivos de dados para otimizar o layout
        spark.sql(f"CALL spark_catalog.system.rewrite_data_files('{table_name}')")
        logger.info(f"Arquivos de dados reescritos para: {table_name}")
        
        # Reescrever manifestos
        spark.sql(f"CALL spark_catalog.system.rewrite_manifests('{table_name}')")
        logger.info(f"Manifestos reescritos para: {table_name}")
        
        # Obter estatísticas da tabela
        stats = spark.sql(f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT proponente_id) as unique_proponentes
            FROM {table_name}
        """).collect()[0]
        
        logger.info(f"Estatísticas de {table_name}:")
        logger.info(f"  - Total de registros: {stats['total_records']}")
        logger.info(f"  - Proponentes únicos: {stats['unique_proponentes']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao otimizar tabela {table_name}: {str(e)}")
        return False

def main():
    """Função principal"""
    logger.info("=== Iniciando otimização das tabelas Silver ===")
    start_time = datetime.now()
    
    spark = create_spark_session()
    
    # Lista de tabelas Silver para otimizar
    silver_tables = [
        "silver.silver_dados_produtores_agro"
    ]
    
    success_count = 0
    
    for table in silver_tables:
        if optimize_table(spark, table):
            success_count += 1
    
    # Relatório final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    logger.info("=== Otimização concluída ===")
    logger.info(f"Tempo total: {duration:.2f} segundos")
    logger.info(f"Tabelas otimizadas: {success_count}/{len(silver_tables)}")
    
    spark.stop()

if __name__ == "__main__":
    main()