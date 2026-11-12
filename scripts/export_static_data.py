"""
Exporta todos os dados do RADAR BF 2026 em arquivos JSON estáticos dentro de frontend/public/data/
e frontend/dist/data/ para que o painel publicado no GitHub Pages e o frontend local funcionem 24/7.
Executa a busca em tempo real sem banco de dados retendo preços passados.
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.services.price_finder import find_and_save_best_prices  # noqa: E402


async def export_all(run_scan: bool = True) -> None:
    print("[export_static_data] Executando varredura e auditoria ao vivo de precos...")
    dash = await find_and_save_best_prices()
    count = dash.get("indicators", {}).get("offers_identified_count", 0)
    lowest_ps5 = dash.get("indicators", {}).get("lowest_ps5_price", 0)
    lowest_ds = dash.get("indicators", {}).get("lowest_dualsense_price", 0)
    print(f"[export_static_data] Sucesso: {count} ofertas identificadas. Menor PS5: R$ {lowest_ps5:.2f} | Menor DualSense: R$ {lowest_ds:.2f}")


if __name__ == "__main__":
    asyncio.run(export_all(run_scan=True))
