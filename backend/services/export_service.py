"""
Serviço central de exportação dos snapshots JSON estáticos do RADAR BF 2026.
Salva instantaneamente em frontend/public/data/ e em frontend/dist/data/
para manter o GitHub Pages sempre atualizado e com máxima performance.
"""
import json
from pathlib import Path
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def export_static_snapshots(db: Session) -> dict:
    """Gera todos os arquivos JSON estáticos a partir do estado atual do banco de dados."""
    # Importações pontuais para evitar ciclos de importação
    from backend.routes.api_routes import (
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
    from backend.services.backup_service import list_database_backups

    out_dirs = [ROOT_DIR / "frontend" / "public" / "data"]
    dist_data = ROOT_DIR / "frontend" / "dist" / "data"
    if (ROOT_DIR / "frontend" / "dist").exists():
        dist_data.mkdir(parents=True, exist_ok=True)
        out_dirs.append(dist_data)

    for d in out_dirs:
        d.mkdir(parents=True, exist_ok=True)

    dashboard = get_dashboard_data(db=db)
    products = get_monitored_products(db=db)
    comparator = get_price_comparator(category="ALL", include_alternatives=True, only_official_warranty=False, db=db)
    hist_ps5 = get_price_history(category="PS5", product_id=None, period="90d", payment_filter="ALL", include_shipping=True, db=db)
    hist_ds = get_price_history(category="DUALSENSE", product_id=None, period="90d", payment_filter="ALL", include_shipping=True, db=db)
    intel = get_radar_intelligence(db=db)
    predictions = get_market_predictions(db=db)
    best_times = get_best_times(category=None, db=db)
    alerts = get_internal_alerts(include_archived=True, only_unread=False, db=db)
    reports = get_system_reports(db=db)
    settings = get_user_settings(db=db)
    logs = get_monitoring_logs(limit=40, db=db)
    backups = {"backups": list_database_backups()}

    files_map = {
        "dashboard.json": dashboard,
        "products.json": products,
        "comparator.json": comparator,
        "history_PS5.json": hist_ps5,
        "history_DUALSENSE.json": hist_ds,
        "intelligence.json": intel,
        "predictions.json": predictions,
        "best-times.json": best_times,
        "alerts.json": alerts,
        "reports.json": reports,
        "settings.json": settings,
        "logs.json": logs,
        "backups.json": backups,
    }

    for fname, payload in files_map.items():
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        for target_dir in out_dirs:
            (target_dir / fname).write_text(text, encoding="utf-8")

    return {
        "status": "SNAPSHOTS_EXPORTED",
        "files_count": len(files_map),
        "dashboard": dashboard,
    }
