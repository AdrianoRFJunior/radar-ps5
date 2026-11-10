"""
Configuração de Banco de Dados do RADAR BF 2026.
Suporta SQLite inicialmente com índices otimizados, WAL mode e arquitetura pronta para PostgreSQL.
"""
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")
UTC_TZ = ZoneInfo("UTC")

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "radar_bf2026.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

is_sqlite = DATABASE_URL.startswith("sqlite")

connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

if is_sqlite:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

Base = declarative_base()


def now_sp() -> datetime:
    """Retorna o datetime atual com timezone America/Sao_Paulo."""
    return datetime.now(SAO_PAULO_TZ)


def format_sp_iso(dt: datetime | None) -> str | None:
    """Converte qualquer datetime (naive ou aware) para string ISO-8601 em America/Sao_Paulo."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SAO_PAULO_TZ)
    else:
        dt = dt.astimezone(SAO_PAULO_TZ)
    return dt.isoformat()


def get_db():
    """Dependency generator para sessões do banco de dados no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
