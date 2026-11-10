"""
Módulos de coleta independentes para as comunidades de ofertas:
- Promobit (promobit.com.br)
- Pelando (pelando.com.br)
"""
import json
import re
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO


class PromobitCollector(BaseStoreCollector):
    store_slug = "promobit"
    store_name = "Promobit"
    website_url = "https://www.promobit.com.br"
    store_type = "COMMUNITY_FEED"
    connector_type = "PUBLIC_FEED"
    reputation_score = 91.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta ofertas públicas moderadas pela comunidade Promobit via JSON-LD / NextData público. "
        "Respeita estritamente limites de requisição e não contorna proteções."
    )

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.promobit.com.br/buscar?q=ps5+slim+digital",
            "https://www.promobit.com.br/buscar?q=dualsense",
        ]
        errors = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        errors.append(f"HTTP {resp.status_code}")
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # Verificar __NEXT_DATA__ ou JSON-LD público se disponível
                    next_data = soup.find("script", id="__NEXT_DATA__")
                    if next_data and next_data.string:
                        data = json.loads(next_data.string)
                        raw_offers = (
                            data.get("props", {})
                            .get("pageProps", {})
                            .get("offers", [])
                        )
                        for item in raw_offers[:10]:
                            price = float(item.get("offer_price") or item.get("price") or 0)
                            if price <= 0:
                                continue
                            ext_id = f"PROMOBIT-{item.get('id', abs(hash(item.get('offer_title', ''))))}"
                            slug = item.get("offer_slug") or ""
                            offer_url = f"https://www.promobit.com.br/oferta/{slug}" if slug else self.website_url
                            coupon = item.get("offer_coupon")
                            store_origin = item.get("store_name") or "Comunidade Promobit"
                            offers.append(
                                CollectedOfferDTO(
                                    external_id=ext_id,
                                    title=item.get("offer_title") or item.get("title", ""),
                                    url=offer_url,
                                    price_cash=round(price, 2),
                                    original_declared_price=float(item.get("offer_old_price")) if item.get("offer_old_price") else None,
                                    coupon_code=coupon,
                                    payment_condition="PIX / Promoção Comunidade",
                                    seller_name=f"Promobit ({store_origin})",
                                    is_marketplace=False,
                                    in_stock=True,
                                    image_url=item.get("offer_photo"),
                                    data_origin="PROMOBIT_PUBLIC_FEED",
                                )
                            )
                except Exception as exc:
                    errors.append(str(exc))

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Feed Promobit consultado com sucesso ({len(offers)} ofertas ativas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message=(
                "Feed público do Promobit não retornou ofertas estruturadas na página inicial ou está protegido por "
                "renderização dinâmica/Cloudflare no momento."
            ),
            offers=[],
            integration_docs=self.integration_docs,
        )


class PelandoCollector(BaseStoreCollector):
    store_slug = "pelando"
    store_name = "Pelando"
    website_url = "https://www.pelando.com.br"
    store_type = "COMMUNITY_FEED"
    connector_type = "PUBLIC_FEED"
    reputation_score = 90.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Consulta o feed público de promoções do Pelando via dados estruturados públicos (__NEXT_DATA__ / JSON-LD). "
        "Respeita rate-limiting e políticas anti-bot."
    )

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        urls = [
            "https://www.pelando.com.br/busca?q=ps5+slim+digital",
            "https://www.pelando.com.br/busca?q=dualsense",
        ]
        errors = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.get_http_headers()) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        errors.append(f"HTTP {resp.status_code}")
                        continue
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for ld in soup.find_all("script", type="application/ld+json"):
                        if not ld.string:
                            continue
                        try:
                            parsed = json.loads(ld.string)
                            items = parsed if isinstance(parsed, list) else [parsed]
                            for obj in items:
                                if obj.get("@type") == "Product":
                                    offer_node = obj.get("offers", {})
                                    price = float(offer_node.get("price") or 0)
                                    if price > 0:
                                        offers.append(
                                            CollectedOfferDTO(
                                                external_id=f"PELANDO-{abs(hash(obj.get('name', '')))}",
                                                title=obj.get("name", ""),
                                                url=offer_node.get("url") or self.website_url,
                                                price_cash=round(price, 2),
                                                payment_condition="Oferta Pelando",
                                                seller_name="Comunidade Pelando",
                                                in_stock=True,
                                                data_origin="PELANDO_JSONLD",
                                            )
                                        )
                        except Exception:
                            continue
                except Exception as exc:
                    errors.append(str(exc))

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Feed Pelando consultado ({len(offers)} promoções identificadas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="UNAVAILABLE",
            status_message=(
                "O Pelando utiliza proteção GraphQL/Cloudflare nas buscas diretas. Nenhuma promoção pública "
                "em JSON-LD retornada sem autenticação."
            ),
            offers=[],
            integration_docs=self.integration_docs,
        )
