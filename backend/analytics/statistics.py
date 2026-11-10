"""
Módulo de Estatística de Histórico de Preços (Seção 6).
Calcula rigorosamente:
- Menor preço
- Maior preço
- Preço médio
- Mediana
- Desvio padrão
- Variação percentual
- Frequência de quedas
- Frequência de aumentos
Diferenciando condições de pagamento (PIX/à vista, cartão, cupom, frete).
"""
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database import now_sp, format_sp_iso
from backend.models.models import PriceHistory


@dataclass
class PriceStatisticsSummary:
    count: int
    min_price: Optional[float]
    max_price: Optional[float]
    mean_price: Optional[float]
    median_price: Optional[float]
    std_dev: Optional[float]
    variation_pct: Optional[float]
    drops_count: int
    increases_count: int
    stability_count: int
    drop_frequency_pct: float
    increase_frequency_pct: float
    lowest_pix_price: Optional[float]
    lowest_card_price: Optional[float]
    lowest_coupon_price: Optional[float]


def compute_price_statistics(prices: List[float]) -> Dict[str, Any]:
    """
    Calcula estatísticas descritivas exatas sobre uma sequência ordenada cronologicamente de preços.
    Usada diretamente pelos serviços e validada pelos testes automatizados.
    """
    clean_prices = [float(p) for p in prices if p is not None and p > 0]
    n = len(clean_prices)
    if n == 0:
        return {
            "count": 0,
            "min_price": None,
            "max_price": None,
            "mean_price": None,
            "median_price": None,
            "std_dev": None,
            "variation_pct": None,
            "drops_count": 0,
            "increases_count": 0,
            "stability_count": 0,
            "drop_frequency_pct": 0.0,
            "increase_frequency_pct": 0.0,
        }

    min_p = round(min(clean_prices), 2)
    max_p = round(max(clean_prices), 2)
    mean_p = round(statistics.mean(clean_prices), 2)
    median_p = round(statistics.median(clean_prices), 2)
    std_p = round(statistics.pstdev(clean_prices), 2) if n > 1 else 0.0

    first_p = clean_prices[0]
    last_p = clean_prices[-1]
    variation_pct = round(((last_p - first_p) / first_p) * 100.0, 2) if first_p > 0 else 0.0

    drops = 0
    increases = 0
    stable = 0
    for i in range(1, n):
        diff = clean_prices[i] - clean_prices[i - 1]
        if diff < -0.01:
            drops += 1
        elif diff > 0.01:
            increases += 1
        else:
            stable += 1

    transitions = max(1, n - 1) if n > 1 else 0
    drop_freq = round((drops / transitions) * 100.0, 2) if transitions > 0 else 0.0
    inc_freq = round((increases / transitions) * 100.0, 2) if transitions > 0 else 0.0

    return {
        "count": n,
        "min_price": min_p,
        "max_price": max_p,
        "mean_price": mean_p,
        "median_price": median_p,
        "std_dev": std_p,
        "variation_pct": variation_pct,
        "drops_count": drops,
        "increases_count": increases,
        "stability_count": stable,
        "drop_frequency_pct": drop_freq,
        "increase_frequency_pct": inc_freq,
    }


def get_product_history_and_stats(
    db: Session,
    product_id: Optional[int] = None,
    category: Optional[str] = None,
    period: str = "30d",
    payment_filter: str = "ALL",
    include_shipping: bool = True,
) -> Dict[str, Any]:
    """
    Retorna a série histórica e estatísticas completas para os períodos:
    24h, 7d, 30d, 90d ou all (Histórico completo), diferenciando condições de pagamento.
    """
    now = now_sp()
    cutoff_map = {
        "24h": now - timedelta(hours=24),
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "90d": now - timedelta(days=90),
        "all": None,
    }
    cutoff = cutoff_map.get(period, now - timedelta(days=30))

    query = db.query(PriceHistory)
    if product_id is not None:
        query = query.filter(PriceHistory.product_id == product_id)
    elif category is not None:
        from backend.models.models import Product
        query = query.join(Product, Product.id == PriceHistory.product_id).filter(
            Product.category == category,
            Product.is_priority.is_(True),
        )

    if cutoff is not None:
        # Comparar tanto aware quanto naive caso SQLite retorne naive
        cutoff_naive = cutoff.replace(tzinfo=None)
        query = query.filter(PriceHistory.recorded_at >= cutoff_naive)

    records: List[PriceHistory] = query.order_by(PriceHistory.recorded_at.asc()).all()

    filtered_records: List[PriceHistory] = []
    for r in records:
        cond_upper = (r.payment_condition or "").upper()
        if payment_filter == "PIX" and "PIX" not in cond_upper and "VISTA" not in cond_upper:
            continue
        if payment_filter == "CARD" and "CART" not in cond_upper and not r.price_card:
            continue
        if payment_filter == "COUPON" and not r.coupon_code:
            continue
        filtered_records.append(r)

    series_values: List[float] = []
    pix_prices: List[float] = []
    card_prices: List[float] = []
    coupon_prices: List[float] = []
    chart_points: List[Dict[str, Any]] = []

    for r in filtered_records:
        base_val = r.final_price if include_shipping else (r.price_found - (r.coupon_discount or 0.0))
        base_val = round(max(0.0, base_val), 2)
        series_values.append(base_val)

        pix_val = (r.price_found + (r.shipping_cost if include_shipping else 0.0)) - (r.coupon_discount or 0.0)
        pix_prices.append(round(pix_val, 2))

        if r.price_card and r.price_card > 0:
            c_val = r.price_card + (r.shipping_cost if include_shipping else 0.0) - (r.coupon_discount or 0.0)
            card_prices.append(round(c_val, 2))

        if r.coupon_code or (r.coupon_discount and r.coupon_discount > 0):
            coupon_prices.append(base_val)

        chart_points.append(
            {
                "id": r.id,
                "offer_id": r.offer_id,
                "product_id": r.product_id,
                "store_id": r.store_id,
                "store_name": r.store.name if r.store else r.seller_name,
                "price_cash": r.price_found,
                "price_card": r.price_card or r.price_found,
                "shipping_cost": r.shipping_cost,
                "coupon_discount": r.coupon_discount,
                "final_price": r.final_price,
                "compared_value": base_val,
                "payment_condition": r.payment_condition,
                "coupon_code": r.coupon_code,
                "is_promotional": r.is_promotional,
                "seller_name": r.seller_name,
                "recorded_at": format_sp_iso(r.recorded_at),
            }
        )

    base_stats = compute_price_statistics(series_values)
    base_stats["lowest_pix_price"] = min(pix_prices) if pix_prices else None
    base_stats["lowest_card_price"] = min(card_prices) if card_prices else None
    base_stats["lowest_coupon_price"] = min(coupon_prices) if coupon_prices else None
    base_stats["period"] = period
    base_stats["payment_filter"] = payment_filter
    base_stats["include_shipping"] = include_shipping

    return {
        "statistics": base_stats,
        "history": chart_points,
    }
