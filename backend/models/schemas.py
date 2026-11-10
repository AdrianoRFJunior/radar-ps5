"""
Schemas Pydantic para validação rigorosa de entrada e saída de dados da API,
incluindo configuração do MODO DE EVENTO e calendário promocional.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PromotionalEventSchema(BaseModel):
    slug: str
    name: str
    start_date: str
    end_date: str
    description: Optional[str] = ""
    expand_coupon_search: bool = True
    recommended_interval_minutes: int = Field(default=10, ge=5, le=1440)


class SettingUpdateSchema(BaseModel):
    ps5_target_price: Optional[float] = Field(default=None, ge=0)
    ps5_excellent_price: Optional[float] = Field(default=None, ge=0)
    ps5_payment_preference: str = Field(default="ANY")
    ps5_preferred_stores: List[str] = Field(default_factory=list)
    ps5_include_bundles: bool = Field(default=True)

    dualsense_target_price: Optional[float] = Field(default=None, ge=0)
    dualsense_excellent_price: Optional[float] = Field(default=None, ge=0)
    dualsense_desired_colors: List[str] = Field(default_factory=list)
    dualsense_preferred_stores: List[str] = Field(default_factory=list)

    scheduler_mode: str = Field(default="AUTO_EVENT")
    interval_normal_minutes: int = Field(default=30, ge=1, le=1440)
    interval_warmup_minutes: int = Field(default=15, ge=1, le=1440)
    interval_high_minutes: int = Field(default=10, ge=1, le=1440)
    interval_night_minutes: int = Field(default=60, ge=5, le=1440)

    event_mode_enabled: bool = Field(default=True)
    event_lead_days: int = Field(default=7, ge=1, le=60)
    prioritize_ps5_in_event: bool = Field(default=True)
    stale_data_threshold_minutes: int = Field(default=90, ge=15, le=1440)
    promotional_events: Optional[List[PromotionalEventSchema]] = None

    browser_notifications_enabled: bool = Field(default=False)
    only_official_warranty: bool = Field(default=False)


class CouponCreateSchema(BaseModel):
    store_slug: str
    code: str
    description: str
    discount_type: str = "PERCENT"
    discount_value: float = Field(gt=0)
    min_order_value: Optional[float] = None
    max_discount_value: Optional[float] = None
    applicable_category: str = "ALL"


class ManualOfferInputSchema(BaseModel):
    store_slug: str
    title: str
    url: str
    price_cash: float = Field(gt=0)
    price_card: Optional[float] = None
    original_declared_price: Optional[float] = None
    shipping_cost: float = Field(default=0.0, ge=0)
    coupon_code: Optional[str] = None
    coupon_discount: float = Field(default=0.0, ge=0)
    payment_condition: str = "PIX / À vista"
    seller_name: str = "Loja Oficial"
    is_marketplace: bool = False
    is_national: bool = True
    has_official_warranty: bool = True
