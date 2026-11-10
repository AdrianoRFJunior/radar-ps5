"""
Módulo PREVISÃO DE MERCADO (Seção 8).
Objetivo: identificar possíveis tendências de queda, aumento ou estabilidade para:
- Próximas 24 horas
- Próximos 3 dias (72h)
- Próximos 7 dias (168h)

Regras estritas (Seção 8):
- Utilizar métodos estatísticos simples e interpretáveis: Médias Móveis (7d e 30d), Regressão Linear Simples (OLS) e Volatilidade.
- Exibir: Tendência de queda, Tendência de aumento, Estabilidade, Confiança da estimativa e Quantidade de dados utilizados.
- IMPORTANTE: Nunca afirmar que uma promoção vai acontecer em determinado horário.
- Não apresentar correlações como certezas.
- Caso não existam dados suficientes (< 5 pontos históricos), informar claramente que a previsão não é confiável.
"""
import math
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.database import now_sp, format_sp_iso
from backend.models.models import PriceHistory, Product, PredictionResult


MIN_DATA_POINTS_FOR_RELIABLE_FORECAST = 6


def _linear_regression_daily_slope(timestamps_days: List[float], prices: List[float]) -> tuple[float, float, float]:
    """
    Calcula regressão linear simples y = a + b*x onde x é o tempo em dias.
    Retorna (intercept, slope_per_day, r_squared).
    """
    n = len(prices)
    if n < 2:
        return (prices[0] if prices else 0.0), 0.0, 0.0

    mean_x = sum(timestamps_days) / n
    mean_y = sum(prices) / n

    ss_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(timestamps_days, prices))
    ss_xx = sum((x - mean_x) ** 2 for x in timestamps_days)
    ss_yy = sum((y - mean_y) ** 2 for y in prices)

    if ss_xx <= 1e-9:
        return mean_y, 0.0, 0.0

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    r_sq = (ss_xy ** 2) / (ss_xx * ss_yy) if ss_yy > 1e-9 else 0.0
    return intercept, slope, max(0.0, min(1.0, r_sq))


def generate_product_predictions(db: Session, product: Product) -> List[Dict[str, Any]]:
    """
    Calcula e persiste as previsões para 24h, 3 dias e 7 dias de um produto.
    """
    now = now_sp()
    records: List[PriceHistory] = (
        db.query(PriceHistory)
        .filter(PriceHistory.product_id == product.id)
        .order_by(PriceHistory.recorded_at.asc())
        .all()
    )

    n = len(records)
    horizons = [
        (24, "Próximas 24 horas", 1.0),
        (72, "Próximos 3 dias", 3.0),
        (168, "Próximos 7 dias", 7.0),
    ]

    results: List[Dict[str, Any]] = []

    if n < MIN_DATA_POINTS_FOR_RELIABLE_FORECAST:
        current_p = records[-1].final_price if records else None
        for h_hours, h_label, _ in horizons:
            explanation = (
                f"Previsão não é confiável no momento: existem apenas {n} registro(s) no histórico "
                f"(mínimo recomendado: {MIN_DATA_POINTS_FOR_RELIABLE_FORECAST} coletas). "
                "Continue com o monitoramento automático ativo para acumular série temporal suficiente."
            )
            results.append(
                {
                    "product_id": product.id,
                    "product_name": product.name,
                    "category": product.category,
                    "horizon_hours": h_hours,
                    "horizon_label": h_label,
                    "trend": "DADOS_INSUFICIENTES",
                    "estimated_price": current_p,
                    "current_price": current_p,
                    "moving_avg_7d": current_p,
                    "moving_avg_30d": current_p,
                    "slope_per_day": 0.0,
                    "volatility_pct": 0.0,
                    "confidence_pct": round((n / MIN_DATA_POINTS_FOR_RELIABLE_FORECAST) * 35.0, 1),
                    "is_reliable": False,
                    "data_points_used": n,
                    "methodology": "Verificação de Amostragem Mínima",
                    "explanation": explanation,
                    "disclaimer": "Estimativas estatísticas indicam apenas tendências históricas e não garantem promoções futuras.",
                }
            )
        return results

    # Extrair tempos em dias relativos ao primeiro ponto e preços finais
    first_dt = records[0].recorded_at
    if first_dt.tzinfo is None:
        first_dt = first_dt.replace(tzinfo=now.tzinfo)

    x_days: List[float] = []
    y_prices: List[float] = []
    prices_7d: List[float] = []
    prices_30d: List[float] = []

    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    for r in records:
        dt = r.recorded_at if r.recorded_at.tzinfo else r.recorded_at.replace(tzinfo=now.tzinfo)
        delta_days = (dt - first_dt).total_seconds() / 86400.0
        x_days.append(delta_days)
        y_prices.append(float(r.final_price))
        if dt >= cutoff_7d:
            prices_7d.append(float(r.final_price))
        if dt >= cutoff_30d:
            prices_30d.append(float(r.final_price))

    current_price = y_prices[-1]
    ma_7d = round(statistics.mean(prices_7d if prices_7d else y_prices[-5:]), 2)
    ma_30d = round(statistics.mean(prices_30d if prices_30d else y_prices), 2)
    std_dev = statistics.pstdev(y_prices) if n > 1 else 0.0
    volatility_pct = round((std_dev / ma_30d) * 100.0, 2) if ma_30d > 0 else 0.0

    # Usar os últimos 30 dias (ou últimos 20 pontos) para regressão de tendência recente
    recent_x = x_days[-20:]
    recent_y = y_prices[-20:]
    _, slope_day, r_sq = _linear_regression_daily_slope(recent_x, recent_y)

    # Sazonalidade de Novembro / Proximidade da Black Friday (4ª sexta-feira de novembro de 2026 = 27/11/2026)
    days_to_bf = (datetime(2026, 11, 27, tzinfo=now.tzinfo) - now).days
    bf_context = ""
    if 0 <= days_to_bf <= 25:
        bf_context = f" Faltam {days_to_bf} dias para a Black Friday 2026 (27/11), período historicamente associado a maior volatilidade e queimas pontuais de estoque."

    # Limitar proyección máxima para evitar extrapolações absurdas
    min_hist = min(y_prices)
    max_hist = max(y_prices)

    # Limpar previsões antigas do produto e salvar as novas
    db.query(PredictionResult).filter(PredictionResult.product_id == product.id).delete()

    for h_hours, h_label, h_days in horizons:
        # Combinação de tendência linear amortecida com reversão parcial à média móvel de 7 dias
        damped_projection = current_price + (slope_day * h_days * 0.65) + ((ma_7d - current_price) * 0.25)
        estimated = round(max(min_hist * 0.85, min(max_hist * 1.15, damped_projection)), 2)

        pct_change_est = ((estimated - current_price) / current_price) * 100.0 if current_price > 0 else 0.0

        if pct_change_est <= -1.2 or (slope_day < -5.0 and ma_7d < ma_30d):
            trend = "TENDÊNCIA DE QUEDA"
        elif pct_change_est >= 1.2 or (slope_day > 5.0 and ma_7d > ma_30d):
            trend = "TENDÊNCIA DE AUMENTO"
        else:
            trend = "ESTABILIDADE"

        # Confiança depende da quantidade de pontos, baixa volatilidade e horizonte (24h > 3d > 7d)
        sample_factor = min(1.0, n / 25.0)
        vol_penalty = max(0.3, 1.0 - (volatility_pct / 35.0))
        horizon_decay = 0.92 if h_hours == 24 else (0.80 if h_hours == 72 else 0.68)
        confidence = round(min(88.0, max(42.0, (45.0 + sample_factor * 40.0) * vol_penalty * horizon_decay)), 1)

        explanation = (
            f"Baseado em {n} coletas históricas, a média móvel de 7 dias (R$ {ma_7d:.2f}) comparada à média de "
            f"30 dias (R$ {ma_30d:.2f}) e inclinação linear de R$ {slope_day:+.2f}/dia indicam {trend.lower()} "
            f"para o horizonte de {h_label.lower()} (volatilidade de {volatility_pct:.1f}%).{bf_context} "
            "Nota: modelos estatísticos refletem padrões passados e não constituem certeza de oferta futura."
        )

        pred_row = PredictionResult(
            product_id=product.id,
            horizon_hours=h_hours,
            horizon_label=h_label,
            trend=trend,
            estimated_price=estimated,
            current_price=current_price,
            moving_avg_7d=ma_7d,
            moving_avg_30d=ma_30d,
            slope_per_day=round(slope_day, 2),
            volatility_pct=volatility_pct,
            confidence_pct=confidence,
            is_reliable=True,
            data_points_used=n,
            methodology="Média Móvel (7d/30d) + Regressão Linear Amortecida (OLS)",
            explanation=explanation,
        )
        db.add(pred_row)

        results.append(
            {
                "product_id": product.id,
                "product_name": product.name,
                "category": product.category,
                "horizon_hours": h_hours,
                "horizon_label": h_label,
                "trend": trend,
                "estimated_price": estimated,
                "current_price": current_price,
                "moving_avg_7d": ma_7d,
                "moving_avg_30d": ma_30d,
                "slope_per_day": round(slope_day, 2),
                "volatility_pct": volatility_pct,
                "confidence_pct": confidence,
                "is_reliable": True,
                "data_points_used": n,
                "methodology": "Média Móvel (7d/30d) + Regressão Linear Amortecida (OLS)",
                "explanation": explanation,
                "disclaimer": "Não é possível afirmar com certeza que uma promoção ocorrerá em horário específico. Correlações históricas não representam garantia futura.",
            }
        )

    db.commit()
    return results
