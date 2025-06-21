#!/usr/bin/env python3
"""
Agricultural Data Producer Simulator
PATH: services/producer_simulator/producer.py

Simulates real-time agricultural sensor data and sends to Kafka.
"""

import json
import time
import os
import random
from datetime import datetime, timezone
from kafka import KafkaProducer
from faker import Faker

# Initialize Faker for generating realistic data
fake = Faker()

class AgricultureDataProducer:
    def __init__(self):
        self.bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        self.topic = os.getenv('KAFKA_TOPIC', 'raw_land_data')
        self.delay = int(os.getenv('SIMULATION_DELAY_SECONDS', '5'))
        
        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=[self.bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        
        # Sample farm locations (coordinates around São Paulo, Brazil)
        self.farm_locations = [
            {"farm_id": "FARM001", "lat": -23.5505, "lon": -46.6333, "region": "São Paulo"},
            {"farm_id": "FARM002", "lat": -23.6821, "lon": -46.8755, "region": "Cotia"},
            {"farm_id": "FARM003", "lat": -23.4205, "lon": -46.7011, "region": "Guarulhos"},
            {"farm_id": "FARM004", "lat": -23.6458, "lon": -46.5214, "region": "São Bernardo"},
            {"farm_id": "FARM005", "lat": -23.5236, "lon": -46.8131, "region": "Osasco"},
        ]
        
        print(f"🌱 Producer inicializado para tópico '{self.topic}' no servidor {self.bootstrap_servers}")
        print(f"⏱️  Enviando dados a cada {self.delay} segundos")

    def generate_sensor_data(self, farm):
        """Generate realistic agricultural sensor data"""
        
        # Simulate different crop types
        crop_types = ["soja", "milho", "cana-de-açúcar", "café", "algodão"]
        
        # Generate realistic sensor readings with some seasonal variation
        base_temp = 25  # Base temperature for São Paulo region
        temp_variation = random.uniform(-5, 10)
        
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "farm_id": farm["farm_id"],
            "location": {
                "latitude": farm["lat"] + random.uniform(-0.01, 0.01),  # Small GPS variation
                "longitude": farm["lon"] + random.uniform(-0.01, 0.01),
                "region": farm["region"]
            },
            "crop_info": {
                "type": random.choice(crop_types),
                "planted_date": fake.date_between(start_date='-6m', end_date='today').isoformat(),
                "field_size_hectares": round(random.uniform(10, 500), 2)
            },
            "environmental_sensors": {
                "temperature_celsius": round(base_temp + temp_variation, 2),
                "humidity_percent": round(random.uniform(40, 90), 2),
                "soil_moisture_percent": round(random.uniform(20, 80), 2),
                "ph_level": round(random.uniform(5.5, 7.5), 2),
                "light_intensity_lux": random.randint(1000, 80000)
            },
            "weather_data": {
                "precipitation_mm": round(random.uniform(0, 15), 2),
                "wind_speed_kmh": round(random.uniform(0, 25), 2),
                "atmospheric_pressure_hpa": round(random.uniform(1010, 1025), 2)
            },
            "equipment_status": {
                "irrigation_active": random.choice([True, False]),
                "fertilizer_level_percent": random.randint(0, 100),
                "machinery_status": random.choice(["operational", "maintenance_required", "offline"])
            },
            "data_quality": {
                "signal_strength": random.randint(70, 100),
                "battery_level": random.randint(20, 100),
                "sensor_calibration_date": fake.date_between(start_date='-30d', end_date='today').isoformat()
            }
        }
        
        return data

    def send_data(self):
        """Send simulated data to Kafka"""
        try:
            # Generate data for a random farm
            farm = random.choice(self.farm_locations)
            sensor_data = self.generate_sensor_data(farm)
            
            # Send to Kafka
            future = self.producer.send(
                self.topic,
                key=farm["farm_id"],
                value=sensor_data
            )
            
            # Wait for confirmation
            record_metadata = future.get(timeout=10)
            
            print(f"✅ Dados enviados - Farm: {farm['farm_id']}, "
                  f"Partition: {record_metadata.partition}, "
                  f"Offset: {record_metadata.offset}")
            
            return True
            
        except Exception as e:
            print(f"❌ Erro ao enviar dados: {str(e)}")
            return False

    def run(self):
        """Main loop to continuously send data"""
        print("🚀 Iniciando simulação de dados agrícolas...")
        
        try:
            while True:
                success = self.send_data()
                
                if success:
                    print(f"⏳ Aguardando {self.delay} segundos...")
                else:
                    print("🔄 Tentando novamente em 10 segundos...")
                    time.sleep(10)
                    continue
                    
                time.sleep(self.delay)
                
        except KeyboardInterrupt:
            print("\n⏹️  Parando produtor...")
        except Exception as e:
            print(f"💥 Erro crítico: {str(e)}")
        finally:
            self.producer.close()
            print("👋 Produtor finalizado!")

if __name__ == "__main__":
    producer = AgricultureDataProducer()
    producer.run()