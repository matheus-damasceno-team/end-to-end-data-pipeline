import time
import random
import os
import json
from datetime import datetime, timezone
from confluent_kafka import Producer
import avro.schema
import avro.io
import io

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')

# Load Avro schema from the separate .avsc file
def load_avro_schema(schema_path="producer_schema.avsc"):
    with open(schema_path, 'r') as f:
        schema_dict = json.load(f)
    return avro.schema.parse(json.dumps(schema_dict))

# Avro schema is now loaded from the file
AVRO_SCHEMA = load_avro_schema()

def create_producer():
    """Creates and returns a standard Kafka producer."""
    try:
        producer_config = {
            'bootstrap.servers': KAFKA_BROKER,
            'client.id': 'agronegocio-producer'
        }
        producer = Producer(producer_config)
        print(f"Kafka Producer connected to {KAFKA_BROKER}")
        return producer
    except Exception as e:
        print(f"Error creating Kafka producer: {e}")
        return None

def serialize_avro_raw(data):
    """Serializes a Python dictionary to raw Avro binary format (without file header)."""
    writer = avro.io.DatumWriter(AVRO_SCHEMA)
    bytes_writer = io.BytesIO()
    encoder = avro.io.BinaryEncoder(bytes_writer)
    writer.write(data, encoder)
    return bytes_writer.getvalue()

def generate_mock_data(proponente_id_start=1):
    """Generates a single mock data event for a producer."""
    proponente_id = f"PROP_{proponente_id_start + random.randint(0, 10000):05d}"
    current_time = datetime.now(timezone.utc)
    current_timestamp_millis = int(current_time.timestamp() * 1000)

    if random.choice([True, False]):
        cpf_cnpj = f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}"
        tipo_pessoa = "FISICA"
    else:
        cnpj_numbers = [random.randint(0, 9) for _ in range(14)]
        cpf_cnpj = f"{cnpj_numbers[0]}{cnpj_numbers[1]}.{cnpj_numbers[2]}{cnpj_numbers[3]}{cnpj_numbers[4]}.{cnpj_numbers[5]}{cnpj_numbers[6]}{cnpj_numbers[7]}/{cnpj_numbers[8]}{cnpj_numbers[9]}{cnpj_numbers[10]}{cnpj_numbers[11]}-{cnpj_numbers[12]}{cnpj_numbers[13]}"
        tipo_pessoa = "JURIDICA"

    possui_experiencia = random.choice([True, False])
    
    return {
        "proponente_id": proponente_id,
        "data_solicitacao": current_timestamp_millis,
        "cpf_cnpj": cpf_cnpj,
        "nome_razao_social": f"Produtor Rural Exemplo {proponente_id}",
        "tipo_pessoa": tipo_pessoa,
        "renda_bruta_anual_declarada": round(random.uniform(50000.0, 1000000.0), 2),
        "valor_solicitado_credito": round(random.uniform(10000.0, 500000.0), 2),
        "finalidade_credito": random.choice(["CUSTEIO_SAFRA", "INVESTIMENTO_MAQUINARIO", "AMPLIACAO_AREA", "OUTROS"]),
        "localizacao_propriedade": {
            "latitude": round(random.uniform(-34.0, 5.0), 6),
            "longitude": round(random.uniform(-74.0, -34.0), 6),
            "municipio": f"Municipio Exemplo {random.randint(1, 100)}",
            "uf": random.choice(["SP", "MG", "PR", "RS", "GO", "MT", "MS", "BA", "SC", "RJ", "ES", "TO", "MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "DF", "AC", "AP", "AM", "PA", "RO", "RR"])
        },
        "area_total_hectares": round(random.uniform(10.0, 2000.0), 2),
        "cultura_principal": random.choice(["SOJA", "MILHO", "CAFE", "CANA_DE_ACUCAR", "ALGODAO", "FRUTICULTURA", "TRIGO", "ARROZ", "FEIJAO", "EUCALIPTO"]),
        "possui_experiencia_atividade": possui_experiencia,
        "anos_experiencia": random.randint(1, 40) if possui_experiencia else 0,
        "fontes_dados_adicionais": {
            "serasa_score": random.randint(300, 900) if random.choice([True, False]) else None,
            "ibama_autuacoes_ativas": random.choice([True, False, None]),
            "numero_matricula_imovel": f"MAT-{random.randint(100000, 999999)}"
        },
        "metadata_evento": {
            "versao_schema": "1.0.0",
            "origem_dados": "simulador_onboarding_digital",
            "timestamp_geracao_evento": current_timestamp_millis
        }
    }

def main():
    producer = create_producer()
    if not producer:
        print("Exiting due to producer creation failure.")
        return

    print(f"Starting to produce RAW Avro messages (without file header) to Kafka topic: {KAFKA_TOPIC} at {KAFKA_BROKER}")
    proponente_counter = 1
    
    try:
        while True:
            mock_data = generate_mock_data(proponente_counter)
            proponente_counter += 1
            
            # Use raw Avro serialization (without file header)
            avro_payload = serialize_avro_raw(mock_data)

            try:
                producer.produce(
                    topic=KAFKA_TOPIC,
                    value=avro_payload,
                    key=mock_data["proponente_id"].encode('utf-8')
                )
                producer.poll(0) # Trigger delivery report callbacks
                
                print(f"Sent RAW Avro message: ID {mock_data['proponente_id']} to topic {KAFKA_TOPIC} (size: {len(avro_payload)} bytes)")
                
            except BufferError:
                print(f"Local producer queue is full ({len(producer)} messages awaiting delivery): try again")
                producer.flush()
            except Exception as e:
                print(f"Error sending Avro message: {e}")

            sleep_time = random.uniform(2.0, 8.0)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("Producer stopped by user.")
    finally:
        if producer:
            print("Flushing and closing producer...")
            producer.flush()

if __name__ == "__main__":
    time.sleep(15)
    main()