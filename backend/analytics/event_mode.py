"""
Motor de Detecção Automática de Eventos Promocionais e Cálculo do MODO DE EVENTO.
Integrado diretamente ao monitoramento principal do RADAR BF 2026 (sem módulos ou históricos duplicados).

Eventos suportados (configuráveis):
- Singles' Day (11/11)
- Esquenta / Semana Black Friday
- Black Friday (27/11/2026)
- Cyber Monday (30/11/2026)
- Prime Day / Mega Oferta Amazon

Comportamento:
- Detecta automaticamente se hoje estamos em evento ATIVO, PRÓXIMO (dentro da janela de antecedência configurada) ou NORMAL.
- Ajusta a frequência recomendada respeitando os limites de consulta de cada fonte.
- Nunca afirma que existe monitoramento em "tempo real" se a fonte depende de ciclos de consulta ou exige credenciais; identifica dados desatualizados.
"""
import json
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from backend.database import now_sp, SAO_PAULO_TZ


DEFAULT_PROMOTIONAL_EVENTS = [
    {
        "slug": "singles-day-11-11",
        "name": "Singles' Day (11/11)",
        "start_date": "2026-11-10",
        "end_date": "2026-11-12",
        "description": "Data dupla 11/11 com forte liberação de cupons relâmpago e descontos no PIX para eletrônicos e games.",
        "expand_coupon_search": True,
        "recommended_interval_minutes": 10,
    },
    {
        "slug": "black-friday-2026",
        "name": "Black Friday 2026",
        "start_date": "2026-11-26",
        "end_date": "2026-11-28",
        "description": "Evento principal do ano para compra do PlayStation 5 Slim Digital e controle DualSense adicional.",
        "expand_coupon_search": True,
        "recommended_interval_minutes": 5,
    },
    {
        "slug": "cyber-monday-2026",
        "name": "Cyber Monday 2026",
        "start_date": "2026-11-30",
        "end_date": "2026-12-01",
        "description": "Queima de estoque residual pós-Black Friday focada em hardware, consoles digitais e acessórios.",
        "expand_coupon_search": True,
        "recommended_interval_minutes": 10,
    },
    {
        "slug": "prime-day-2027",
        "name": "Amazon Prime Day",
        "start_date": "2027-07-14",
        "end_date": "2027-07-16",
        "description": "Evento promocional exclusivo Amazon Brasil com ofertas em consoles e acessórios PlayStation.",
        "expand_coupon_search": True,
        "recommended_interval_minutes": 10,
    },
]


def parse_events_json(raw_json: Optional[str]) -> List[Dict[str, Any]]:
    if not raw_json:
        return DEFAULT_PROMOTIONAL_EVENTS
    try:
        parsed = json.loads(raw_json)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed
    except Exception:
        pass
    return DEFAULT_PROMOTIONAL_EVENTS


def evaluate_event_mode(
    events_list: List[Dict[str, Any]],
    lead_days: int = 5,
    event_mode_enabled: bool = True,
    interval_normal_minutes: int = 30,
    interval_warmup_minutes: int = 15,
    interval_event_minutes: int = 10,
    interval_night_minutes: int = 60,
    prioritize_ps5_in_event: bool = True,
    reference_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Avalia a data/hora atual em America/Sao_Paulo contra o calendário de eventos configurados.
    Retorna o estado atual do MODO DE EVENTO, o evento ativo ou próximo, a contagem regressiva,
    as ações intensificadas ativas e o intervalo de consulta respeitando os limites das fontes.
    """
    now = reference_dt or now_sp()
    today: date = now.date()
    hour = now.hour
    is_night_hours = 0 <= hour < 6

    active_event: Optional[Dict[str, Any]] = None
    upcoming_event: Optional[Dict[str, Any]] = None
    min_days_until: Optional[int] = None

    enriched_calendar: List[Dict[str, Any]] = []

    for ev in events_list:
        try:
            start_d = date.fromisoformat(str(ev["start_date"])[:10])
            end_d = date.fromisoformat(str(ev["end_date"])[:10])
        except Exception:
            continue

        days_to_start = (start_d - today).days
        days_to_end = (end_d - today).days

        if start_d <= today <= end_d:
            ev_status = "ACTIVE"
        elif 0 < days_to_start <= lead_days:
            ev_status = "WARMUP"
        elif days_to_start > lead_days:
            ev_status = "UPCOMING"
        else:
            ev_status = "PAST"

        item = {
            **ev,
            "status": ev_status,
            "days_until_start": days_to_start,
            "days_until_end": days_to_end,
        }
        enriched_calendar.append(item)

        if ev_status == "ACTIVE" and active_event is None:
            active_event = item
        elif days_to_start > 0:
            if min_days_until is None or days_to_start < min_days_until:
                min_days_until = days_to_start
                upcoming_event = item

    # Determinar o modo de monitoramento e o intervalo efetivo
    if not event_mode_enabled:
        mode_code = "NORMAL"
        mode_label = "Monitoramento Padrão (Modo de Evento Desativado)"
        effective_interval = interval_night_minutes if is_night_hours else interval_normal_minutes
        is_intensified = False
    elif active_event is not None:
        mode_code = "EVENT_ACTIVE"
        mode_label = f"MODO DE EVENTO ATIVO: {active_event['name']}"
        # Mesmo durante evento, respeita limites mínimos das fontes (>= 5 min)
        effective_interval = max(5, int(interval_event_minutes))
        is_intensified = True
    elif upcoming_event is not None and upcoming_event["days_until_start"] <= lead_days:
        mode_code = "EVENT_WARMUP"
        mode_label = f"MODO AQUECIMENTO ({upcoming_event['days_until_start']}d para {upcoming_event['name']})"
        effective_interval = max(5, int(interval_warmup_minutes))
        is_intensified = True
    else:
        mode_code = "NIGHT" if is_night_hours else "NORMAL"
        mode_label = "Período Noturno (Respeitando Limites)" if is_night_hours else "Monitoramento Periódico Normal"
        effective_interval = interval_night_minutes if is_night_hours else interval_normal_minutes
        is_intensified = False

    active_actions = [
        "Comparação automática de preços finais entre lojas",
        "Atualização contínua das estatísticas por horário",
        "Atualização manual liberada a qualquer momento",
    ]
    if is_intensified:
        active_actions = [
            f"Consultas intensificadas a cada {effective_interval} min (respeitando rate-limit de cada fonte)",
            "Busca ampliada por cupons promocionais e descontos PIX",
            "Detecção imediata de quedas repentinas e ofertas temporárias (Flash Deals)",
            "Comparação cruzada entre lojas e atualização de estatísticas por horário",
            "Priorização de varredura para PlayStation 5 Slim Digital" if prioritize_ps5_in_event else "Monitoramento balanceado PS5 Slim Digital + DualSense",
        ]

    return {
        "event_mode_enabled": event_mode_enabled,
        "mode_code": mode_code,
        "mode_label": mode_label,
        "is_intensified": is_intensified,
        "effective_interval_minutes": effective_interval,
        "lead_days_configured": lead_days,
        "prioritize_ps5_active": bool(is_intensified and prioritize_ps5_in_event),
        "expand_coupon_search_active": is_intensified,
        "active_event": active_event,
        "next_event": upcoming_event,
        "days_until_next_event": min_days_until,
        "active_actions": active_actions,
        "calendar": enriched_calendar,
        "transparency_notice": (
            "As consultas respeitam rigorosamente os limites técnicos de cada loja. O sistema não afirma "
            "monitoramento em tempo real para fontes que bloqueiam acesso automatizado ou não fornecem API em tempo real, "
            "sinalizando claramente quando um dado está desatualizado."
        ),
    }
