FROM trinodb/trino:450

# Copy configuration files
COPY config.properties /etc/trino/config.properties
COPY node.properties /etc/trino/node.properties
COPY jvm.config /etc/trino/jvm.config

# Copy catalog configuration
COPY catalog/ /etc/trino/catalog/

# Create data directory
RUN mkdir -p /data/trino && chown trino:trino /data/trino

USER trino

EXPOSE 8080