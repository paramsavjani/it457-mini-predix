import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://predix:change-me@localhost:5432/predix"
)
DB_POOL_MIN = int(os.getenv("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Label shown on the dashboard so we know which deployment we are looking at
DEPLOYMENT_NAME = os.getenv("DEPLOYMENT_NAME", "local")
