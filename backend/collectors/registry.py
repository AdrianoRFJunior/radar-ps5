"""
Registro central de todos os módulos de coleta (Seção 3).
Focado em lojas varejistas confiáveis e vendedores verificados de produtos NOVOS (incluindo Mercado Livre, Amazon, KaBuM!, Magalu, Fast Shop, Carrefour, Casas Bahia, Ponto e Promobit).
"""
from typing import Dict, List
from backend.collectors.base import BaseStoreCollector
from backend.collectors.mercadolivre import MercadoLivreCollector
from backend.collectors.retail_stores import (
    AmazonBrasilCollector,
    KabumCollector,
    MagazineLuizaCollector,
    FastShopCollector,
    CasasBahiaCollector,
    PontoCollector,
    CarrefourCollector,
    AmericanasCollector,
)
from backend.collectors.community_sources import PromobitCollector, PelandoCollector


def get_all_collectors() -> List[BaseStoreCollector]:
    """Retorna instâncias dos módulos de coleta de lojas confiáveis para produtos novos."""
    return [
        MercadoLivreCollector(),
        KabumCollector(),
        MagazineLuizaCollector(),
        AmazonBrasilCollector(),
        FastShopCollector(),
        CarrefourCollector(),
        AmericanasCollector(),
        CasasBahiaCollector(),
        PontoCollector(),
        PromobitCollector(),
        PelandoCollector(),
    ]


def get_collector_by_slug(slug: str) -> BaseStoreCollector | None:
    mapping: Dict[str, BaseStoreCollector] = {c.store_slug: c for c in get_all_collectors()}
    return mapping.get(slug)
