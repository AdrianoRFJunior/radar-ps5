"""
Estrutura base para cada módulo de coleta de loja/fonte do RADAR BF 2026.
Cumpre estritamente as Seções 3, 17 e 19:
- Cada fonte possui seu próprio módulo independente.
- Nunca inventa preços.
- Nunca tenta contornar CAPTCHAs, bloqueios ou autenticação forçada.
- Informa claramente quando uma fonte está indisponível ou requer credenciais de API.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import os
import httpx


@dataclass
class CollectedOfferDTO:
    external_id: str
    title: str
    url: str
    price_cash: float
    price_card: Optional[float] = None
    original_declared_price: Optional[float] = None
    shipping_cost: float = 0.0
    coupon_code: Optional[str] = None
    coupon_discount: float = 0.0
    payment_condition: str = "PIX / À vista"
    installments_text: Optional[str] = None
    seller_name: str = "Loja Oficial"
    is_marketplace: bool = False
    in_stock: bool = True
    image_url: Optional[str] = None
    data_origin: str = "PUBLIC_API"


@dataclass
class CollectorResult:
    store_slug: str
    store_name: str
    status: str  # "ONLINE", "UNAVAILABLE", "NEEDS_CREDENTIALS", "BLOCKED_ANTIBOT", "ERROR"
    status_message: str
    offers: List[CollectedOfferDTO] = field(default_factory=list)
    integration_docs: str = ""


class BaseStoreCollector(ABC):
    store_slug: str = ""
    store_name: str = ""
    website_url: str = ""
    store_type: str = "RETAILER"
    connector_type: str = "PUBLIC_API"
    reputation_score: float = 90.0
    default_shipping_estimate: float = 0.0
    integration_docs: str = ""

    def __init__(self):
        self.timeout = float(os.getenv("COLLECTOR_TIMEOUT_SECONDS", "12"))
        self.user_agent = os.getenv(
            "USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )

    def get_http_headers(self) -> dict:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }

    @abstractmethod
    async def collect(self) -> CollectorResult:
        """Executa a coleta respeitando os limites e termos da plataforma."""
        raise NotImplementedError
