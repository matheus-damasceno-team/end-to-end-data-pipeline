FROM openjdk:8-jre-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV HADOOP_VERSION=3.3.6
ENV HIVE_VERSION=3.1.3
ENV HADOOP_HOME=/opt/hadoop
ENV HIVE_HOME=/opt/hive
ENV PATH=$PATH:$HADOOP_HOME/bin:$HIVE_HOME/bin

# Download and install Hadoop
RUN curl -L https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}.tar.gz | tar -xz -C /opt/ \
    && mv /opt/hadoop-${HADOOP_VERSION} ${HADOOP_HOME}

# Download and install Hive
RUN curl -L https://archive.apache.org/dist/hive/hive-${HIVE_VERSION}/apache-hive-${HIVE_VERSION}-bin.tar.gz | tar -xz -C /opt/ \
    && mv /opt/apache-hive-${HIVE_VERSION}-bin ${HIVE_HOME}

# Download MySQL/MariaDB JDBC connector
RUN curl -L https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.33/mysql-connector-java-8.0.33.jar \
    -o ${HIVE_HOME}/lib/mysql-connector-java.jar

# Download AWS SDK for S3 support
RUN curl -L https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar \
    -o ${HIVE_HOME}/lib/aws-java-sdk-bundle.jar \
    && curl -L https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/${HADOOP_VERSION}/hadoop-aws-${HADOOP_VERSION}.jar \
    -o ${HIVE_HOME}/lib/hadoop-aws.jar

# Create necessary directories
RUN mkdir -p /opt/hive/logs /opt/hive/conf

# Copy configuration files
COPY conf/hive-site.xml ${HIVE_HOME}/conf/
COPY scripts/entrypoint.sh /opt/hive/scripts/

# Make scripts executable
RUN chmod +x /opt/hive/scripts/entrypoint.sh

# Expose metastore port
EXPOSE 9083

# Set working directory
WORKDIR ${HIVE_HOME}

ENTRYPOINT ["/opt/hive/scripts/entrypoint.sh"]