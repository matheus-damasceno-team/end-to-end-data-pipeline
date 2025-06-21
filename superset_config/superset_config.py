# Superset Configuration
# PATH: superset_config/superset_config.py

import os
from flask_caching.backends.redis import RedisCache

# Database Configuration
SQLALCHEMY_DATABASE_URI = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

# Redis Configuration for Caching
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': os.getenv('REDIS_HOST', 'redis'),
    'CACHE_REDIS_PORT': int(os.getenv('REDIS_PORT', 6379)),
    'CACHE_REDIS_DB': 1,
    'CACHE_REDIS_URL': f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', 6379)}/1"
}

# Results Backend Cache
RESULTS_BACKEND = RedisCache(
    host=os.getenv('REDIS_HOST', 'redis'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    key_prefix='superset_results_'
)

# Security Configuration
SECRET_KEY = os.getenv('SUPERSET_SECRET_KEY', 'your-secret-key-change-this-in-production')
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None

# Feature Flags
FEATURE_FLAGS = {
    'DASHBOARD_NATIVE_FILTERS': True,
    'ENABLE_TEMPLATE_PROCESSING': True,
    'DASHBOARD_CROSS_FILTERS': True,
    'DASHBOARD_RBAC': True,
    'EMBEDDABLE_CHARTS': True,
    'ESCAPING_MARKUP_IN_TOOLTIPS': True,
    'GENERIC_CHART_AXES': True,
}

# Row Level Security
ROW_LEVEL_SECURITY_CONFIG = {
    'ENABLE_ROW_LEVEL_SECURITY': True,
}

# Async Query Configuration
SUPERSET_ASYNC_QUERY_CONFIG = {
    'SQLLAB_ASYNC_TIME_LIMIT_SEC': 300,
    'SUPERSET_WEBSERVER_TIMEOUT': 300,
}

# Email Configuration (optional - configure if needed)
# SMTP_HOST = 'your-smtp-host'
# SMTP_STARTTLS = True
# SMTP_SSL = False
# SMTP_USER = 'your-email'
# SMTP_PORT = 587
# SMTP_PASSWORD = 'your-password'
# SMTP_MAIL_FROM = 'your-email'

# Logging
ENABLE_TIME_ROTATE = True
TIME_ROTATE_LOG_LEVEL = 'DEBUG'
FILENAME = '/app/superset.log'

# SQL Lab Configuration
SQLLAB_TIMEOUT = 300
SQLLAB_ASYNC_TIME_LIMIT_SEC = 60
SUPERSET_WEBSERVER_TIMEOUT = 60

# Custom CSS (optional)
# CUSTOM_CSS = """
# .navbar-brand {
#     font-size: 18px;
# }
# """