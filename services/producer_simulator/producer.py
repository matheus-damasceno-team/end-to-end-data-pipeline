import time
import random
import os
from datetime import datetime, timezone
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
import avro.schema
import avro.io
import io

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')
SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', 'http://schema-registry:8081')

# Load Avro Schema
def load_avro_schema(schema_path):
    with open(schema_path, 'r') as f:
        return f.read()

# Path to your Avro schema file
AVRO_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'producer_schema.avsc')
VALUE_SCHEMA_STR = load_avro_schema(AVRO_SCHEMA_PATH)

def create_producer():
    """Creates and returns a Kafka producer."""
    try:
        producer = Producer({
            'bootstrap.servers': KAFKA_BROKER,
            'retries': 5,
            # 'acks': 'all' # For stronger delivery guarantees, can impact throughput
        })
        print(f"KafkaProducer connected to {KAFKA_BROKER}")
        return producer
    except Exception as e:
        print(f"Error creating Kafka producer: {e}")
        return None

def generate_mock_data(proponente_id_start=1):
    """Generates a single mock data event for a producer."""
    proponente_id = f"PROP_{proponente_id_start + random.randint(0, 10000):05d}"
    current_time = datetime.now(timezone.utc)

    possui_experiencia_atividade = random.choice([True, False])
    data = {
        "proponente_id": proponente_id,
        "data_solicitacao": current_time.isoformat(), # ISO 8601 format timestamp
        "cpf_cnpj": f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
        "nome_razao_social": f"Produtor Rural Exemplo {proponente_id}",
        "tipo_pessoa": random.choice(["FISICA", "JURIDICA"]),
        "renda_bruta_anual_declarada": round(random.uniform(50000, 1000000), 2),
        "valor_solicitado_credito": round(random.uniform(10000, 500000), 2),
        "finalidade_credito": random.choice(["Custeio Safra", "Investimento Maquinario", "Ampliacao Area", "Outros"]),
        "localizacao_propriedade": {
            "latitude": round(random.uniform(-34, 5), 6), # Brazil's lat range approx
            "longitude": round(random.uniform(-74, -34), 6), # Brazil's lon range approx
            "municipio": f"Municipio Exemplo {random.randint(1,100)}",
            "uf": random.choice(["SP", "MG", "PR", "RS", "GO", "MT", "MS", "BA"])
        },
        "area_total_hectares": round(random.uniform(10, 2000), 2),
        "cultura_principal": random.choice(["Soja", "Milho", "Cafe", "Cana-de-açucar", "Algodao", "Fruticultura"]),
        "possui_experiencia_atividade": possui_experiencia_atividade,
        "anos_experiencia": random.randint(0, 40) if possui_experiencia_atividade else 0,
        "fontes_dados_adicionais": { # Simulating potential raw data points for enrichment
            "serasa_score": random.randint(0,1000) if random.choice([True, False]) else None,
            "ibama_autuacoes_ativas": random.choice([True, False, None]),
            "numero_matricula_imovel": f"MAT-{random.randint(1000,99999)}"
        },
        "metadata_evento": {
            "versao_schema": "1.0.2",
            "origem_dados": "simulador_onboarding_digital",
            "timestamp_geracao_evento": current_time.timestamp() # Unix timestamp (float)
        }
    }
    return data

def main():
    producer = create_producer()
    if not producer:
        print("Exiting due to Kafka producer creation failure.")
        return

    print(f"Starting to produce messages to Kafka topic: {KAFKA_TOPIC} at {KAFKA_BROKER}")
    proponente_counter = 1
    try:
        while True:
            mock_data = generate_mock_data(proponente_counter)
            proponente_counter +=1

            try:
                # Parse the schema
                parsed_schema = avro.schema.parse(VALUE_SCHEMA_STR)
                writer = avro.io.DatumWriter(parsed_schema)
                bytes_writer = io.BytesIO()
                encoder = avro.io.BinaryEncoder(bytes_writer)
                writer.write(mock_data, encoder)
                serialized_data = bytes_writer.getvalue()

                # Asynchronously produce a message
                producer.produce(
                    topic=KAFKA_TOPIC,
                    key=str(mock_data["proponente_id"]).encode('utf-8'), # Key needs to be bytes
                    value=serialized_data,
                    callback=delivery_report
                )
                # Poll for events to ensure callbacks are triggered and to manage the queue size
                producer.poll(0) # Non-blocking poll

            except Exception as e:
                print(f"Error producing message: {e}")
                # Potentially implement more robust error handling, e.g., retry, DLQ, or logging service

            # Simulate variable delay between messages
            sleep_time = random.uniform(15, 30) # Seconds
            print(f"Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Producer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred in producer: {e}")
    finally:
        if producer:
            print("Flushing outstanding messages...")
            producer.flush(timeout=10) # Wait for all messages to be sent
            print("Producer closed.")

def delivery_report(err, msg):
    """Callback function for delivery reports."""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()} (Key: {msg.key().decode('utf-8')})")

if __name__ == "__main__":
    # Add a small delay at startup to allow Kafka to be fully ready, especially in Docker Compose
    time.sleep(10)
    main()
