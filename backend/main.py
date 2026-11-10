"""
Aplicação Principal do Backend RADAR BF 2026 (FastAPI).
Inicializa o banco de dados, catálogos, agendador automático independente e rotas da API.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import Base, engine, SessionLocal, now_sp, format_sp_iso
from backend.models import models  # noqa: F401
from backend.routes.api_routes import router as api_router
from backend.services.monitoring_service import ensure_initial_catalog_and_settings, run_monitoring_cycle
from backend.services.backup_service import create_database_backup
from backend.scheduler.radar_scheduler import radar_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Criar tabelas e índices no banco SQLite/PostgreSQL
    Base.metadata.create_all(bind=engine)

    # 2. Inicializar catálogo e configurações padrão
    db = SessionLocal()
    try:
        ensure_initial_catalog_and_settings(db)
        setting = db.query(models.Setting).first()
        mode, interval = radar_scheduler.compute_effective_schedule(setting)
    finally:
        db.close()

    # 3. Criar backup inicial e iniciar o agendador automático
    create_database_backup()
    auto_start = os.getenv("SCHEDULER_AUTO_START", "true").lower() == "true"
    if auto_start:
        radar_scheduler.start(mode=mode, interval_minutes=interval)
        # Disparar primeiro ciclo assíncrono em background após 5s para não concorrer com o carregamento inicial do painel
        async def _delayed_first_run():
            await asyncio.sleep(5)
            await radar_scheduler._scheduled_task()
        asyncio.create_task(_delayed_first_run())

    yield

    # Shutdown limpo do agendador
    radar_scheduler.shutdown()


app = FastAPI(
    title="RADAR BF 2026 — Sistema Inteligente de Monitoramento de Ofertas",
    description=(
        "Plataforma de inteligência de mercado, monitoramento contínuo, histórico estatístico "
        "e detecção de falsos descontos para PlayStation 5 Slim Digital e Sony DualSense."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    return {
        "system": "RADAR BF 2026",
        "status": "ONLINE",
        "server_time_sp": format_sp_iso(now_sp()),
        "scheduler": radar_scheduler.get_status(),
    }
