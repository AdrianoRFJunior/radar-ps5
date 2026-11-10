"""
Agendador Automático Independente do Frontend integrado ao MODO DE EVENTO.
Funciona continuamente enquanto o backend estiver ativo:
- Quando em AUTO_EVENT (ou Modo de Evento habilitado), detecta automaticamente a proximidade ou vigência de eventos promocionais (Singles' Day 11/11, Black Friday, Cyber Monday, Prime Day) e ajusta o intervalo de consulta respeitando os limites técnicos de cada fonte.
- Nunca afirma monitoramento em tempo real para fontes que dependem de consultas periódicas.
"""
import logging
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.database import SessionLocal, now_sp, format_sp_iso, SAO_PAULO_TZ
from backend.models.models import Setting
from backend.analytics.event_mode import parse_events_json, evaluate_event_mode
from backend.services.monitoring_service import run_monitoring_cycle
from backend.services.backup_service import create_database_backup

logger = logging.getLogger("radar_scheduler")


class RadarMonitoringScheduler:
    JOB_ID = "radar_bf2026_monitoring_job"
    BACKUP_JOB_ID = "radar_bf2026_backup_job"

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=SAO_PAULO_TZ)
        self.current_mode: str = "AUTO_EVENT"
        self.current_interval_minutes: int = 15
        self.last_run_at: Optional[str] = None
        self.last_run_summary: Optional[Dict[str, Any]] = None
        self.is_running_cycle: bool = False

    def compute_effective_schedule(self, setting: Optional[Setting]) -> tuple[str, int]:
        if not setting:
            return "NORMAL", 30

        hour = now_sp().hour
        if setting.scheduler_mode == "HIGH_ACTIVITY":
            return "HIGH_ACTIVITY", max(5, setting.interval_high_minutes)
        if setting.scheduler_mode == "NIGHT":
            return "NIGHT", max(5, setting.interval_night_minutes)
        if setting.scheduler_mode == "NORMAL" and not setting.event_mode_enabled:
            if 0 <= hour < 6:
                return "NIGHT", max(5, setting.interval_night_minutes)
            return "NORMAL", max(5, setting.interval_normal_minutes)

        # AUTO_EVENT / Modo de Evento Inteligente
        ev_state = evaluate_event_mode(
            events_list=parse_events_json(setting.custom_events_json),
            lead_days=setting.event_lead_days,
            event_mode_enabled=setting.event_mode_enabled,
            interval_normal_minutes=setting.interval_normal_minutes,
            interval_warmup_minutes=setting.interval_warmup_minutes,
            interval_event_minutes=setting.interval_high_minutes,
            interval_night_minutes=setting.interval_night_minutes,
            prioritize_ps5_in_event=setting.prioritize_ps5_in_event,
        )
        return ev_state["mode_code"], ev_state["effective_interval_minutes"]

    async def _scheduled_task(self):
        if self.is_running_cycle:
            return
        self.is_running_cycle = True
        db = SessionLocal()
        try:
            setting = db.query(Setting).first()
            target_mode, target_interval = self.compute_effective_schedule(setting)
            if target_interval != self.current_interval_minutes or target_mode != self.current_mode:
                self.reschedule(target_mode, target_interval)

            summary = await run_monitoring_cycle(db)
            self.last_run_at = format_sp_iso(now_sp())
            self.last_run_summary = summary
        except Exception as exc:
            logger.error("Erro no ciclo agendado: %s", exc)
        finally:
            db.close()
            self.is_running_cycle = False

    def _scheduled_backup(self):
        try:
            create_database_backup()
        except Exception as exc:
            logger.error("Erro ao criar backup agendado: %s", exc)

    def start(self, mode: str = "AUTO_EVENT", interval_minutes: int = 15):
        self.current_mode = mode
        self.current_interval_minutes = max(1, int(interval_minutes))
        if not self.scheduler.running:
            self.scheduler.add_job(
                self._scheduled_task,
                trigger=IntervalTrigger(minutes=self.current_interval_minutes, timezone=SAO_PAULO_TZ),
                id=self.JOB_ID,
                replace_existing=True,
                max_instances=1,
            )
            self.scheduler.add_job(
                self._scheduled_backup,
                trigger=IntervalTrigger(hours=6, timezone=SAO_PAULO_TZ),
                id=self.BACKUP_JOB_ID,
                replace_existing=True,
            )
            self.scheduler.start()

    def reschedule(self, mode: str, interval_minutes: int):
        self.current_mode = mode
        self.current_interval_minutes = max(1, int(interval_minutes))
        if self.scheduler.running:
            self.scheduler.reschedule_job(
                self.JOB_ID,
                trigger=IntervalTrigger(minutes=self.current_interval_minutes, timezone=SAO_PAULO_TZ),
            )

    def pause(self):
        if self.scheduler.running:
            job = self.scheduler.get_job(self.JOB_ID)
            if job:
                job.pause()

    def resume(self):
        if self.scheduler.running:
            job = self.scheduler.get_job(self.JOB_ID)
            if job:
                job.resume()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def get_status(self) -> Dict[str, Any]:
        job = self.scheduler.get_job(self.JOB_ID) if self.scheduler.running else None
        next_run = format_sp_iso(job.next_run_time) if (job and job.next_run_time) else None
        is_paused = (job is not None and job.next_run_time is None)
        return {
            "scheduler_running": self.scheduler.running and not is_paused,
            "is_paused": is_paused,
            "is_running_cycle_now": self.is_running_cycle,
            "current_mode": self.current_mode,
            "current_interval_minutes": self.current_interval_minutes,
            "last_run_at": self.last_run_at,
            "next_run_at": next_run,
        }


radar_scheduler = RadarMonitoringScheduler()
