import re


def convertir_monto(texto):
    """Convierte texto de monto argentino a float. Ej: '1.234,56' → 1234.56"""
    if not texto:
        return 0.0
    try:
        texto = str(texto).strip()
        # Eliminar signo negativo para procesarlo aparte
        negativo = texto.startswith("-") or texto.startswith("(")
        texto = texto.lstrip("-(").rstrip(")")
        # Eliminar puntos de miles y reemplazar coma decimal por punto
        texto = texto.replace(".", "").replace(",", ".")
        # Eliminar caracteres no numéricos salvo punto y signo
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
    # Reemplazar caracteres especiales comunes
    reemplazos = {
        "°": "o",
        "º": "o",
        "ª": "a",
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "\t": " ",
        "\r": " ",
    }
    for orig, reempl in reemplazos.items():
        texto = texto.replace(orig, reempl)
    # Eliminar espacios dobles
    texto = re.sub(r" {2,}", " ", texto)
    return texto.strip()


def extraer_monto_regex(texto, patron):
    """
    Busca el patrón en el texto normalizado y retorna el primer monto encontrado
    en la misma línea o línea siguiente. Retorna 0.0 si no encuentra.
    """
    texto_norm = normalizar_texto(texto)
    patron_norm = normalizar_texto(patron)
    # Patrón flexible: permite espacios variables entre palabras del patron
    patron_flexible = r"\s+".join(re.escape(p) for p in patron_norm.split())
    # Buscar patrón seguido de monto en la misma línea
    regex = rf"{patron_flexible}[^\n]*([\-\(]?\s*\d[\d.,]*)"
    match = re.search(regex, texto_norm, re.IGNORECASE)
    if match:
        return convertir_monto(match.group(1))
    return 0.0


def extraer_todos_montos_regex(texto, patron):
    """
    Igual que extraer_monto_regex pero retorna lista de todos los montos encontrados.
    Útil para Fiserv donde los descuentos se acumulan en múltiples bloques.
    """
    texto_norm = normalizar_texto(texto)
    patron_norm = normalizar_texto(patron)
    patron_flexible = r"\s+".join(re.escape(p) for p in patron_norm.split())
    regex = rf"{patron_flexible}[^\n]*([\-\(]?\s*\d[\d.,]*)"
    matches = re.findall(regex, texto_norm, re.IGNORECASE)
    return [convertir_monto(m) for m in matches]
