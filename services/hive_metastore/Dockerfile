# Usa a imagem base do Hive 3.1.3
FROM apache/hive:3.1.3

USER root

# Instala ferramentas necessárias
RUN apt-get update && \
    apt-get install -y wget netcat-openbsd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Baixa o driver JDBC e os JARs do S3/AWS
RUN wget -q https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.0.33/mysql-connector-j-8.0.33.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.1.2/hadoop-aws-3.1.2.jar && \
    wget -q https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.11.271/aws-java-sdk-bundle-1.11.271.jar && \
    \
    # --- INÍCIO: Correção Definitiva ---
    # Copia os JARs para AMBAS as pastas de libs do HIVE e do HADOOP
    # para garantir que tanto o serviço do Metastore quanto os comandos do Hadoop os encontrem.
    cp mysql-connector-j-8.0.33.jar /opt/hive/lib/ && \
    cp hadoop-aws-3.1.2.jar /opt/hive/lib/ && \
    cp aws-java-sdk-bundle-1.11.271.jar /opt/hive/lib/ && \
    \
    cp mysql-connector-j-8.0.33.jar /opt/hadoop/share/hadoop/common/lib/ && \
    cp hadoop-aws-3.1.2.jar /opt/hadoop/share/hadoop/common/lib/ && \
    cp aws-java-sdk-bundle-1.11.271.jar /opt/hadoop/share/hadoop/common/lib/ && \
    # --- FIM: Correção Definitiva ---
    \
    # Limpa os arquivos baixados do diretório raiz
    rm mysql-connector-j-8.0.33.jar hadoop-aws-3.1.2.jar aws-java-sdk-bundle-1.11.271.jar && \
    \
    # Ajusta permissões em ambas as pastas
    chmod 644 /opt/hive/lib/*.jar && \
    chmod 644 /opt/hadoop/share/hadoop/common/lib/*.jar

# Volta para o usuário hive
USER hive

# O entrypoint da imagem base cuida da configuração
ENTRYPOINT ["/entrypoint.sh"]