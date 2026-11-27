"""
Registro central de todos os módulos de coleta (Modo Intensivo Black Friday 2026).
Cobre mais de 20 varejistas confiáveis e radares de ofertas relâmpago para produtos 100% NOVOS:
Mercado Livre, Amazon Brasil, KaBuM!, Magazine Luiza, Shopee Oficial, Fast Shop, Carrefour,
Havan, Kalunga, Rede Varejistas VTEX (Bemol, Benoit, Angeloni, iByte, Fujioka, Webcontinental, Solar),
Casas Bahia, Ponto, Americanas, Extra, Submarino, Girafa, Webfones e Radar Promobit.
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
    ShopeeOficialCollector,
    HavanCollector,
    KalungaCollector,
    VtexRetailNetworkCollector,
    ExtraSubmarinoGirafaCollector,
)
from backend.collectors.community_sources import PromobitCollector


def get_all_collectors() -> List[BaseStoreCollector]:
    """Retorna todas as instâncias de coleta de lojas confiáveis para varredura paralela Black Friday."""
    return [
        PromobitCollector(),
        MercadoLivreCollector(),
        AmazonBrasilCollector(),
        KabumCollector(),
        MagazineLuizaCollector(),
        ShopeeOficialCollector(),
        FastShopCollector(),
        CarrefourCollector(),
        HavanCollector(),
        KalungaCollector(),
        VtexRetailNetworkCollector(),
        CasasBahiaCollector(),
        PontoCollector(),
        AmericanasCollector(),
        ExtraSubmarinoGirafaCollector(),
    ]


def get_collector_by_slug(slug: str) -> BaseStoreCollector | None:
    mapping: Dict[str, BaseStoreCollector] = {c.store_slug: c for c in get_all_collectors()}
    return mapping.get(slug)
