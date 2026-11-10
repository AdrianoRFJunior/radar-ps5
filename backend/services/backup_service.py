"""
Serviço de Backup Automático do Banco de Dados (Seção 17).
Cria cópias seguras de backup do banco SQLite (ou dump de metadados) na pasta backups/.
"""
import os
import shutil
import sqlite3
from datetime import datetime
from backend.database import DEFAULT_DB_PATH, is_sqlite, now_sp


BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups")


def create_database_backup() -> dict:
    """Realiza backup consistente usando a API nativa de backup do SQLite."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = now_sp().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"radar_bf2026_backup_{ts}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    if is_sqlite and os.path.exists(DEFAULT_DB_PATH):
        src_conn = sqlite3.connect(DEFAULT_DB_PATH)
        dst_conn = sqlite3.connect(backup_path)
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()
        size_kb = round(os.path.getsize(backup_path) / 1024.0, 2)

        # Manter os 10 backups mais recentes
        backups = sorted(
            [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR) if f.endswith(".db")],
            key=os.path.getmtime,
            reverse=True,
        )
        for old_bkp in backups[10:]:
            try:
                os.remove(old_bkp)
            except OSError:
                pass

        return {
            "status": "SUCCESS",
            "backup_file": backup_filename,
            "backup_path": backup_path,
            "size_kb": size_kb,
            "created_at": now_sp().isoformat(),
        }

    return {
        "status": "SKIPPED",
        "message": "Banco de dados externo (PostgreSQL) ou arquivo ainda não materializado em disco.",
        "created_at": now_sp().isoformat(),
    }


def list_database_backups() -> list[dict]:
    if not os.path.exists(BACKUP_DIR):
        return []
    items = []
    for fname in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if fname.endswith(".db"):
            fpath = os.path.join(BACKUP_DIR, fname)
            items.append(
                {
                    "filename": fname,
                    "size_kb": round(os.path.getsize(fpath) / 1024.0, 2),
                    "modified_at": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                }
            )
    return items
