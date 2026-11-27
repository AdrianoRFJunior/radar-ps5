"""
Agendador Automático Independente integrado ao Motor Intensivo Black Friday (price_finder).
Executa varreduras automáticas em memória a cada 2 minutos durante a Black Friday,
sem sobrescrever snapshots com dados antigos do SQLite.
"""
import logging
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from backend.database import now_sp, format_sp_iso, SAO_PAULO_TZ
from backend.models.models import Setting
from backend.services.price_finder import find_and_save_best_prices

logger = logging.getLogger("radar_scheduler")


class RadarMonitoringScheduler:
    JOB_ID = "radar_bf2026_monitoring_job"

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=SAO_PAULO_TZ)
        self.current_mode: str = "BLACK_FRIDAY_LIVE"
        self.current_interval_minutes: int = 2
        self.last_run_at: Optional[str] = None
        self.last_run_summary: Optional[Dict[str, Any]] = None
        self.is_running_cycle: bool = False

    def compute_effective_schedule(self, setting: Optional[Setting] = None) -> tuple[str, int]:
        # Modo Intensivo Black Friday: varredura a cada 2 minutos!
        return ("BLACK_FRIDAY_LIVE", 2)

    async def _scheduled_task(self):
        if self.is_running_cycle:
            return
        self.is_running_cycle = True
        try:
            dash = await find_and_save_best_prices()
            self.last_run_at = format_sp_iso(now_sp())
            ind = dash.get("indicators", {})
            self.last_run_summary = {
                "offers_identified": ind.get("offers_identified_count", 0),
                "lowest_ps5_price": ind.get("lowest_ps5_price"),
                "lowest_dualsense_price": ind.get("lowest_dualsense_price"),
            }
        except Exception as exc:
            logger.error("Erro no ciclo agendado Black Friday: %s", exc)
        finally:
            self.is_running_cycle = False

    def start(self, mode: str = "BLACK_FRIDAY_LIVE", interval_minutes: int = 2):
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
        is_paused = job is not None and job.next_run_time is None
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
