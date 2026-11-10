"""
Classificador inteligente de ofertas de PlayStation 5 Novo e Controle DualSense Oficial.
Regras principais solicitadas pelo usuário:
- Apenas produtos NOVOS (exclui usados, seminovos, recondicionados, open box ou vitrine).
- Monitorar como prioritários tanto o PS5 Slim Digital (sem leitor) quanto o PS5 Slim com Leitor de Disco (mídia física) e seus bundles oficiais, identificando claramente cada versão.
- Diferenciar se é nacional (Anatel / garantia oficial Sony Brasil) ou importado (ex: UAE/KSA/Japão), e se é venda direta ou marketplace.
- Diferenciar DualSense oficial Sony de controles paralelos/similares.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassificationResult:
    is_relevant: bool
    category: str  # "PS5", "DUALSENSE", "IRRELEVANT"
    product_slug: str
    subcategory: str  # "MAIN", "DISC_EDITION", "BUNDLE_GAMES", "BUNDLE_CONTROLLER", "COLOR_VARIANT", "SPECIAL_EDITION", "ALTERNATIVE"
    edition_type: str  # "PS5 Slim Digital (Sem Leitor)", "PS5 Slim Com Leitor de Disco", etc.
    is_priority: bool  # True para PS5 Slim Novo (Digital ou Com Leitor de Disco) e DualSense Oficial Sony
    is_official: bool
    color: Optional[str]
    model_revision: Optional[str]
    is_national: bool
    has_official_warranty: bool
    rejection_or_alt_reason: Optional[str] = None


# Palavras que excluem completamente (acessórios, jogos avulsos, leitores avulsos E produtos usados/recondicionados/open box)
ACCESSORY_OR_USED_EXCLUSION_KEYWORDS = [
    "usado",
    "seminovo",
    "semi-novo",
    "semi novo",
    "recondicionado",
    "refurbished",
    "open box",
    "openbox",
    "vitrine",
    "mostruário",
    "mostruario",
    "caixa aberta",
    "com defeito",
    "no estado",
    "leitor de disco para",
    "unidade de disco para",
    "drive leitor de disco",
    "playstation portal",
    "reprodutor remoto",
    "controle access",
    "capa de silicone",
    "skin adesivo",
    "adesivo para",
    "suporte vertical",
    "suporte triplo",
    "base de resfriamento",
    "base de carregamento",
    "charging station",
    "cooler ventilador",
    "cabo usb",
    "grip analógico",
    "analogico dualsense",
    "analógico dualsense",
    "borrachinha",
    "maleta case",
    "estojo",
    "carcaça",
    "faceplate",
    "tampa lateral",
    "peça de reposição",
    "bateria para controle",
    "película",
    "headset",
    "pulse 3d",
    "pulse elite",
    "ps4",
    "playstation 4",
    "dualshock 4",
    "xbox",
    "nintendo switch",
    "aluguel",
    "conta primária",
    "mídia digital jogo",
    "gift card",
    "kit controle dual sense",
    "kit controle dualsense",
    "planos tim",
    "ultracombo",
    "ssd interno",
    "unidade interna",
    "nvme",
    "wd_black",
    "hd externo",
    "base carregadora",
]

PARALLEL_CONTROLLER_KEYWORDS = [
    "paralelo",
    "similar",
    "compatível com ps5",
    "compativel com ps5",
    "genérico",
    "generico",
    "tipo dualsense",
    "primeira linha",
    "réplica",
    "replica",
    "ipega",
    "qrd spark",
    "victrix",
    "razer wolverine",
    "nacon",
    "scuf",
]

DUALSENSE_COLORS = {
    "midnight black": "Midnight Black (Preto)",
    "preto": "Midnight Black (Preto)",
    "black": "Midnight Black (Preto)",
    "cosmic red": "Cosmic Red (Vermelho)",
    "starlight blue": "Starlight Blue (Azul)",
    "galactic purple": "Galactic Purple (Roxo)",
    "nova pink": "Nova Pink (Rosa)",
    "grey camouflage": "Grey Camouflage (Camuflado)",
    "gray camouflage": "Grey Camouflage (Camuflado)",
    "gray camuflado": "Grey Camouflage (Camuflado)",
    "camuflado": "Grey Camouflage (Camuflado)",
    "camouflage": "Grey Camouflage (Camuflado)",
    "cobalt blue": "Cobalt Blue (Azul Cobalto)",
    "volcanic red": "Volcanic Red (Vermelho Vulcânico)",
    "sterling silver": "Sterling Silver (Prata)",
    "chroma pearl": "Chroma Pearl",
    "chroma indigo": "Chroma Indigo",
    "chroma teal": "Chroma Teal",
    "branco": "Branco (Standard)",
    "white": "Branco (Standard)",
}

SPECIAL_EDITIONS = [
    "astro bot",
    "spider-man",
    "spider man",
    "god of war",
    "ragnarok",
    "hogwarts legacy",
    "lebron",
    "30th anniversary",
    "30 anos",
    "30º aniversário",
    "the last of us",
    "fortnite",
    "monster hunter",
    "concord",
    "helldivers",
    "wolverine",
    "ghost of yotei",
    "ghost of yōtei",
    "marathon",
    "hyperpop",
    "blackpink",
    "gran turismo",
]


def detect_revision(title: str) -> Optional[str]:
    """Extrai revisão CFI do título quando disponível."""
    match = re.search(r"(CFI-\d{4}[A-Z]?|CFI-ZCT[12][A-Z0-9]*)", title.upper())
    if match:
        return match.group(1)
    return None


def detect_nationality_and_warranty(title: str, seller_name: str = "") -> tuple[bool, bool]:
    """Avalia se o console/controle é nacional Anatel e com garantia oficial Sony Brasil."""
    t_lower = title.lower()
    is_imported = any(
        k in t_lower
        for k in [
            "importado",
            "versão japonesa",
            "versão europeia",
            "uae version",
            "ksa version",
            "uk version",
            "us version",
            "sem caixa",
        ]
    )
    is_national = not is_imported
    has_warranty = is_national and not any(k in t_lower for k in ["sem garantia", "90 dias de garantia"])
    return is_national, has_warranty


def classify_offer_title(title: str, price: float = 0.0, seller_name: str = "") -> ClassificationResult:
    """
    Classifica uma oferta em PS5 Novo (Slim Digital ou Slim com Leitor de Disco, Bundles ou Alternativos)
    ou DualSense Novo (Oficial ou Alternativo).
    """
    clean_title = title.strip()
    t_lower = clean_title.lower()

    # 1. Filtrar acessórios irrelevantes, jogos avulsos ou produtos USADOS/SEMINOVOS/OPEN BOX
    for kw in ACCESSORY_OR_USED_EXCLUSION_KEYWORDS:
        if kw in t_lower:
            return ClassificationResult(
                is_relevant=False,
                category="IRRELEVANT",
                product_slug="irrelevant",
                subcategory="IRRELEVANT",
                edition_type="Irrelevante ou Produto Usado/Acessório",
                is_priority=False,
                is_official=False,
                color=None,
                model_revision=None,
                is_national=False,
                has_official_warranty=False,
                rejection_or_alt_reason=f"Excluído por termo de acessório ou não-novo: {kw}",
            )

    revision = detect_revision(clean_title)
    is_national, has_warranty = detect_nationality_and_warranty(clean_title, seller_name)

    # 2. Verificar se é Controle DualSense (e não um Console PS5 que menciona DualSense ou Controle no título)
    is_console = any(
        k in t_lower
        for k in [
            "console",
            "825gb",
            "825 gb",
            "1tb",
            "1 tb",
            "2tb",
            "edição digital",
            "edicao digital",
            "digital edition",
            "playstation 5 slim",
            "playstation®5 slim",
            "playstation 5 standard",
            "playstation 5 disc",
            "playstation 5 digital",
            "ps5 slim",
            "ps5 pro",
            "playstation 5 pro",
            "ps5 digital",
            "ps5 físico",
            "ps5 fisico",
            "ps5 mídia física",
            "ps5 com leitor",
            "pacote astro bot",
        ]
    )

    if not is_console and ("dualsense" in t_lower or ("controle" in t_lower and ("ps5" in t_lower or "playstation 5" in t_lower))):
        # Validar faixa mínima de preço razoável para evitar capas/cabos/botões disfarçados
        if 0 < price < 200:
            return ClassificationResult(
                is_relevant=False,
                category="IRRELEVANT",
                product_slug="irrelevant",
                subcategory="IRRELEVANT",
                edition_type="Acessório abaixo do piso de controle",
                is_priority=False,
                is_official=False,
                color=None,
                model_revision=None,
                is_national=False,
                has_official_warranty=False,
                rejection_or_alt_reason="Preço incompatível com controle DualSense novo (< R$ 200)",
            )

        is_parallel = any(pk in t_lower for pk in PARALLEL_CONTROLLER_KEYWORDS)
        if "sony" not in t_lower and "dualsense" not in t_lower:
            is_parallel = True

        # Verificar DualSense Edge
        if "dualsense edge" in t_lower:
            return ClassificationResult(
                is_relevant=True,
                category="DUALSENSE",
                product_slug="dualsense-edge-alt",
                subcategory="ALTERNATIVE",
                edition_type="DualSense Edge (Pro)",
                is_priority=False,
                is_official=True,
                color="Branco/Preto",
                model_revision=revision or "CFI-ZCP1",
                is_national=is_national,
                has_official_warranty=has_warranty,
                rejection_or_alt_reason="Versão Pro (DualSense Edge) — classificada em oportunidades alternativas.",
            )

        if is_parallel:
            return ClassificationResult(
                is_relevant=True,
                category="DUALSENSE",
                product_slug="dualsense-parallel-alt",
                subcategory="ALTERNATIVE",
                edition_type="Controle Paralelo / Similar",
                is_priority=False,
                is_official=False,
                color="Variado",
                model_revision=revision,
                is_national=is_national,
                has_official_warranty=False,
                rejection_or_alt_reason="Controle paralelo/similar (não oficial Sony).",
            )

        # DualSense Oficial Sony
        detected_color = "Branco (Standard)"
        for key, label in DUALSENSE_COLORS.items():
            if key in t_lower:
                detected_color = label
                break

        is_special = any(se in t_lower for se in SPECIAL_EDITIONS) or "edição limitada" in t_lower or "limited edition" in t_lower
        if is_special:
            return ClassificationResult(
                is_relevant=True,
                category="DUALSENSE",
                product_slug="sony-dualsense-special",
                subcategory="SPECIAL_EDITION",
                edition_type="Edição Especial Oficial Sony",
                is_priority=True,
                is_official=True,
                color=detected_color,
                model_revision=revision or "CFI-ZCT1W",
                is_national=is_national,
                has_official_warranty=has_warranty,
            )

        subcat = "MAIN" if ("Branco" in detected_color or "Midnight Black" in detected_color) else "COLOR_VARIANT"
        slug = "sony-dualsense-branco" if "Branco" in detected_color else (
            "sony-dualsense-preto" if "Midnight Black" in detected_color else "sony-dualsense-cores"
        )
        return ClassificationResult(
            is_relevant=True,
            category="DUALSENSE",
            product_slug=slug,
            subcategory=subcat,
            edition_type="DualSense Oficial Sony",
            is_priority=True,
            is_official=True,
            color=detected_color,
            model_revision=revision or "CFI-ZCT1W",
            is_national=is_national,
            has_official_warranty=has_warranty,
        )

    # 3. Verificar se é Console PlayStation 5 Novo
    if is_console:
        if 0 < price < 2200:
            return ClassificationResult(
                is_relevant=False,
                category="IRRELEVANT",
                product_slug="irrelevant",
                subcategory="IRRELEVANT",
                edition_type="Valor incompatível com console PS5 novo",
                is_priority=False,
                is_official=False,
                color=None,
                model_revision=None,
                is_national=False,
                has_official_warranty=False,
                rejection_or_alt_reason="Preço abaixo de R$ 2.200 (provável acessório, peça ou golpe).",
            )

        # 3.1 Separar PS5 Pro (2TB) em Alternativas para não distorcer a busca pelo menor preço do PS5 Slim
        if "ps5 pro" in t_lower or "playstation 5 pro" in t_lower or "2tb" in t_lower:
            return ClassificationResult(
                is_relevant=True,
                category="PS5",
                product_slug="ps5-pro-alternative",
                subcategory="ALTERNATIVE",
                edition_type="PS5 Pro (2TB)",
                is_priority=False,
                is_official=True,
                color="Branco",
                model_revision=revision or "CFI-7014B",
                is_national=is_national,
                has_official_warranty=has_warranty,
                rejection_or_alt_reason="PS5 Pro 2TB — separado em alternativas para focar no menor preço do PS5 Slim.",
            )

        # 3.2 Incluir PS5 Standard/Fat (CFI-10xx / CFI-11xx / CFI-12xx) como prioritário também (apenas PS5 Pro fica de fora)
        is_slim_explicit = "slim" in t_lower or (revision is not None and (revision.startswith("CFI-20") or revision.startswith("CFI-21")))
        is_fat = (
            "ps5 fat" in t_lower
            or (revision is not None and (revision.startswith("CFI-10") or revision.startswith("CFI-11") or revision.startswith("CFI-12")))
        )
        if is_fat:
            return ClassificationResult(
                is_relevant=True,
                category="PS5",
                product_slug="ps5-fat-alternative",
                subcategory="DISC_EDITION",
                edition_type="PS5 Standard / Edição Padrão",
                is_priority=True,
                is_official=True,
                color="Branco",
                model_revision=revision or "CFI-1214",
                is_national=is_national,
                has_official_warranty=has_warranty,
            )

        # 3.3 Identificar se é Edição Digital (Sem Leitor) ou Com Leitor de Disco (Mídia Física)
        # Ambos são monitorados como PRIORITÁRIOS (is_priority=True) conforme pedido do usuário:
        # "sempre que ele achar um PlayStation 5 novo com preço ótimo, seja com leitor de disco ou sem, é legal que ele me mostre."
        has_disc_keywords = any(
            dk in t_lower
            for dk in [
                "com leitor",
                "leitor de disco",
                "leitor de discos",
                "mídia física",
                "midia fisica",
                "ps5 físico",
                "ps5 fisico",
                "disc edition",
                "disc console",
                "slim disk",
                "c/drive",
                "com drive",
                "edição com disco",
                "edicao com disco",
                "blu-ray",
                "blue ray",
                "bluray",
                "standard",
            ]
        )
        is_digital_explicit = any(
            dg in t_lower
            for dg in [
                "digital",
                "sem leitor",
                "cfi-2014b",
                "cfi-2114b",
                "cfi-2015b",
            ]
        )

        has_extra_controller = any(
            ck in t_lower
            for ck in ["2 controles", "dois controles", "controle adicional", "controle extra", "dual sense extra", "blue controller bundle"]
        )
        has_bundle_games = any(
            gk in t_lower
            for gk in [
                "returnal",
                "ratchet",
                "clank",
                "astro bot",
                "spider-man",
                "god of war",
                "gt7",
                "gran turismo",
                "2 jogos",
                "com jogos",
                "bundle",
                "pacote",
                "horizon",
                "call of duty",
                "wolverine",
                "fc 25",
                "fc 26",
            ]
        )

        # Caso A: PS5 Slim COM Leitor de Disco (ou quando não é explícito Digital)
        is_disc_version = (has_disc_keywords and not is_digital_explicit) or (
            revision is not None and revision.endswith("A") and (revision.startswith("CFI-20") or revision.startswith("CFI-21"))
        ) or (not is_digital_explicit)

        if is_disc_version:
            edition_label = (
                "PS5 Slim Com Leitor de Disco + Jogos"
                if has_bundle_games
                else "PS5 Slim Com Leitor de Disco (Mídia Física)"
            )
            return ClassificationResult(
                is_relevant=True,
                category="PS5",
                product_slug="ps5-slim-disc-main",
                subcategory="DISC_EDITION",
                edition_type=edition_label,
                is_priority=True,
                is_official=True,
                color="Branco",
                model_revision=revision or "CFI-2014A",
                is_national=is_national,
                has_official_warranty=has_warranty,
            )

        # Caso B: PS5 Slim Edição Digital (Sem Leitor)
        if has_extra_controller:
            return ClassificationResult(
                is_relevant=True,
                category="PS5",
                product_slug="ps5-slim-digital-bundle-controller",
                subcategory="BUNDLE_CONTROLLER",
                edition_type="PS5 Slim Digital (Sem Leitor) + Controle Extra",
                is_priority=True,
                is_official=True,
                color="Branco",
                model_revision=revision or "CFI-2014B",
                is_national=is_national,
                has_official_warranty=has_warranty,
            )

        if has_bundle_games:
            return ClassificationResult(
                is_relevant=True,
                category="PS5",
                product_slug="ps5-slim-digital-bundle-games",
                subcategory="BUNDLE_GAMES",
                edition_type="PS5 Slim Digital (Sem Leitor) + 2 Jogos",
                is_priority=True,
                is_official=True,
                color="Branco",
                model_revision=revision or "CFI-2014B",
                is_national=is_national,
                has_official_warranty=has_warranty,
            )

        return ClassificationResult(
            is_relevant=True,
            category="PS5",
            product_slug="ps5-slim-digital-main",
            subcategory="MAIN",
            edition_type="PS5 Slim Digital (Sem Leitor)",
            is_priority=True,
            is_official=True,
            color="Branco",
            model_revision=revision or "CFI-2014B",
            is_national=is_national,
            has_official_warranty=has_warranty,
        )

    return ClassificationResult(
        is_relevant=False,
        category="IRRELEVANT",
        product_slug="irrelevant",
        subcategory="IRRELEVANT",
        edition_type="Irrelevante",
        is_priority=False,
        is_official=False,
        color=None,
        model_revision=None,
        is_national=False,
        has_official_warranty=False,
        rejection_or_alt_reason="Título não corresponde a PS5 Novo nem a DualSense.",
    )
