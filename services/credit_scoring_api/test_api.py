import requests
import json
from datetime import datetime

API_URL = "http://localhost:8087"

def test_health():
    response = requests.get(f"{API_URL}/health")
    print(f"Health check: {response.status_code} - {response.json()}")

def test_credit_scoring():
    sample_request = {
        "proponente_id": "PROP_00001",
        "data_solicitacao": int(datetime.now().timestamp() * 1000),
        "cpf_cnpj": "123.456.789-00",
        "nome_razao_social": "Produtor Rural Teste",
        "tipo_pessoa": "FISICA",
        "renda_bruta_anual_declarada": 150000.0,
        "valor_solicitado_credito": 50000.0,
        "finalidade_credito": "CUSTEIO_SAFRA",
        "localizacao_propriedade": {
            "latitude": -15.7942,
            "longitude": -47.8822,
            "municipio": "Brasília",
            "uf": "DF"
        },
        "area_total_hectares": 100.0,
        "cultura_principal": "SOJA",
        "possui_experiencia_atividade": True,
        "anos_experiencia": 15,
        "fontes_dados_adicionais": {
            "serasa_score": 750,
            "ibama_autuacoes_ativas": False,
            "numero_matricula_imovel": "MAT-123456"
        },
        "metadata_evento": {
            "versao_schema": "1.0.0",
            "origem_dados": "test_api",
            "timestamp_geracao_evento": int(datetime.now().timestamp() * 1000)
        }
    }
    
    response = requests.post(f"{API_URL}/score", json=sample_request)
    print(f"Credit scoring: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Result: {json.dumps(result, indent=2)}")
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    try:
        test_health()
        test_credit_scoring()
    except requests.exceptions.ConnectionError:
        print("Could not connect to API. Make sure it's running on port 8087")