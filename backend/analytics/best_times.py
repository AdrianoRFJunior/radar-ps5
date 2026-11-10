"""
Módulo ANÁLISE DE HORÁRIOS — MELHORES HORÁRIOS (Seção 9).
Agrupa os dados por:
- Hora do dia (00h a 23h)
- Dia da semana (Segunda a Domingo)
- Dia do mês (1 a 31)
- Semana da Black Friday (Semanas 1 a 4 de Novembro + Semana da BF)

Gera dados para os gráficos:
- Quantidade de quedas por horário
- Quantidade de ofertas por horário
- Média de desconto por horário
- Horários com maior frequência (taxa normalizada) de oportunidades
- Horários com maiores quedas de preço

Regra estrita:
- Diferenciar quantidade de ofertas e qualidade das ofertas.
- Não declarar que determinado horário é melhor apenas por existir mais registros. Considera a taxa proporcional (quedas / total de consultas realizadas naquele período).
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.database import SAO_PAULO_TZ
from backend.models.models import PriceHistory, Product


WEEKDAYS_PT = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]


def analyze_best_times(db: Session, category: Optional[str] = None) -> Dict[str, Any]:
    query = db.query(PriceHistory).join(Product, Product.id == PriceHistory.product_id).filter(Product.is_priority.is_(True))
    if category:
        query = query.filter(Product.category == category)

    records: List[PriceHistory] = query.order_by(PriceHistory.recorded_at.asc()).all()

    # Calcular média global por produto para medir qualidade real do desconto em cada registro
    product_prices: Dict[int, List[float]] = {}
    for r in records:
        product_prices.setdefault(r.product_id, []).append(float(r.final_price))

    product_avg: Dict[int, float] = {
        pid: (sum(vals) / len(vals)) for pid, vals in product_prices.items() if vals
    }

    # Estruturas por Hora (0..23)
    hourly_stats = {
        h: {
            "hour": h,
            "hour_label": f"{h:02d}:00",
            "checks_count": 0,
            "offers_with_discount_count": 0,
            "drops_count": 0,
            "high_quality_opportunities_count": 0,
            "discounts_pct_sum": 0.0,
            "max_drop_pct": 0.0,
        }
        for h in range(24)
    }

    # Estruturas por Dia da Semana (0..6)
    weekday_stats = {
        d: {
            "weekday_index": d,
            "weekday": WEEKDAYS_PT[d],
            "checks_count": 0,
            "drops_count": 0,
            "opportunities_count": 0,
            "discounts_pct_sum": 0.0,
        }
        for d in range(7)
    }

    # Estruturas por Dia do Mês (1..31)
    month_day_stats: Dict[int, Dict[str, Any]] = {}

    # Estruturas por Semana da Black Friday (Novembro)
    bf_week_stats = {
        "Semana 1 (01 a 07/Nov - Esquenta)": {"label": "Semana 1 (01-07/Nov)", "checks": 0, "drops": 0, "opportunities": 0, "discount_sum": 0.0},
        "Semana 2 (08 a 14/Nov - Pré-BF)": {"label": "Semana 2 (08-14/Nov)", "checks": 0, "drops": 0, "opportunities": 0, "discount_sum": 0.0},
        "Semana 3 (15 a 21/Nov - Antecipação)": {"label": "Semana 3 (15-21/Nov)", "checks": 0, "drops": 0, "opportunities": 0, "discount_sum": 0.0},
        "Semana Black Friday (22 a 28/Nov)": {"label": "Semana BF (22-28/Nov)", "checks": 0, "drops": 0, "opportunities": 0, "discount_sum": 0.0},
        "Cyber Monday & Pós-BF (29/Nov+)": {"label": "Cyber Monday (29-30/Nov)", "checks": 0, "drops": 0, "opportunities": 0, "discount_sum": 0.0},
    }

    for r in records:
        dt = r.recorded_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=SAO_PAULO_TZ)
        else:
            dt = dt.astimezone(SAO_PAULO_TZ)

        h = dt.hour
        wd = dt.weekday()
        dom = dt.day

        avg_p = product_avg.get(r.product_id, r.final_price)
        discount_vs_avg_pct = max(0.0, ((avg_p - r.final_price) / avg_p) * 100.0) if avg_p > 0 else 0.0

        is_drop = bool(r.previous_price and r.previous_price > r.final_price + 0.01)
        drop_pct = ((r.previous_price - r.final_price) / r.previous_price) * 100.0 if (is_drop and r.previous_price) else 0.0

        is_promo_offer = discount_vs_avg_pct >= 2.0 or bool(r.coupon_code) or is_drop
        is_high_quality_opportunity = discount_vs_avg_pct >= 7.5 or drop_pct >= 6.0

        # Atualizar Hora
        hs = hourly_stats[h]
        hs["checks_count"] += 1
        if is_promo_offer:
            hs["offers_with_discount_count"] += 1
            hs["discounts_pct_sum"] += max(discount_vs_avg_pct, drop_pct)
        if is_drop:
            hs["drops_count"] += 1
            if drop_pct > hs["max_drop_pct"]:
                hs["max_drop_pct"] = round(drop_pct, 2)
        if is_high_quality_opportunity:
            hs["high_quality_opportunities_count"] += 1

        # Atualizar Dia da Semana
        ws = weekday_stats[wd]
        ws["checks_count"] += 1
        if is_drop:
            ws["drops_count"] += 1
        if is_high_quality_opportunity:
            ws["opportunities_count"] += 1
        ws["discounts_pct_sum"] += max(discount_vs_avg_pct, drop_pct)

        # Atualizar Dia do Mês
        mds = month_day_stats.setdefault(
            dom,
            {"day": dom, "checks_count": 0, "drops_count": 0, "opportunities_count": 0, "avg_discount_pct": 0.0, "_disc_sum": 0.0},
        )
        mds["checks_count"] += 1
        if is_drop:
            mds["drops_count"] += 1
        if is_high_quality_opportunity:
            mds["opportunities_count"] += 1
        mds["_disc_sum"] += max(discount_vs_avg_pct, drop_pct)

        # Atualizar Semana da Black Friday
        if dt.month == 11:
            if dom <= 7:
                wkey = "Semana 1 (01 a 07/Nov - Esquenta)"
            elif dom <= 14:
                wkey = "Semana 2 (08 a 14/Nov - Pré-BF)"
            elif dom <= 21:
                wkey = "Semana 3 (15 a 21/Nov - Antecipação)"
            elif dom <= 28:
                wkey = "Semana Black Friday (22 a 28/Nov)"
            else:
                wkey = "Cyber Monday & Pós-BF (29/Nov+)"
            bws = bf_week_stats[wkey]
            bws["checks"] += 1
            if is_drop:
                bws["drops"] += 1
            if is_high_quality_opportunity:
                bws["opportunities"] += 1
            bws["discount_sum"] += max(discount_vs_avg_pct, drop_pct)

    # Normalizar métricas por Hora (Qualidade x Quantidade ponderada por número de consultas)
    hourly_list = []
    for h in range(24):
        hs = hourly_stats[h]
        checks = hs["checks_count"]
        promo_cnt = hs["offers_with_discount_count"]
        avg_disc = round(hs["discounts_pct_sum"] / promo_cnt, 2) if promo_cnt > 0 else 0.0
        opp_rate_pct = round((hs["high_quality_opportunities_count"] / checks) * 100.0, 2) if checks > 0 else 0.0
        drop_rate_pct = round((hs["drops_count"] / checks) * 100.0, 2) if checks > 0 else 0.0
        # Índice composto de eficiência do horário (qualidade ajustada pelo volume de consultas)
        efficiency_index = round((opp_rate_pct * 0.5) + (avg_disc * 3.0) + (hs["max_drop_pct"] * 1.5), 2) if checks > 0 else 0.0

        hourly_list.append(
            {
                "hour": h,
                "hour_label": hs["hour_label"],
                "checks_count": checks,
                "offers_count": promo_cnt,
                "drops_count": hs["drops_count"],
                "opportunities_count": hs["high_quality_opportunities_count"],
                "avg_discount_pct": avg_disc,
                "max_drop_pct": hs["max_drop_pct"],
                "opportunity_rate_pct": opp_rate_pct,
                "drop_rate_pct": drop_rate_pct,
                "quality_efficiency_index": efficiency_index,
            }
        )

    weekday_list = []
    for d in range(7):
        ws = weekday_stats[d]
        checks = ws["checks_count"]
        avg_d = round(ws["discounts_pct_sum"] / checks, 2) if checks > 0 else 0.0
        opp_rate = round((ws["opportunities_count"] / checks) * 100.0, 2) if checks > 0 else 0.0
        weekday_list.append(
            {
                "weekday": ws["weekday"],
                "checks_count": checks,
                "drops_count": ws["drops_count"],
                "opportunities_count": ws["opportunities_count"],
                "avg_discount_pct": avg_d,
                "opportunity_rate_pct": opp_rate,
            }
        )

    month_day_list = []
    for dom in sorted(month_day_stats.keys()):
        mds = month_day_stats[dom]
        c = mds["checks_count"]
        month_day_list.append(
            {
                "day": dom,
                "label": f"Dia {dom:02d}",
                "checks_count": c,
                "drops_count": mds["drops_count"],
                "opportunities_count": mds["opportunities_count"],
                "avg_discount_pct": round(mds["_disc_sum"] / c, 2) if c > 0 else 0.0,
            }
        )

    bf_weeks_list = []
    for k, bws in bf_week_stats.items():
        c = bws["checks"]
        bf_weeks_list.append(
            {
                "week_name": k,
                "label": bws["label"],
                "checks_count": c,
                "drops_count": bws["drops"],
                "opportunities_count": bws["opportunities"],
                "avg_discount_pct": round(bws["discount_sum"] / c, 2) if c > 0 else 0.0,
                "opportunity_rate_pct": round((bws["opportunities"] / c) * 100.0, 2) if c > 0 else 0.0,
            }
        )

    # Identificar melhores horários considerando taxa proporcional (evitando viés de volume bruto de consultas)
    valid_hours = [h for h in hourly_list if h["checks_count"] > 0]
    best_by_quality = sorted(valid_hours, key=lambda x: (x["quality_efficiency_index"], x["opportunity_rate_pct"]), reverse=True)[:3]
    best_by_drop_magnitude = sorted(valid_hours, key=lambda x: (x["max_drop_pct"], x["avg_discount_pct"]), reverse=True)[:3]

    return {
        "total_records_analyzed": len(records),
        "by_hour": hourly_list,
        "by_weekday": weekday_list,
        "by_month_day": month_day_list,
        "by_bf_week": bf_weeks_list,
        "top_quality_hours": best_by_quality,
        "top_drop_hours": best_by_drop_magnitude,
        "methodology_note": (
            "A classificação de Melhores Horários pondera a Taxa de Oportunidades Reais (oportunidades dividido pelo "
            "número de consultas realizadas naquela faixa horária) e a Média de Desconto Real, evitando declarar "
            "um horário como melhor apenas por possuir mais consultas."
        ),
    }
