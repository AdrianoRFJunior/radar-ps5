"""
Módulo de coleta oficial para o Mercado Livre Brasil.
Utiliza a API Pública Oficial do Mercado Livre (https://api.mercadolibre.com/sites/MLB/search)
e suporta token OAuth opcional via variável de ambiente MERCADOLIVRE_ACCESS_TOKEN.
"""
import os
import re
import httpx
from bs4 import BeautifulSoup
from backend.collectors.base import BaseStoreCollector, CollectorResult, CollectedOfferDTO


class MercadoLivreCollector(BaseStoreCollector):
    store_slug = "mercado-livre"
    store_name = "Mercado Livre"
    website_url = "https://www.mercadolivre.com.br"
    store_type = "RETAILER"
    connector_type = "PUBLIC_API"
    reputation_score = 93.0
    default_shipping_estimate = 0.0
    integration_docs = (
        "Conector utiliza a API Pública REST do Mercado Livre (sites/MLB/search) e páginas públicas de listagem "
        "oficial. Para limites ampliados, configure MERCADOLIVRE_ACCESS_TOKEN no arquivo .env."
    )

    SEARCH_QUERIES = [
        "Console PlayStation 5 Slim Digital 1TB",
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

            # 2. Caso a API pública retorne 403 por política sem token, consultar página pública de listagem (sem burlar bloqueios)
            if not offers:
                public_urls = [
                    "https://lista.mercadolivre.com.br/console-playstation-5-slim-digital",
                    "https://lista.mercadolivre.com.br/controle-sony-dualsense-ps5",
                ]
                for pub_url in public_urls:
                    try:
                        resp = await client.get(pub_url)
                        if resp.status_code == 200 and "ui-search-layout__item" in resp.text:
                            soup = BeautifulSoup(resp.text, "html.parser")
                            cards = soup.select(".ui-search-layout__item")[:10]
                            for card in cards:
                                title_el = card.select_one(".poly-component__title, .ui-search-item__title")
                                link_el = card.select_one("a.poly-component__title, a.ui-search-link")
                                price_el = card.select_one(".andes-money-amount__fraction")
                                if not title_el or not price_el:
                                    continue
                                title_txt = title_el.get_text(strip=True)
                                raw_price = price_el.get_text(strip=True).replace(".", "").replace(",", ".")
                                try:
                                    price_val = float(raw_price)
                                except ValueError:
                                    continue
                                href = link_el.get("href", pub_url) if link_el else pub_url
                                mlb_match = re.search(r"(MLB-?\d+)", href)
                                ext_id = mlb_match.group(1).replace("-", "") if mlb_match else f"MLB-{ abs(hash(href)) % 10000000 }"
                                if ext_id in seen_ids:
                                    continue
                                seen_ids.add(ext_id)
                                img_el = card.select_one("img")
                                img_url = img_el.get("data-src") or img_el.get("src") if img_el else None

                                offers.append(
                                    CollectedOfferDTO(
                                        external_id=ext_id,
                                        title=title_txt,
                                        url=href.split("#")[0],
                                        price_cash=round(price_val, 2),
                                        price_card=round(price_val, 2),
                                        shipping_cost=0.0,
                                        payment_condition="PIX / À vista",
                                        seller_name="Mercado Livre Oficial / Loja Verificada",
                                        is_marketplace=False,
                                        in_stock=True,
                                        image_url=img_url,
                                        data_origin="MERCADOLIVRE_PUBLIC_CATALOG",
                                    )
                                )
                    except Exception as exc:
                        api_errors.append(str(exc))

        if offers:
            return CollectorResult(
                store_slug=self.store_slug,
                store_name=self.store_name,
                status="ONLINE",
                status_message=f"Coleta pública concluída com sucesso ({len(offers)} ofertas encontradas).",
                offers=offers,
                integration_docs=self.integration_docs,
            )

        return CollectorResult(
            store_slug=self.store_slug,
            store_name=self.store_name,
            status="NEEDS_CREDENTIALS" if any("403" in e or "401" in e for e in api_errors) else "UNAVAILABLE",
            status_message=(
                "A API do Mercado Livre exigiu autenticação OAuth neste IP ou não retornou ofertas públicas. "
                "Configure MERCADOLIVRE_ACCESS_TOKEN no .env para consulta autenticada."
            ),
            offers=[],
            integration_docs=self.integration_docs,
        )
