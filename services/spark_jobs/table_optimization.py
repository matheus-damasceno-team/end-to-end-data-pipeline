# services/spark_jobs/table_optimization.py

import logging
from pyspark.sql import SparkSession
from datetime import datetime, timedelta

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session():
    """Cria sessão Spark otimizada para operações de manutenção"""
    
    spark = SparkSession.builder \
        .appName("TableOptimization") \
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
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider") \
        .config("spark.hadoop.fs.s3a.region", "us-east-1") \
        .config("spark.hadoop.fs.s3a.bucket.all.region.lookup.disable", "true") \
        .config("spark.hadoop.fs.s3a.signer.override", "S3SignerType") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("INFO")
    return spark

def get_table_list(spark):
    """Obtém lista de todas as tabelas Iceberg"""
    
    try:
        # Lista tabelas do bronze
        bronze_tables = spark.sql("SHOW TABLES IN bronze").collect()
        
        # Lista tabelas do silver
        silver_tables = spark.sql("SHOW TABLES IN silver").collect()
        
        # Lista tabelas do gold
        gold_tables = spark.sql("SHOW TABLES IN gold").collect()
        
        all_tables = []
        
        for table in bronze_tables:
            all_tables.append(f"bronze.{table.tableName}")
        
        for table in silver_tables:
            all_tables.append(f"silver.{table.tableName}")
            
        for table in gold_tables:
            all_tables.append(f"gold.{table.tableName}")
        
        logger.info(f"Encontradas {len(all_tables)} tabelas para otimização")
        return all_tables
        
    except Exception as e:
        logger.error(f"Erro ao obter lista de tabelas: {e}")
        return []

def rewrite_data_files(spark, table_name):
    """Reescreve arquivos de dados para otimizar o layout"""
    
    try:
        logger.info(f"Reescrevendo arquivos de dados para {table_name}")
        
        # Reescreve arquivos pequenos em arquivos maiores
        spark.sql(f"CALL spark_catalog.system.rewrite_data_files('{table_name}')")
        
        logger.info(f"Reescrita de dados concluída para {table_name}")
        
    except Exception as e:
        logger.error(f"Erro ao reescrever dados de {table_name}: {e}")
        raise

def rewrite_manifests(spark, table_name):
    """Reescreve manifestos para otimizar metadados"""
    
    try:
        logger.info(f"Reescrevendo manifestos para {table_name}")
        
        # Reescreve manifestos
        spark.sql(f"CALL spark_catalog.system.rewrite_manifests('{table_name}')")
        
        logger.info(f"Reescrita de manifestos concluída para {table_name}")
        
    except Exception as e:
        logger.error(f"Erro ao reescrever manifestos de {table_name}: {e}")
        raise

def expire_snapshots(spark, table_name, retention_days=7):
    """Remove snapshots antigos"""
    
    try:
        logger.info(f"Removendo snapshots antigos de {table_name}")
        
        # Data de corte para expiração
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_timestamp = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
        
        # Remove snapshots antigos
        spark.sql(f"""
            CALL spark_catalog.system.expire_snapshots(
                '{table_name}',
                TIMESTAMP '{cutoff_timestamp}'
            )
        """)
        
        logger.info(f"Snapshots antigos removidos de {table_name}")
        
    except Exception as e:
        logger.error(f"Erro ao remover snapshots de {table_name}: {e}")
        raise

def remove_orphan_files(spark, table_name):
    """Remove arquivos órfãos"""
    
    try:
        logger.info(f"Removendo arquivos órfãos de {table_name}")
        
        # Remove arquivos órfãos (mais antigos que 3 dias)
        cutoff_date = datetime.now() - timedelta(days=3)
        cutoff_timestamp = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
        
        spark.sql(f"""
            CALL spark_catalog.system.remove_orphan_files(
                table => '{table_name}',
                older_than => TIMESTAMP '{cutoff_timestamp}'
            )
        """)
        
        logger.info(f"Arquivos órfãos removidos de {table_name}")
        
    except Exception as e:
        logger.error(f"Erro ao remover arquivos órfãos de {table_name}: {e}")
        raise

def get_table_statistics(spark, table_name):
    """Obtém estatísticas da tabela"""
    
    try:
        # Estatísticas básicas
        stats = spark.sql(f"DESCRIBE EXTENDED {table_name}").collect()
        
        # Informações de snapshots
        snapshots = spark.sql(f"SELECT * FROM {table_name}.snapshots").collect()
        
        # Informações de arquivos
        files = spark.sql(f"SELECT * FROM {table_name}.files").collect()
        
        logger.info(f"Estatísticas de {table_name}:")
        logger.info(f"  - Snapshots: {len(snapshots)}")
        logger.info(f"  - Arquivos de dados: {len(files)}")
        
        # Calcula tamanho total dos arquivos
        total_size = sum([f.file_size_in_bytes for f in files]) if files else 0
        logger.info(f"  - Tamanho total: {total_size / (1024*1024):.2f} MB")
        
        return {
            'table_name': table_name,
            'snapshots_count': len(snapshots),
            'files_count': len(files),
            'total_size_mb': total_size / (1024*1024)
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de {table_name}: {e}")
        return None

def optimize_table_partitioning(spark, table_name):
    """Otimiza particionamento da tabela se necessário"""
    
    try:
        logger.info(f"Verificando particionamento de {table_name}")
        
        # Obtém informações de particionamento
        partitions = spark.sql(f"SHOW PARTITIONS {table_name}").collect()
        
        if len(partitions) > 1000:
            logger.warning(f"Tabela {table_name} tem muitas partições ({len(partitions)})")
            logger.info("Considere reorganizar o particionamento")
        
        # Para tabelas com dados por data, verifica se há partições vazias ou muito pequenas
        if 'data_' in table_name.lower():
            small_partitions = spark.sql(f"""
                SELECT partition, count(*) as record_count
                FROM {table_name}
                GROUP BY partition
                HAVING count(*) < 1000
                ORDER BY record_count
            """).collect()
            
            if small_partitions:
                logger.info(f"Encontradas {len(small_partitions)} partições pequenas em {table_name}")
        
    except Exception as e:
        logger.error(f"Erro ao verificar particionamento de {table_name}: {e}")

def compact_table(spark, table_name):
    """Executa compactação completa da tabela"""
    
    try:
        logger.info(f"Iniciando compactação completa de {table_name}")
        
        # 1. Reescreve arquivos de dados
        rewrite_data_files(spark, table_name)
        
        # 2. Reescreve manifestos
        rewrite_manifests(spark, table_name)
        
        # 3. Remove snapshots antigos
        expire_snapshots(spark, table_name, retention_days=7)
        
        # 4. Remove arquivos órfãos
        remove_orphan_files(spark, table_name)
        
        logger.info(f"Compactação completa de {table_name} finalizada")
        
    except Exception as e:
        logger.error(f"Erro na compactação de {table_name}: {e}")
        raise

def analyze_table_health(spark, table_name):
    """Analisa a 'saúde' da tabela e sugere otimizações"""
    
    try:
        logger.info(f"Analisando saúde da tabela {table_name}")
        
        # Obtém estatísticas
        stats = get_table_statistics(spark, table_name)
        
        if not stats:
            return
        
        health_issues = []
        
        # Verifica se há muitos arquivos pequenos
        if stats['files_count'] > 1000:
            health_issues.append(f"Muitos arquivos ({stats['files_count']}) - considere compactação")
        
        # Verifica tamanho médio dos arquivos
        if stats['files_count'] > 0:
            avg_file_size = stats['total_size_mb'] / stats['files_count']
            if avg_file_size < 10:  # Arquivos menores que 10MB
                health_issues.append(f"Arquivos muito pequenos (média: {avg_file_size:.2f}MB)")
        
        # Verifica número de snapshots
        if stats['snapshots_count'] > 20:
            health_issues.append(f"Muitos snapshots ({stats['snapshots_count']}) - considere limpeza")
        
        if health_issues:
            logger.warning(f"Problemas identificados em {table_name}:")
            for issue in health_issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info(f"Tabela {table_name} está saudável")
        
        return health_issues
        
    except Exception as e:
        logger.error(f"Erro na análise de saúde de {table_name}: {e}")
        return []

def main():
    """Função principal do script de otimização"""
    
    logger.info("=== Iniciando Otimização de Tabelas Iceberg ===")
    
    spark = None
    optimization_report = {
        'start_time': datetime.now().isoformat(),
        'tables_processed': 0,
        'tables_optimized': 0,
        'errors': [],
        'summary': {}
    }
    
    try:
        # Cria sessão Spark
        spark = create_spark_session()
        
        # Obtém lista de tabelas
        tables = get_table_list(spark)
        
        if not tables:
            logger.warning("Nenhuma tabela encontrada para otimização")
            return
        
        optimization_report['tables_found'] = len(tables)
        
        # Processa cada tabela
        for table_name in tables:
            try:
                logger.info(f"Processando tabela: {table_name}")
                optimization_report['tables_processed'] += 1
                
                # Analisa saúde da tabela
                health_issues = analyze_table_health(spark, table_name)
                
                # Decide se precisa otimizar
                needs_optimization = len(health_issues) > 0
                
                if needs_optimization:
                    logger.info(f"Tabela {table_name} precisa de otimização")
                    
                    # Executa compactação
                    compact_table(spark, table_name)
                    
                    # Verifica particionamento
                    optimize_table_partitioning(spark, table_name)
                    
                    optimization_report['tables_optimized'] += 1
                    optimization_report['summary'][table_name] = {
                        'optimized': True,
                        'issues_found': health_issues
                    }
                else:
                    logger.info(f"Tabela {table_name} não precisa de otimização")
                    optimization_report['summary'][table_name] = {
                        'optimized': False,
                        'issues_found': []
                    }
                
            except Exception as e:
                error_msg = f"Erro ao processar {table_name}: {e}"
                logger.error(error_msg)
                optimization_report['errors'].append(error_msg)
                continue
        
        # Relatório final
        optimization_report['end_time'] = datetime.now().isoformat()
        optimization_report['success'] = True
        
        logger.info("=== Relatório de Otimização ===")
        logger.info(f"Tabelas encontradas: {optimization_report['tables_found']}")
        logger.info(f"Tabelas processadas: {optimization_report['tables_processed']}")
        logger.info(f"Tabelas otimizadas: {optimization_report['tables_optimized']}")
        logger.info(f"Erros: {len(optimization_report['errors'])}")
        
        if optimization_report['errors']:
            logger.warning("Erros durante otimização:")
            for error in optimization_report['errors']:
                logger.warning(f"  - {error}")
        
        logger.info("=== Otimização Concluída ===")
        
    except Exception as e:
        optimization_report['success'] = False
        optimization_report['end_time'] = datetime.now().isoformat()
        optimization_report['errors'].append(f"Erro geral: {e}")
        logger.error(f"Erro durante otimização: {e}")
        raise
        
    finally:
        if spark:
            spark.stop()
        
        # Salva relatório (opcional)
        try:
            import json
            with open('/tmp/optimization_report.json', 'w') as f:
                json.dump(optimization_report, f, indent=2)
            logger.info("Relatório salvo em /tmp/optimization_report.json")
        except:
            pass

if __name__ == "__main__":
    main()