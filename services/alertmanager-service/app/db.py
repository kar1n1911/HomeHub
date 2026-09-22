import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# Explicit DATABASE_URL is supported for isolated tests or external deployments.
# Normal deployments inject only this service's credentials, with no shared fallback.
def database_url():
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    password_file = os.getenv("PGPASSWORD_FILE")
    password = Path(password_file).read_text().strip() if password_file else os.environ["PGPASSWORD"]
    query = {"sslmode": os.getenv("PGSSLMODE", "require")}
    if os.getenv("PGSSLROOTCERT"):
        query["sslrootcert"] = os.environ["PGSSLROOTCERT"]
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["PGUSER"], password=password,
        host=os.environ["PGHOST"], port=int(os.getenv("PGPORT", "5432")),
        database=os.environ["PGDATABASE"], query=query,
    )


DATABASE_URL = database_url()
# Bound each replica's use of the shared database, including overflow.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
    pool_timeout=2,
    connect_args={"connect_timeout": 2, "options": "-c statement_timeout=2000"},
)
