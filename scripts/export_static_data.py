"""
Exporta todos os endpoints do RADAR BF 2026 em arquivos JSON estáticos dentro de frontend/public/data/
para que o painel publicado no GitHub Pages funcione 24/7 sem expiração e seja atualizado automaticamente
via GitHub Actions.
"""
import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.database import Base, engine, SessionLocal  # noqa: E402
from backend.routes.api_routes import (  # noqa: E402
    get_dashboard_data,
    get_monitored_products,
    get_price_comparator,
    get_price_history,
    get_radar_intelligence,
    get_market_predictions,
    get_best_times,
    get_internal_alerts,
    get_system_reports,
    get_user_settings,
    get_monitoring_logs,
)
from backend.services.backup_service import list_database_backups  # noqa: E402
from backend.services.monitoring_service import (  # noqa: E402
    ensure_initial_catalog_and_settings,
    run_monitoring_cycle,
)


async def export_all(run_scan: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    out_dir = ROOT_DIR / "frontend" / "public" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        ensure_initial_catalog_and_settings(db)
        if run_scan:
            print("[export_static_data] Executando ciclo de monitoramento em tempo real...")
            await run_monitoring_cycle(db)

        def _dump(filename: str, payload: dict) -> None:
            target = out_dir / filename
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  -> Gerado: {target.relative_to(ROOT_DIR)}")

        _dump("dashboard.json", get_dashboard_data(db=db))
        _dump("products.json", get_monitored_products(db=db))
        _dump(
            "comparator.json",
            get_price_comparator(category="ALL", include_alternatives=True, only_official_warranty=False, db=db),
        )
        _dump(
            "history_PS5.json",
            get_price_history(category="PS5", product_id=None, period="90d", payment_filter="ALL", include_shipping=True, db=db),
        )
        _dump(
            "history_DUALSENSE.json",
            get_price_history(category="DUALSENSE", product_id=None, period="90d", payment_filter="ALL", include_shipping=True, db=db),
        )
        _dump("intelligence.json", get_radar_intelligence(db=db))
        _dump("predictions.json", get_market_predictions(db=db))
        _dump("best-times.json", get_best_times(category=None, db=db))
        _dump("alerts.json", get_internal_alerts(include_archived=True, only_unread=False, db=db))
        _dump("reports.json", get_system_reports(db=db))
        _dump("settings.json", get_user_settings(db=db))
        _dump("logs.json", get_monitoring_logs(limit=40, db=db))
        _dump("backups.json", {"backups": list_database_backups()})
    finally:
        db.close()


if __name__ == "__main__":
    should_scan = "--scan" in sys.argv
    asyncio.run(export_all(run_scan=should_scan))
