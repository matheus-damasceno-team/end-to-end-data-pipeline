import json
import os
import time
from datetime import datetime, timezone
from kafka import KafkaConsumer
from minio import Minio
from minio.error import S3Error

# Kafka Configuration
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'kafka:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'dados_produtores')
KAFKA_CONSUMER_GROUP = os.getenv('KAFKA_CONSUMER_GROUP', 'minio_ingestion_group')

# MinIO Configuration
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'admin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'password')
MINIO_BUCKET_BRONZE = os.getenv('MINIO_BUCKET_BRONZE', 'bronze') # Target bucket for raw data

def create_minio_client():
    """Creates and returns a MinIO client."""
    try:
        client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False  # Assuming HTTP for local MinIO, set to True for HTTPS
        )
        # Check if connection is working by trying to list buckets (optional)
        # client.list_buckets()
        print(f"MinIO client connected to endpoint: {MINIO_ENDPOINT}")
        return client
    except Exception as e:
        print(f"Error creating MinIO client: {e}")
        return None

def create_kafka_consumer(max_retries=5, retry_delay=10):
    """Creates and returns a Kafka consumer with retry logic."""
    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=KAFKA_BROKER,
                auto_offset_reset='earliest',  # Start reading at the earliest message if no offset found
                enable_auto_commit=True,       # Auto commit offsets
                group_id=KAFKA_CONSUMER_GROUP,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')), # Deserialize JSON messages
                consumer_timeout_ms=10000 # Timeout after 10s of no messages, to allow graceful shutdown
            )
            print(f"KafkaConsumer connected to {KAFKA_BROKER}, subscribed to topic '{KAFKA_TOPIC}' with group '{KAFKA_CONSUMER_GROUP}'")
            return consumer
        except Exception as e:
            print(f"Error creating Kafka consumer (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Could not create Kafka consumer.")
                return None

def upload_to_minio(client, bucket_name, object_name, data_bytes):
    """Uploads data (bytes) to a MinIO bucket."""
    from io import BytesIO
    data_stream = BytesIO(data_bytes)
    data_len = len(data_bytes)
    try:
        # Ensure bucket exists (optional, setup.sh should create it)
        # if not client.bucket_exists(bucket_name):
        #     client.make_bucket(bucket_name)
        #     print(f"Bucket '{bucket_name}' created.")

        client.put_object(
            bucket_name,
            object_name,
            data_stream,
            length=data_len,
            content_type='application/json' # Assuming JSON data
        )
        print(f"Successfully uploaded '{object_name}' to MinIO bucket '{bucket_name}'.")
        return True
    except S3Error as e:
        print(f"MinIO S3Error uploading '{object_name}': {e}")
    except Exception as e:
        print(f"Generic error uploading '{object_name}': {e}")
    return False


def main():
    minio_client = create_minio_client()
    kafka_consumer = create_kafka_consumer()

    if not minio_client or not kafka_consumer:
        print("Exiting due to client creation failure (MinIO or Kafka).")
        return

    print(f"Starting to consume messages from Kafka topic: {KAFKA_TOPIC}")
    try:
        for message in kafka_consumer:
            # message.key, message.value, message.topic, message.partition, message.offset
            print(f"Received message: Offset={message.offset}, Key={message.key.decode() if message.key else 'None'}")

            raw_data = message.value # Already deserialized by KafkaConsumer

            # Generate a unique object name for MinIO
            # Example: YYYY/MM/DD/HH/proponente_id_timestamp.json
            # Using proponente_id from the message if available, and current timestamp for uniqueness
            proponente_id = raw_data.get("proponente_id", "unknown_proponente")
            # It's good practice to ensure proponente_id is filename-safe
            safe_proponente_id = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in str(proponente_id))

            now = datetime.now(timezone.utc)
            object_path_prefix = f"{now.strftime('%Y/%m/%d/%H')}"
            object_name = f"{object_path_prefix}/{safe_proponente_id}_{now.strftime('%Y%m%d%H%M%S%f')}.json"

            # Convert data back to JSON string bytes for upload
            data_bytes = json.dumps(raw_data).encode('utf-8')

            if not upload_to_minio(minio_client, MINIO_BUCKET_BRONZE, object_name, data_bytes):
                print(f"Failed to upload message offset {message.offset} to MinIO. Data: {raw_data}")
                # Error handling: What to do if upload fails?
                # - Retry?
                # - Send to a Dead Letter Queue (DLQ) in Kafka?
                # - Log and skip? (current behavior implicitly)
                # For this example, we log and continue. In production, a robust DLQ strategy is advised.

            # Manual offset commit if enable_auto_commit=False
            # kafka_consumer.commit()

    except KeyboardInterrupt:
        print("Consumer stopped by user.")
    except Exception as e:
        print(f"An unexpected error occurred in consumer: {e}")
    finally:
        if kafka_consumer:
            print("Closing Kafka consumer...")
            kafka_consumer.close()
            print("Consumer closed.")
        # MinIO client does not have a close() method in the same way.

if __name__ == "__main__":
    # Add a small delay at startup for dependencies like Kafka and MinIO
    time.sleep(15) # Increased delay for consumer
    main()
