from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
import redis
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Credit Scoring API", version="1.0.0")

redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

class LocalizacaoPropriedade(BaseModel):
    latitude: float
    longitude: float
    municipio: str
    uf: str

class FontesDadosAdicionais(BaseModel):
    serasa_score: Optional[int] = None
    ibama_autuacoes_ativas: Optional[bool] = None
    numero_matricula_imovel: str

class MetadataEvento(BaseModel):
    versao_schema: str
    origem_dados: str
    timestamp_geracao_evento: int

class CreditRequest(BaseModel):
    proponente_id: str
    data_solicitacao: int
    cpf_cnpj: str
    nome_razao_social: str
    tipo_pessoa: str
    renda_bruta_anual_declarada: float
    valor_solicitado_credito: float
    finalidade_credito: str
    localizacao_propriedade: LocalizacaoPropriedade
    area_total_hectares: float
    cultura_principal: str
    possui_experiencia_atividade: bool
    anos_experiencia: int
    fontes_dados_adicionais: FontesDadosAdicionais
    metadata_evento: MetadataEvento

class CreditResponse(BaseModel):
    proponente_id: str
    status: str
    score: float
    credit_limit: float
    risk_level: str
    recommendation: str
    timestamp: str

model = None

def load_model():
    global model
    try:
        model_path = '/app/models/credit_model.joblib'
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            logger.info("Model loaded successfully with joblib")
        else:
            # Fallback to pickle for backward compatibility
            pickle_path = '/app/models/credit_model.pkl'
            if os.path.exists(pickle_path):
                import pickle
                with open(pickle_path, 'rb') as f:
                    model = pickle.load(f)
                logger.info("Model loaded successfully with pickle (fallback)")
            else:
                raise FileNotFoundError("No model file found")
    except Exception as e:
        logger.warning(f"Could not load model: {e}")
        model = None

def get_features_from_redis(proponente_id: str) -> Dict[str, Any]:
    try:
        proponente_features = redis_client.get(f"proponente_features:{proponente_id}")
        location_features = redis_client.get(f"location_features:{proponente_id}")
        risk_features = redis_client.get(f"risk_features:{proponente_id}")
        
        features = {}
        if proponente_features:
            features.update(json.loads(proponente_features))
        if location_features:
            features.update(json.loads(location_features))
        if risk_features:
            features.update(json.loads(risk_features))
            
        return features
    except Exception as e:
        logger.error(f"Error retrieving features from Redis: {e}")
        return {}

def calculate_credit_score(request: CreditRequest) -> Dict[str, Any]:
    features = get_features_from_redis(request.proponente_id)
    
    if not features:
        logger.warning(f"No features found for {request.proponente_id}, using request data")
        features = create_features_from_request(request)
    
    if model is not None:
        try:
            feature_vector = prepare_feature_vector(features)
            score = model.predict_proba([feature_vector])[0][1]
        except Exception as e:
            logger.error(f"Error using model: {e}")
            score = calculate_fallback_score(request)
    else:
        score = calculate_fallback_score(request)
    
    risk_level = "LOW" if score > 0.7 else "MEDIUM" if score > 0.4 else "HIGH"
    
    credit_limit = calculate_credit_limit(request, score)
    
    recommendation = "APPROVE" if score > 0.6 else "MANUAL_REVIEW" if score > 0.3 else "DENY"
    
    return {
        "score": float(score),
        "risk_level": risk_level,
        "credit_limit": float(credit_limit),
        "recommendation": recommendation
    }

def create_features_from_request(request: CreditRequest) -> Dict[str, Any]:
    return {
        "renda_bruta_anual_declarada": request.renda_bruta_anual_declarada,
        "valor_solicitado_credito": request.valor_solicitado_credito,
        "area_total_hectares": request.area_total_hectares,
        "anos_experiencia": request.anos_experiencia,
        "possui_experiencia_atividade": 1 if request.possui_experiencia_atividade else 0,
        "tipo_pessoa_fisica": 1 if request.tipo_pessoa == "FISICA" else 0,
        "serasa_score": request.fontes_dados_adicionais.serasa_score or 500,
        "ibama_autuacoes_ativas": 1 if request.fontes_dados_adicionais.ibama_autuacoes_ativas else 0,
        "cultura_principal_soja": 1 if request.cultura_principal == "SOJA" else 0,
        "cultura_principal_milho": 1 if request.cultura_principal == "MILHO" else 0,
        "finalidade_custeio": 1 if request.finalidade_credito == "CUSTEIO_SAFRA" else 0,
        "finalidade_investimento": 1 if request.finalidade_credito == "INVESTIMENTO_MAQUINARIO" else 0,
    }

def prepare_feature_vector(features: Dict[str, Any]) -> list:
    expected_features = [
        "total_solicitacoes", "valor_total_solicitado", "valor_medio_solicitado",
        "valor_maximo_solicitado", "valor_minimo_solicitado", "serasa_score_medio",
        "anos_experiencia_medio", "area_media_hectares", "taxa_autuacoes_ibama",
        "diversidade_culturas", "diversidade_finalidades"
    ]
    
    return [features.get(feature, 0) for feature in expected_features]

def calculate_fallback_score(request: CreditRequest) -> float:
    score = 0.5
    
    income_to_credit_ratio = request.renda_bruta_anual_declarada / request.valor_solicitado_credito
    if income_to_credit_ratio > 5:
        score += 0.2
    elif income_to_credit_ratio > 3:
        score += 0.1
    elif income_to_credit_ratio < 1:
        score -= 0.3
    
    if request.anos_experiencia > 10:
        score += 0.1
    elif request.anos_experiencia > 5:
        score += 0.05
    elif request.anos_experiencia == 0:
        score -= 0.2
    
    if request.area_total_hectares > 500:
        score += 0.1
    elif request.area_total_hectares > 100:
        score += 0.05
    
    if request.fontes_dados_adicionais.serasa_score:
        if request.fontes_dados_adicionais.serasa_score > 700:
            score += 0.2
        elif request.fontes_dados_adicionais.serasa_score > 500:
            score += 0.1
        else:
            score -= 0.1
    
    if request.fontes_dados_adicionais.ibama_autuacoes_ativas:
        score -= 0.15
    
    return max(0.0, min(1.0, score))

def calculate_credit_limit(request: CreditRequest, score: float) -> float:
    base_limit = min(request.valor_solicitado_credito, request.renda_bruta_anual_declarada * 0.3)
    
    score_multiplier = 0.5 + (score * 0.5)
    
    return base_limit * score_multiplier

@app.on_event("startup")
async def startup_event():
    load_model()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "model_loaded": model is not None}

@app.post("/score", response_model=CreditResponse)
async def score_credit_request(request: CreditRequest):
    try:
        result = calculate_credit_score(request)
        
        response = CreditResponse(
            proponente_id=request.proponente_id,
            status="success",
            score=result["score"],
            credit_limit=result["credit_limit"],
            risk_level=result["risk_level"],
            recommendation=result["recommendation"],
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"Credit scoring completed for {request.proponente_id}: {result['recommendation']}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing credit request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/features/{proponente_id}")
async def get_features(proponente_id: str):
    features = get_features_from_redis(proponente_id)
    if not features:
        raise HTTPException(status_code=404, detail="Features not found")
    return features

@app.get("/model-info")
async def get_model_info():
    """Get information about the current ML model"""
    try:
        model_info = {
            "model_loaded": model is not None,
            "model_type": type(model).__name__ if model is not None else None,
            "model_path": "/app/models/credit_model.joblib",
            "fallback_mode": model is None
        }
        
        # Try to get model metrics from file
        try:
            metrics_path = '/app/models/model_metrics.json'
            if os.path.exists(metrics_path):
                with open(metrics_path, 'r') as f:
                    metrics = json.load(f)
                model_info.update({
                    "metrics": metrics,
                    "metrics_available": True
                })
            else:
                model_info["metrics_available"] = False
        except Exception as e:
            logger.warning(f"Could not load model metrics: {e}")
            model_info["metrics_available"] = False
        
        # Try to get deployment info
        try:
            deployment_path = '/app/models/deployment_info.json'
            if os.path.exists(deployment_path):
                with open(deployment_path, 'r') as f:
                    deployment_info = json.load(f)
                model_info.update({
                    "deployment_info": deployment_info,
                    "deployment_info_available": True
                })
            else:
                model_info["deployment_info_available"] = False
        except Exception as e:
            logger.warning(f"Could not load deployment info: {e}")
            model_info["deployment_info_available"] = False
        
        # Add API info
        model_info.update({
            "api_version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        })
        
        return model_info
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)