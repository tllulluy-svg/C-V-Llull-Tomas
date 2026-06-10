import re


def convertir_monto(texto):
    """Convierte texto de monto argentino a float. Ej: '1.234,56' → 1234.56"""
    if not texto:
        return 0.0
    try:
        texto = str(texto).strip()
        negativo = texto.startswith("-") or texto.startswith("(")
        texto = texto.lstrip("-(").rstrip(")")
        texto = texto.replace(".", "").replace(",", ".")
        texto = re.sub(r"[^\d.]", "", texto)
        valor = float(texto)
        return -valor if negativo else valor
    except (ValueError, AttributeError):
        return 0.0


def normalizar_texto(texto):
    """Convierte a minúsculas, elimina espacios dobles y normaliza caracteres especiales."""
    if not texto:
        return ""
    texto = texto.lower()
    reemplazos = {
        "°": "o", "º": "o", "ª": "a",
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u",
        "ñ": "n", "\t": " ", "\r": " ",
    }
    for orig, reempl in reemplazos.items():
        texto = texto.replace(orig, reempl)
    texto = re.sub(r" {2,}", " ", texto)
    return texto.strip()


def _patron_a_regex(patron_norm: str) -> str:
    """
    Convierte un patrón (con soporte para '|' como OR) en una expresión regex.
    Ej: 'arancel tj.|arancel credito' → busca cualquiera de las alternativas.
    Los espacios internos de cada alternativa se vuelven \\s+ para ser flexibles.
    """
    alternativas = [p.strip() for p in patron_norm.split("|") if p.strip()]
    partes_regex = []
    for alt in alternativas:
        flexible = r"\s+".join(re.escape(word) for word in alt.split())
        partes_regex.append(flexible)
    return "(?:" + "|".join(partes_regex) + ")"


def extraer_monto_regex(texto: str, patron: str) -> float:
    """
    Busca el patrón en el texto y retorna el primer monto encontrado en la misma línea.
    El patrón puede contener '|' para indicar alternativas (OR).
    Retorna 0.0 si no encuentra nada.
    """
    texto_norm = normalizar_texto(texto)
    patron_norm = normalizar_texto(patron)
    regex_patron = _patron_a_regex(patron_norm)
    regex = rf"{regex_patron}[^\n]*([\-\(]?\s*\d[\d.,]*)"
    match = re.search(regex, texto_norm, re.IGNORECASE)
    if match:
        return convertir_monto(match.group(1))
    return 0.0


def extraer_todos_montos_regex(texto: str, patron: str) -> list:
    """
    Igual que extraer_monto_regex pero retorna lista de todos los montos encontrados.
    El patrón puede contener '|' para alternativas.
    """
    texto_norm = normalizar_texto(texto)
    patron_norm = normalizar_texto(patron)
    regex_patron = _patron_a_regex(patron_norm)
    regex = rf"{regex_patron}[^\n]*([\-\(]?\s*\d[\d.,]*)"
    matches = re.findall(regex, texto_norm, re.IGNORECASE)
    return [convertir_monto(m) for m in matches]
