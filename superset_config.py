import os

# ---------------------------------------------------------
# Conexão com o Banco de Dados (Metadata Backend)
# ---------------------------------------------------------
# O Superset precisa de um banco de dados para armazenar seus próprios metadados
# (usuários, dashboards, queries salvas, etc.).
# Aqui, usamos as variáveis de ambiente para construir a URL de conexão.

DB_USER = os.getenv("POSTGRES_USER", "superset")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "superset")
DB_HOST = os.getenv("DB_HOST", "superset-db") # O nome do serviço do banco de dados
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "superset")

# A URI completa para o SQLAlchemy
SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ---------------------------------------------------------
# Funcionalidades (Feature Flags)
# ---------------------------------------------------------
# Habilite ou desabilite funcionalidades experimentais ou avançadas aqui.
FEATURE_FLAGS = {
    # Habilita filtros cruzados em dashboards (muito útil)
    "DASHBOARD_CROSS_FILTERS": True,

    # Permite o uso de templates Jinja em queries SQL
    "ENABLE_TEMPLATE_PROCESSING": True,

    # Habilita o sistema de tags para organizar dashboards e charts
    "TAGGING_SYSTEM": True,
    
    # Habilita a criação de Alertas & Relatórios
    "ALERTS_ATTACH_REPORTS": True,
}

# ---------------------------------------------------------
# Configuração de Cache (Opcional, mas recomendado)
# ---------------------------------------------------------
# Para um melhor desempenho, você pode configurar um cache com Redis.
# Isso exigiria adicionar um serviço 'redis' ao seu docker-compose.yml.
# Exemplo de configuração de cache:
# CACHE_CONFIG = {
#     'CACHE_TYPE': 'RedisCache',
#     'CACHE_DEFAULT_TIMEOUT': 300,
#     'CACHE_KEY_PREFIX': 'superset_',
#     'CACHE_REDIS_HOST': 'redis', # Nome do serviço Redis
#     'CACHE_REDIS_PORT': 6379,
#     'CACHE_REDIS_DB': 1,
# }
# RESULTS_BACKEND = RedisCache(host='redis', port=6379, db=2)

# ---------------------------------------------------------
# Outras configurações
# ---------------------------------------------------------
# Chave secreta para assinar as sessões. Usar a variável de ambiente é o ideal.
SECRET_KEY = os.getenv("SUPERSET_SECRET_KEY")

# Chave de API do Mapbox para visualizações de mapa
# MAPBOX_API_KEY = 'sua_chave_aqui'

