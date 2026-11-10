"""
Registro central de todos os módulos de coleta (Seção 3).
Focado em lojas varejistas confiáveis de produtos NOVOS (sem Mercado Livre, conforme solicitado pelo usuário).
"""
from typing import Dict, List
from backend.collectors.base import BaseStoreCollector
from backend.collectors.retail_stores import (
    AmazonBrasilCollector,
    KabumCollector,
    MagazineLuizaCollector,
    FastShopCollector,
    CasasBahiaCollector,
    PontoCollector,
    CarrefourCollector,
)
from backend.collectors.community_sources import PromobitCollector, PelandoCollector


def get_all_collectors() -> List[BaseStoreCollector]:
    """Retorna instâncias dos módulos de coleta de lojas confiáveis para produtos novos."""
    return [
        KabumCollector(),
        MagazineLuizaCollector(),
        AmazonBrasilCollector(),
        FastShopCollector(),
        CasasBahiaCollector(),
        PontoCollector(),
        CarrefourCollector(),
        PromobitCollector(),
        PelandoCollector(),
    ]


def get_collector_by_slug(slug: str) -> BaseStoreCollector | None:
    mapping: Dict[str, BaseStoreCollector] = {c.store_slug: c for c in get_all_collectors()}
    return mapping.get(slug)
