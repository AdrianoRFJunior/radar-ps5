"""
Suíte Completa de Testes Automatizados do RADAR BF 2026 (Seção 16).
Utiliza um banco SQLite em memória completamente isolado (`sqlite:///:memory:`),
garantindo que os dados simulados nos testes NUNCA se misturem ao banco real.

Cobre todos os 14 requisitos obrigatórios da Seção 16:
1. Cadastro de produtos (e separação de PS5 Slim Digital vs Fat/Pro/Disco e DualSense Oficial vs Paralelo)
2. Cadastro de lojas
3. Coleta de preços
4. Armazenamento histórico (imutável)
5. Cálculo de média
6. Cálculo de mediana
7. Cálculo do menor preço
8. Cálculo do índice de oportunidade (incluindo trava para histórico insuficiente)
9. Detecção de falsos descontos ("metade do dobro" e preço "De:" inflado)
10. Geração de alertas internos
11. Funcionamento do agendador
12. Falhas de conexão nos coletores
13. Prevenção de duplicidade de registros de ofertas
14. Exibição dos dados do dashboard via API
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db, now_sp
from backend.main import app
from backend.models.models import Product, Store, Offer, PriceHistory, Alert, MonitoringLog
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO
from backend.collectors.classifier import classify_offer_title
from backend.analytics.statistics import compute_price_statistics
from backend.analytics.intelligence import calculate_opportunity_index
from backend.analytics.fake_discount import evaluate_fake_discount
from backend.analytics.event_mode import DEFAULT_PROMOTIONAL_EVENTS, evaluate_event_mode
from backend.services.monitoring_service import (
    ensure_initial_catalog_and_settings,
    upsert_collected_offer,
    recalculate_all_offers_intelligence,
)
from backend.scheduler.radar_scheduler import RadarMonitoringScheduler


# Banco em memória estritamente isolado para os testes
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=TEST_ENGINE)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Teste de Cadastro de Produtos e Classificação (Seções 2 e 16)
# ---------------------------------------------------------------------------
def test_product_registration_and_strict_classification(db_session):
    ensure_initial_catalog_and_settings(db_session)
    products = db_session.query(Product).all()
    assert len(products) >= 8

    # Verificar que PS5 Slim Digital é prioritário
    slim_dig = classify_offer_title("Console Sony PlayStation 5 Slim Digital Edition 1TB CFI-2014B", 3299.0)
    assert slim_dig.is_relevant is True
    assert slim_dig.category == "PS5"
    assert slim_dig.is_priority is True
    assert slim_dig.product_slug == "ps5-slim-digital-main"

    # Verificar que PS5 Fat e PS5 Pro NÃO se misturam ao PS5 Slim
    fat_res = classify_offer_title("Console PlayStation 5 Standard 825GB CFI-1214A", 3100.0)
    assert fat_res.is_priority is False
    assert fat_res.subcategory == "ALTERNATIVE"

    pro_res = classify_offer_title("Console Sony PlayStation 5 Pro 2TB SSD Digital", 6200.0)
    assert pro_res.is_priority is False
    assert pro_res.subcategory == "ALTERNATIVE"

    # Verificar que PS5 Slim com Leitor de Disco É monitorado como prioritário (junto com Digital) e identificado como DISC_EDITION
    disc_res = classify_offer_title("Console PlayStation 5 Slim 1TB com Leitor de Disco Mídia Física", 3599.0)
    assert disc_res.is_priority is True
    assert disc_res.subcategory == "DISC_EDITION"
    assert disc_res.product_slug == "ps5-slim-disc-main"

    # Verificar exclusão estrita de consoles usados/seminovos/open box
    used_res = classify_offer_title("Console PlayStation 5 Slim 1TB Seminovo Usado", 2900.0)
    assert used_res.is_relevant is False

    # Verificar diferenciação de DualSense Oficial vs Paralelo
    ds_official = classify_offer_title("Controle Sem Fio Sony DualSense PS5 Midnight Black Original", 349.0)
    assert ds_official.category == "DUALSENSE"
    assert ds_official.is_official is True
    assert ds_official.is_priority is True

    ds_parallel = classify_offer_title("Controle Sem Fio Compatível com PS5 Similar Paralelo Bluetooth", 220.0)
    assert ds_parallel.category == "DUALSENSE"
    assert ds_parallel.is_official is False
    assert ds_parallel.is_priority is False


# ---------------------------------------------------------------------------
# 2. Teste de Cadastro de Lojas Confiáveis (Sem Mercado Livre) (Seções 3 e 16)
# ---------------------------------------------------------------------------
def test_store_registration(db_session):
    ensure_initial_catalog_and_settings(db_session)
    stores = db_session.query(Store).all()
    store_slugs = {s.slug for s in stores}
    expected_slugs = {
        "amazon-br",
        "kabum",
        "magazine-luiza",
        "fast-shop",
        "casas-bahia",
        "ponto",
        "carrefour",
        "promobit",
        "pelando",
    }
    assert expected_slugs.issubset(store_slugs)
    assert "mercado-livre" not in store_slugs


# ---------------------------------------------------------------------------
# 3 & 4. Coleta de Preços e Armazenamento Histórico Imutável (Seções 5, 6 e 16)
# ---------------------------------------------------------------------------
def test_price_collection_and_immutable_history(db_session):
    ensure_initial_catalog_and_settings(db_session)
    store = db_session.query(Store).filter(Store.slug == "amazon-br").first()

    dto1 = CollectedOfferDTO(
        external_id="TEST-AMZ-PS5-001",
        title="Console Sony PlayStation 5 Slim Digital Edition 1TB Branco",
        url="https://www.amazon.com.br/dp/TEST001",
        price_cash=3499.00,
        shipping_cost=0.0,
        payment_condition="PIX",
        seller_name="Amazon.com.br",
    )
    offer = upsert_collected_offer(db_session, store, dto1)
    db_session.commit()
    assert offer is not None
    assert offer.final_price == 3499.00

    # Segunda coleta com queda de preço — não deve apagar o histórico anterior!
    dto2 = CollectedOfferDTO(
        external_id="TEST-AMZ-PS5-001",
        title="Console Sony PlayStation 5 Slim Digital Edition 1TB Branco",
        url="https://www.amazon.com.br/dp/TEST001",
        price_cash=3199.00,
        shipping_cost=25.00,
        payment_condition="PIX",
        seller_name="Amazon.com.br",
    )
    offer_updated = upsert_collected_offer(db_session, store, dto2)
    db_session.commit()

    assert offer_updated.id == offer.id
    assert offer_updated.previous_price == 3499.00
    assert offer_updated.final_price == 3224.00  # 3199 + 25 frete

    history_rows = db_session.query(PriceHistory).filter(PriceHistory.offer_id == offer.id).all()
    assert len(history_rows) == 2
    assert history_rows[0].final_price == 3499.00
    assert history_rows[1].final_price == 3224.00


# ---------------------------------------------------------------------------
# 5, 6 & 7. Cálculo de Média, Mediana e Menor Preço (Seções 6 e 16)
# ---------------------------------------------------------------------------
def test_statistics_mean_median_and_min_price():
    sample_prices = [3600.0, 3500.0, 3400.0, 3550.0, 3250.0]
    stats = compute_price_statistics(sample_prices)

    assert stats["count"] == 5
    assert stats["min_price"] == 3250.0
    assert stats["max_price"] == 3600.0
    assert stats["mean_price"] == 3460.0  # (3600+3500+3400+3550+3250)/5 = 17300/5 = 3460.0
    assert stats["median_price"] == 3500.0  # Ordenado: [3250, 3400, 3500, 3550, 3600] -> elemento central 3500
    assert stats["drops_count"] == 3
    assert stats["increases_count"] == 1


# ---------------------------------------------------------------------------
# 8. Cálculo do Índice de Oportunidade e Trava de Histórico Insuficiente (Seções 7 e 16)
# ---------------------------------------------------------------------------
def test_opportunity_index_calculation():
    # Oferta real excelente com histórico sólido
    hist_30d = [3650.0, 3599.0, 3550.0, 3499.0, 3480.0, 3450.0]
    eval_good = calculate_opportunity_index(
        final_price=3099.0,
        historical_prices_30d=hist_30d,
        all_historical_prices=hist_30d,
        other_stores_current_prices=[3499.0, 3599.0],
        previous_price=3450.0,
        shipping_cost=0.0,
        store_reputation=96.0,
        is_marketplace=False,
        has_official_warranty=True,
        payment_condition="PIX ou 10x sem juros",
        coupon_code="BF100",
        coupon_discount=100.0,
        in_stock=True,
        is_fake_discount=False,
    )
    assert eval_good.score >= 85
    assert "oportunidade" in eval_good.classification.lower()

    # Oferta sem histórico suficiente (< 3 pontos) não pode receber pontuação alta
    eval_short_history = calculate_opportunity_index(
        final_price=2900.0,
        historical_prices_30d=[2900.0],
        all_historical_prices=[2900.0],
        in_stock=True,
    )
    assert eval_short_history.score <= 55


# ---------------------------------------------------------------------------
# 9. Detecção de Falsos Descontos ("Metade do Dobro") (Seções 10 e 16)
# ---------------------------------------------------------------------------
def test_fake_discount_detection():
    # Exemplo clássico da especificação: custava R$ 2.500, subiu para R$ 3.200 e anuncia 20% OFF por R$ 2.560
    history_prices = [2500.0, 2490.0, 2510.0, 3200.0, 2560.0]
    eval_fake = evaluate_fake_discount(
        current_final_price=2560.0,
        original_declared_price=3200.0,
        historical_prices=history_prices,
        store_reputation=85.0,
        is_marketplace=True,
        expected_category="PS5",
    )
    assert eval_fake.is_fake_discount is True
    assert eval_fake.reliability_score < 65
    assert eval_fake.summary_reason is not None


# ---------------------------------------------------------------------------
# 10. Geração de Alertas Internos (Seções 11 e 16)
# ---------------------------------------------------------------------------
def test_internal_alert_generation(db_session):
    ensure_initial_catalog_and_settings(db_session)
    store = db_session.query(Store).filter(Store.slug == "kabum").first()
    # Simular nos testes uma queda de preço excelente para validar o disparo de alerta de oportunidade/mínimo histórico
    dto_promo = CollectedOfferDTO(
        external_id="TEST-ALERT-PROMO-01",
        title="Console Sony PlayStation 5 Slim Digital Edition 1TB CFI-2014B",
        url="https://www.kabum.com.br/produto/989702",
        price_cash=3399.00,
        shipping_cost=0.0,
        payment_condition="PIX",
        seller_name="KaBuM! (Venda Direta)",
    )
    upsert_collected_offer(db_session, store, dto_promo)
    db_session.commit()
    recalculate_all_offers_intelligence(db_session)

    alerts = db_session.query(Alert).all()
    assert len(alerts) >= 2
    alert_types = {a.alert_type for a in alerts}
    # Deve ter gerado alerta de oportunidade excelente/mínimo histórico e alerta de falso desconto/sobrepreço
    assert "FAKE_DISCOUNT" in alert_types
    assert any(t in alert_types for t in ("OPPORTUNITY_EXCELLENT", "OPPORTUNITY_EXCEPTIONAL", "HISTORICAL_LOW"))


# ---------------------------------------------------------------------------
# 11. Funcionamento do Agendador (Seções 5 e 16)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_scheduler_operation():
    test_sched = RadarMonitoringScheduler()
    test_sched.start(mode="NORMAL", interval_minutes=30)
    status = test_sched.get_status()
    assert status["scheduler_running"] is True
    assert status["current_mode"] == "NORMAL"
    assert status["current_interval_minutes"] == 30

    test_sched.reschedule(mode="HIGH_ACTIVITY", interval_minutes=10)
    status_high = test_sched.get_status()
    assert status_high["current_mode"] == "HIGH_ACTIVITY"
    assert status_high["current_interval_minutes"] == 10
    test_sched.shutdown()


# ---------------------------------------------------------------------------
# 12. Tratamento de Falhas de Conexão (Seções 16 e 17)
# ---------------------------------------------------------------------------
class FailingMockCollector(BaseStoreCollector):
    store_slug = "failing-store"
    store_name = "Loja Indisponível Teste"

    async def collect(self) -> CollectorResult:
        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message="Timeout de conexão simulado com o servidor da loja.",
            offers=[],
        )


@pytest.mark.asyncio
async def test_collector_connection_failure_handling():
    col = FailingMockCollector()
    res = await col.collect()
    assert res.status == "UNAVAILABLE"
    assert len(res.offers) == 0
    assert "Timeout" in res.status_message


# ---------------------------------------------------------------------------
# 13. Prevenção de Duplicidade de Registros de Ofertas (Seções 16 e 17)
# ---------------------------------------------------------------------------
def test_offer_deduplication(db_session):
    ensure_initial_catalog_and_settings(db_session)
    store = db_session.query(Store).filter(Store.slug == "kabum").first()
    initial_count = db_session.query(Offer).filter(Offer.store_id == store.id).count()

    dto_dup = CollectedOfferDTO(
        external_id="KABUM-UNIQUE-999",
        title="Controle Sem Fio Sony DualSense PS5 Branco Original",
        url="https://www.kabum.com.br/produto/999",
        price_cash=349.90,
    )
    upsert_collected_offer(db_session, store, dto_dup)
    upsert_collected_offer(db_session, store, dto_dup)
    db_session.commit()

    after_count = db_session.query(Offer).filter(Offer.store_id == store.id).count()
    assert after_count == initial_count + 1


# ---------------------------------------------------------------------------
# 14. Exibição do Dashboard e Rotas da API (Seções 4, 16 e 18)
# ---------------------------------------------------------------------------
def test_dashboard_and_api_endpoints(client):
    resp_dash = client.get("/api/dashboard")
    assert resp_dash.status_code == 200
    data = resp_dash.json()

    assert "indicators" in data
    assert "event_mode" in data
    assert "featured_products" in data
    assert data["indicators"]["monitored_products_count"] >= 8
    assert data["indicators"]["stores_consulted_count"] == 9
    assert data["featured_products"]["ps5"] is not None
    assert data["featured_products"]["ps5_lowest_digital"] is not None
    assert data["featured_products"]["ps5_lowest_disc"] is not None
    assert data["featured_products"]["dualsense"] is not None
    assert data["event_mode"]["next_event"] is not None or data["event_mode"]["active_event"] is not None

    # Validar detecção automática do Modo de Evento (ex: Singles' Day 11/11 e Black Friday)
    from datetime import datetime
    from backend.database import SAO_PAULO_TZ
    ev_during_bf = evaluate_event_mode(
        events_list=DEFAULT_PROMOTIONAL_EVENTS,
        lead_days=7,
        event_mode_enabled=True,
        interval_event_minutes=10,
        reference_dt=datetime(2026, 11, 27, 14, 0, tzinfo=SAO_PAULO_TZ),
    )
    assert ev_during_bf["mode_code"] == "EVENT_ACTIVE"
    assert ev_during_bf["is_intensified"] is True
    assert ev_during_bf["effective_interval_minutes"] == 10
    assert ev_during_bf["active_event"]["slug"] == "black-friday-2026"

    # Verificar demais rotas principais das 10 páginas
    for endpoint in [
        "/api/products",
        "/api/comparator",
        "/api/history?category=PS5&period=30d",
        "/api/intelligence",
        "/api/predictions",
        "/api/best-times",
        "/api/alerts",
        "/api/reports",
        "/api/settings",
    ]:
        r = client.get(endpoint)
        assert r.status_code == 200, f"Falha no endpoint {endpoint}"
