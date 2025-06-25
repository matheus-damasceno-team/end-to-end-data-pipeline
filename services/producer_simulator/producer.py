import json
import time
import random
from datetime import datetime, timezone
from kafka import KafkaProducer

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')

# MinIO Configuration (not directly used by producer, but for context)
# MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio:9000')
# MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'admin')
# MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'password')
# MINIO_BUCKET_BRONZE = os.getenv('MINIO_BUCKET_BRONZE', 'bronze')

def create_producer():
    """Creates and returns a Kafka producer."""
    try:
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=5, # Retry sending if producing fails
            # acks='all' # For stronger delivery guarantees, can impact throughput
        )
        print(f"KafkaProducer connected to {KAFKA_BROKER}")
        return producer
    except Exception as e:
        print(f"Error creating Kafka producer: {e}")
        # Consider a retry mechanism or exiting if critical
        return None

def generate_mock_data(proponente_id_start=1):
    """Generates a single mock data event for a producer."""
    proponente_id = f"PROP_{proponente_id_start + random.randint(0, 10000):05d}"
    current_time = datetime.now(timezone.utc)

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
        "possui_experiencia_atividade": random.choice([True, False]),
        "anos_experiencia": random.randint(0, 40) if data["possui_experiencia_atividade"] else 0,
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
                future = producer.send(KAFKA_TOPIC, value=mock_data, key=mock_data["proponente_id"].encode('utf-8'))
                # Block for 'synchronous' sends, or handle asynchronously
                record_metadata = future.get(timeout=10) # Wait for send confirmation
                print(f"Sent message: ID {mock_data['proponente_id']} to topic {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}")
            except Exception as e:
                print(f"Error sending message: {e}")
                # Potentially implement more robust error handling, e.g., retry, DLQ, or logging service

            # Simulate variable delay between messages
            sleep_time = random.uniform(0.5, 3.0) # Seconds
            print(f"Sleeping for {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Producer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred in producer: {e}")
    finally:
        if producer:
            print("Flushing and closing Kafka producer...")
            producer.flush(timeout=10) # Wait for all messages to be sent
            producer.close(timeout=10)
            print("Producer closed.")

if __name__ == "__main__":
    # Add a small delay at startup to allow Kafka to be fully ready, especially in Docker Compose
    time.sleep(10)
    main()
