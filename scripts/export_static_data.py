"""
Exporta todos os endpoints do RADAR BF 2026 em arquivos JSON estáticos dentro de frontend/public/data/
e frontend/dist/data/ para que o painel publicado no GitHub Pages funcione 24/7 sem expiração.
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.database import Base, engine, SessionLocal  # noqa: E402
from backend.services.monitoring_service import (  # noqa: E402
    ensure_initial_catalog_and_settings,
    run_monitoring_cycle,
)
from backend.services.export_service import export_static_snapshots  # noqa: E402


async def export_all(run_scan: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_initial_catalog_and_settings(db)
        if run_scan:
            print("[export_static_data] Executando ciclo de monitoramento em tempo real...")
            await run_monitoring_cycle(db)

        result = export_static_snapshots(db)
        print(f"[export_static_data] {result['files_count']} arquivos JSON gerados com sucesso.")
    finally:
        db.close()


if __name__ == "__main__":
    should_scan = "--scan" in sys.argv
    asyncio.run(export_all(run_scan=should_scan))
