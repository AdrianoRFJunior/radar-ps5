"""
Modelos ORM SQLAlchemy para todas as 9 tabelas exigidas pelo RADAR BF 2026:
- products
- stores
- offers
- price_history
- alerts
- monitoring_logs
- coupons
- settings
- prediction_results
"""
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from backend.database import Base, now_sp


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=False, index=True)  # "PS5" ou "DUALSENSE"
    subcategory = Column(String(60), nullable=False, default="MAIN")
    # Subcategorias PS5: MAIN (Slim Digital), BUNDLE_GAMES, BUNDLE_CONTROLLER, ALTERNATIVE (Fat, Pro, Slim Disco)
    # Subcategorias DUALSENSE: MAIN (Branco/Preto), COLOR_VARIANT, SPECIAL_EDITION, ALTERNATIVE (Paralelo/Similar)
    edition_type = Column(String(80), nullable=True)  # Digital, Disc, Fat, Pro, Standard, Edge, Parallel
    model_revision = Column(String(60), nullable=True)  # Ex: CFI-2014B, CFI-2015B, CFI-ZCT1W
    color = Column(String(60), nullable=True)
    is_official = Column(Boolean, default=True, nullable=False)
    is_priority = Column(Boolean, default=True, nullable=False)  # False para Fat, Pro, Slim Disco ou controles paralelos
    image_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    target_price = Column(Float, nullable=True)  # Opcional (orçamento flexível)
    excellent_price = Column(Float, nullable=True)  # Opcional
    created_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_sp, onupdate=now_sp, nullable=False)

    offers = relationship("Offer", back_populates="product", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="product", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="product", cascade="all, delete-orphan")
    predictions = relationship("PredictionResult", back_populates="product", cascade="all, delete-orphan")


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    website_url = Column(String(255), nullable=False)
    store_type = Column(String(40), nullable=False, default="RETAILER")  # RETAILER ou COMMUNITY_FEED
    connector_type = Column(String(60), nullable=False, default="PUBLIC_API")
    reputation_score = Column(Float, nullable=False, default=90.0)  # 0 a 100
    default_shipping_estimate = Column(Float, nullable=False, default=0.0)
    is_enabled = Column(Boolean, default=True, nullable=False)
    status = Column(String(40), nullable=False, default="IDLE")
    # Status: ONLINE, UNAVAILABLE, BLOCKED_ANTIBOT, NEEDS_CREDENTIALS, ERROR, IDLE
    status_message = Column(Text, nullable=True)
    integration_docs = Column(Text, nullable=True)
    last_check_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)

    offers = relationship("Offer", back_populates="store", cascade="all, delete-orphan")
    price_history = relationship("PriceHistory", back_populates="store", cascade="all, delete-orphan")
    monitoring_logs = relationship("MonitoringLog", back_populates="store", cascade="all, delete-orphan")
    coupons = relationship("Coupon", back_populates="store", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="store")


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("store_id", "external_id", name="uq_offer_store_external"),
        Index("ix_offers_product_final_price", "product_id", "final_price"),
        Index("ix_offers_opportunity_score", "opportunity_score"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id = Column(String(180), nullable=False)
    title = Column(String(350), nullable=False)
    url = Column(String(700), nullable=False)
    image_url = Column(String(500), nullable=True)

    # Preços e Condições
    price_cash = Column(Float, nullable=False)  # Preço à vista / PIX
    price_card = Column(Float, nullable=True)  # Preço parcelado no cartão
    original_declared_price = Column(Float, nullable=True)  # Preço "De:" informado pela loja
    shipping_cost = Column(Float, nullable=False, default=0.0)
    coupon_code = Column(String(80), nullable=True)
    coupon_discount = Column(Float, nullable=False, default=0.0)
    final_price = Column(Float, nullable=False, index=True)  # Preço final considerando frete e cupom
    previous_price = Column(Float, nullable=True)
    payment_condition = Column(String(120), nullable=False, default="PIX / À vista")
    installments_text = Column(String(120), nullable=True)

    # Atributos de Qualidade / Vendedor / Garantia (Seção 2)
    seller_name = Column(String(150), nullable=False, default="Loja Oficial")
    is_marketplace = Column(Boolean, default=False, nullable=False)
    is_national = Column(Boolean, default=True, nullable=False)
    has_official_warranty = Column(Boolean, default=True, nullable=False)
    model_revision_detected = Column(String(60), nullable=True)
    in_stock = Column(Boolean, default=True, nullable=False)
    data_origin = Column(String(80), nullable=False, default="PUBLIC_API")

    # Inteligência do Radar e Detecção de Falso Desconto (Seções 7 e 10)
    opportunity_score = Column(Integer, nullable=False, default=50)  # 0 a 100
    opportunity_level = Column(String(60), nullable=False, default="Preço interessante, mas pode melhorar")
    opportunity_reason = Column(Text, nullable=True)
    reliability_score = Column(Integer, nullable=False, default=85)  # 0 a 100
    reliability_label = Column(String(60), nullable=False, default="Alta Confiabilidade")
    is_fake_discount = Column(Boolean, default=False, nullable=False)
    fake_discount_reason = Column(Text, nullable=True)
    declared_discount_pct = Column(Float, nullable=True)
    real_discount_vs_avg_pct = Column(Float, nullable=True)

    first_seen_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)
    last_checked_at = Column(DateTime(timezone=True), default=now_sp, nullable=False, index=True)

    product = relationship("Product", back_populates="offers")
    store = relationship("Store", back_populates="offers")
    price_history = relationship("PriceHistory", back_populates="offer", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="offer")


class PriceHistory(Base):
    __tablename__ = "price_history"
    __table_args__ = (
        Index("ix_price_history_product_recorded", "product_id", "recorded_at"),
        Index("ix_price_history_offer_recorded", "offer_id", "recorded_at"),
        Index("ix_price_history_store_recorded", "store_id", "recorded_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="SET NULL"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)

    price_found = Column(Float, nullable=False)  # Preço base à vista / PIX
    price_card = Column(Float, nullable=True)
    previous_price = Column(Float, nullable=True)
    shipping_cost = Column(Float, nullable=False, default=0.0)
    coupon_discount = Column(Float, nullable=False, default=0.0)
    final_price = Column(Float, nullable=False)
    payment_condition = Column(String(120), nullable=False, default="PIX")
    coupon_code = Column(String(80), nullable=True)
    is_promotional = Column(Boolean, default=False, nullable=False)
    in_stock = Column(Boolean, default=True, nullable=False)
    seller_name = Column(String(150), nullable=False, default="Loja Oficial")
    offer_url = Column(String(700), nullable=False)
    data_origin = Column(String(80), nullable=False, default="PUBLIC_API")
    recorded_at = Column(DateTime(timezone=True), default=now_sp, nullable=False, index=True)

    offer = relationship("Offer", back_populates="price_history")
    product = relationship("Product", back_populates="price_history")
    store = relationship("Store", back_populates="price_history")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_created", "is_archived", "is_read", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="SET NULL"), nullable=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True)

    alert_type = Column(String(60), nullable=False, index=True)
    # Tipos: OPPORTUNITY_EXCEPTIONAL, OPPORTUNITY_EXCELLENT, HISTORICAL_LOW, PRICE_DROP, FAKE_DISCOUNT, TARGET_PRICE_REACHED
    severity = Column(String(30), nullable=False, default="INFO")  # HIGH, SUCCESS, WARNING, DANGER, INFO
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    price = Column(Float, nullable=False)
    historical_comparison = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    offer_url = Column(String(700), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=now_sp, nullable=False, index=True)

    product = relationship("Product", back_populates="alerts")
    offer = relationship("Offer", back_populates="alerts")
    store = relationship("Store", back_populates="alerts")


class MonitoringLog(Base):
    __tablename__ = "monitoring_logs"
    __table_args__ = (
        Index("ix_monitoring_logs_store_started", "store_id", "started_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=True, index=True)
    store_name = Column(String(120), nullable=False)
    status = Column(String(40), nullable=False)  # SUCCESS, UNAVAILABLE, ERROR, PARTIAL
    offers_found = Column(Integer, default=0, nullable=False)
    offers_updated = Column(Integer, default=0, nullable=False)
    history_entries_created = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime(timezone=True), default=now_sp, nullable=False, index=True)
    finished_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)

    store = relationship("Store", back_populates="monitoring_logs")


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(80), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    discount_type = Column(String(20), nullable=False, default="PERCENT")  # PERCENT ou FIXED
    discount_value = Column(Float, nullable=False, default=0.0)
    min_order_value = Column(Float, nullable=True)
    max_discount_value = Column(Float, nullable=True)
    applicable_category = Column(String(50), nullable=True)  # PS5, DUALSENSE, ALL
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    source_url = Column(String(500), nullable=True)
    discovered_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    store = relationship("Store", back_populates="coupons")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    # Configuração PS5 Slim Digital
    ps5_target_price = Column(Float, nullable=True)
    ps5_excellent_price = Column(Float, nullable=True)
    ps5_payment_preference = Column(String(40), nullable=False, default="ANY")  # PIX, CARD, ANY
    ps5_preferred_stores = Column(Text, nullable=False, default="[]")  # JSON array de store slugs
    ps5_include_bundles = Column(Boolean, default=True, nullable=False)

    # Configuração DualSense
    dualsense_target_price = Column(Float, nullable=True)
    dualsense_excellent_price = Column(Float, nullable=True)
    dualsense_desired_colors = Column(Text, nullable=False, default='["Branco", "Preto", "Midnight Black", "Cosmic Red", "Starlight Blue", "Galactic Purple", "Grey Camouflage", "Cobalt Blue", "Volcanic Red", "Sterling Silver", "Chroma"]')
    dualsense_preferred_stores = Column(Text, nullable=False, default="[]")

    # Configuração do Agendador, Modo de Evento e Notificações
    scheduler_mode = Column(String(30), nullable=False, default="AUTO_EVENT")  # AUTO_EVENT, NORMAL, HIGH_ACTIVITY, NIGHT
    interval_normal_minutes = Column(Integer, nullable=False, default=30)
    interval_warmup_minutes = Column(Integer, nullable=False, default=15)
    interval_high_minutes = Column(Integer, nullable=False, default=10)
    interval_night_minutes = Column(Integer, nullable=False, default=60)
    event_mode_enabled = Column(Boolean, default=True, nullable=False)
    event_lead_days = Column(Integer, nullable=False, default=7)
    prioritize_ps5_in_event = Column(Boolean, default=True, nullable=False)
    custom_events_json = Column(Text, nullable=True)
    stale_data_threshold_minutes = Column(Integer, nullable=False, default=90)
    browser_notifications_enabled = Column(Boolean, default=False, nullable=False)
    only_official_warranty = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=now_sp, onupdate=now_sp, nullable=False)


class PredictionResult(Base):
    __tablename__ = "prediction_results"
    __table_args__ = (
        Index("ix_predictions_product_created", "product_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    horizon_hours = Column(Integer, nullable=False)  # 24, 72 (3d), 168 (7d)
    horizon_label = Column(String(40), nullable=False)  # "Próximas 24 horas", "Próximos 3 dias", "Próximos 7 dias"
    trend = Column(String(40), nullable=False)  # QUEDA, AUMENTO, ESTABILIDADE, DADOS_INSUFICIENTES
    estimated_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    moving_avg_7d = Column(Float, nullable=True)
    moving_avg_30d = Column(Float, nullable=True)
    slope_per_day = Column(Float, nullable=True)
    volatility_pct = Column(Float, nullable=True)
    confidence_pct = Column(Float, nullable=False, default=0.0)
    is_reliable = Column(Boolean, default=False, nullable=False)
    data_points_used = Column(Integer, nullable=False, default=0)
    methodology = Column(String(120), nullable=False, default="Média Móvel Ponderada + Regressão Linear Simples")
    explanation = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now_sp, nullable=False)

    product = relationship("Product", back_populates="predictions")
