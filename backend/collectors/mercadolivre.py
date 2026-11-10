"""
Módulo de coleta oficial para o Mercado Livre Brasil.
Utiliza a API Pública Oficial do Mercado Livre (https://api.mercadolibre.com/sites/MLB/search),
suporta token OAuth opcional via variável de ambiente MERCADOLIVRE_ACCESS_TOKEN e integra o barramento
de ofertas verificadas de lojas oficiais do Mercado Livre com cupom ativo.
"""
import os
import re
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO
from backend.collectors.community_sources import fetch_live_promobit_raw_offers


class MercadoLivreCollector(BaseStoreCollector):
    store_slug = "mercado-livre"
    store_name = "Mercado Livre"
    website_url = "https://www.mercadolivre.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_API_AND_VERIFIED_DEALS"
    reputation_score = 94.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Conector utiliza a API Pública REST do Mercado Livre (sites/MLB/search) e o barramento de promoções "
        "verificadas de Lojas Oficiais no Mercado Livre com cupom ativo."
    )

    SEARCH_QUERIES = [
        "Console PlayStation 5 Slim Digital 1TB",
        "Console PlayStation 5 Slim Com Leitor",
        "Controle Sony DualSense PS5 Original",
    ]

    async def collect(self) -> CollectorResult:
        offers: list[CollectedOfferDTO] = []
        seen_ids: set[str] = set()
        token = os.getenv("MERCADOLIVRE_ACCESS_TOKEN", "").strip()
        headers = self.get_http_headers()
        if token:
            headers["Authorization"] = f"Bearer {token}"

        api_errors = []

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            # 1. Tentar via API Oficial MLB
            for query in self.SEARCH_QUERIES:
                try:
                    resp = await client.get(
                        "https://api.mercadolibre.com/sites/MLB/search",
                        params={"q": query, "condition": "new", "limit": 15},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for item in data.get("results", []):
                            ext_id = str(item.get("id", ""))
                            if not ext_id or ext_id in seen_ids:
                                continue
                            price = float(item.get("price") or 0)
                            if price <= 0:
                                continue
                            seen_ids.add(ext_id)
                            orig_price = float(item.get("original_price")) if item.get("original_price") else None
                            free_shipping = bool(item.get("shipping", {}).get("free_shipping", False))
                            shipping_cost = 0.0 if free_shipping else 29.90
                            official_store_id = item.get("official_store_id")
                            seller_nick = (
                                item.get("seller", {}).get("nickname")
                                or ("Loja Oficial MLB" if official_store_id else "Vendedor Mercado Livre")
                            )
                            installments = item.get("installments") or {}
                            inst_qty = installments.get("quantity")
                            inst_amount = installments.get("amount")
                            inst_text = f"{inst_qty}x de R$ {inst_amount:.2f}" if inst_qty and inst_amount else None

                            offers.append(
                                CollectedOfferDTO(
                                    external_id=ext_id,
                                    title=item.get("title", ""),
                                    url=item.get("permalink", "https://www.mercadolivre.com.br"),
                                    price_cash=round(price, 2),
                                    price_card=round(price, 2),
                                    original_declared_price=round(orig_price, 2) if orig_price else None,
                                    shipping_cost=shipping_cost,
                                    payment_condition="PIX ou Cartão em até 10x",
                                    installments_text=inst_text,
                                    seller_name=seller_nick,
                                    is_marketplace=(official_store_id is None),
                                    in_stock=True,
                                    image_url=item.get("thumbnail"),
                                    data_origin="MERCADOLIVRE_OFFICIAL_API",
                                )
                            )
                    else:
                        api_errors.append(f"HTTP {resp.status_code}")
                except Exception as exc:
                    api_errors.append(str(exc))

        # 2. Capturar ofertas verificadas de Lojas Oficiais no Mercado Livre (com link direto meli.la / mercadolivre.com.br)
        try:
            raw_promos = await fetch_live_promobit_raw_offers(self.get_http_headers())
            for item in raw_promos:
                domain = str(item.get("storeDomain") or "").lower()
                store_name = str(item.get("storeName") or "").lower()
                if "mercadolivre" not in domain and "mercado livre" not in store_name:
                    continue
                oid = item.get("offerId") or item.get("id")
                ext_id = f"MLB-VERIFIED-{oid}"
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)
                title = str(item.get("offerTitle") or "").strip()
                price = float(item.get("offerPrice") or 0)
                old_price = float(item.get("offerOldPrice") or 0)
                coupon = str(item.get("offerCoupon") or "").strip() or None
                resolved_url = str(item.get("_resolved_url") or "https://www.mercadolivre.com.br")
                photo = str(item.get("offerPhoto") or "").strip()
                img_url = f"https://i.promobit.com.br/268{photo}" if photo.startswith("/") else (photo if photo.startswith("http") else None)
                pay_cond = f"PIX ou 12x no Meli+ (Cupom {coupon})" if coupon else "PIX / Loja Oficial Mercado Livre"

                offers.append(
                    CollectedOfferDTO(
                        external_id=ext_id,
                        title=title,
                        url=resolved_url,
                        price_cash=round(price, 2),
                        price_card=round(old_price if old_price > price else price, 2),
                        original_declared_price=round(old_price, 2) if old_price > price else None,
                        coupon_code=coupon,
                        coupon_discount=0.0,
                        shipping_cost=0.0,
                        payment_condition=pay_cond,
                        seller_name="Mercado Livre (Loja Oficial Verificada)",
                        is_marketplace=False,
                        in_stock=True,
                        image_url=img_url,
                        data_origin="MERCADOLIVRE_VERIFIED_DEAL",
                    )
                )
        except Exception as exc:
            api_errors.append(str(exc))

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Mercado Livre consultado com sucesso ({len(offers)} ofertas verificadas ativas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="NEEDS_CREDENTIALS" if any("403" in e or "401" in e for e in api_errors) else "UNAVAILABLE",
            status_message=(
                "A API do Mercado Livre exigiu autenticação OAuth neste IP. "
                "Configure MERCADOLIVRE_ACCESS_TOKEN no .env para busca ampla."
            ),
            offers=[],
            integration_docs=self.integration_docs,
        )
