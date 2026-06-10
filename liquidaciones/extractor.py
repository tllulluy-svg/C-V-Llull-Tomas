"""
Lógica central de extracción. Orquesta la lectura de PDFs, identificación
de emisor, extracción de campos y validación de montos.
"""

import re
import pdfplumber
from utils import normalizar_texto, convertir_monto, extraer_monto_regex, extraer_todos_montos_regex


def _cargar_emisores():
    """Carga emisores desde DB si está disponible, sino usa el diccionario base."""
    try:
        from database import obtener_emisores
        db_emisores = obtener_emisores()
        if db_emisores:
            return db_emisores
    except Exception:
        pass
    from diccionario import EMISORES
    return EMISORES


def identificar_emisor(texto_completo: str) -> str:
    """
    Normaliza el texto y busca identificadores de cada emisor.
    Retorna el nombre del emisor o 'desconocido'.
    """
    texto_norm = normalizar_texto(texto_completo)
    emisores = _cargar_emisores()
    for nombre, config in emisores.items():
        for ident in config.get("identificadores", []):
            if normalizar_texto(ident) in texto_norm:
                return nombre
    return "desconocido"


def _extraer_valor_linea(texto_norm: str, patron: str) -> str:
    """Extrae el valor en la misma línea que el patrón, después del patrón."""
    patron_norm = normalizar_texto(patron)
    patron_flexible = r"\s*".join(re.escape(p) for p in patron_norm.split())
    regex = rf"{patron_flexible}[:\s]+(.+)"
    match = re.search(regex, texto_norm)
    if match:
        return match.group(1).strip()
    return ""


def extraer_encabezado(texto: str, emisor: str) -> dict:
    """
    Extrae razón social, CUIT, N° comercio, marca tarjeta,
    total presentado y neto usando el diccionario del emisor.
    """
    emisores = _cargar_emisores()
    config = emisores.get(emisor, {})
    campos = config.get("campos", {})
    texto_norm = normalizar_texto(texto)

    resultado = {
        "razon_social": "",
        "cuit": "",
        "nro_comercio": "",
        "marca_tarjeta": "",
        "total_presentado": 0.0,
        "neto": 0.0,
    }

    # Campos de texto (razón social, CUIT, nro comercio, marca)
    for campo in ("razon_social", "cuit", "nro_comercio", "marca_tarjeta"):
        patron = campos.get(campo, "")
        if patron:
            valor = _extraer_valor_linea(texto_norm, patron)
            # Limpiar hasta salto de línea
            valor = valor.split("\n")[0].strip()
            resultado[campo] = valor

    # Campos numéricos
    for campo in ("total_presentado", "neto"):
        patron = campos.get(campo, "")
        if patron:
            resultado[campo] = extraer_monto_regex(texto, patron)

    return resultado


def dividir_en_bloques(texto: str, separador: str) -> list:
    """
    Divide el texto del PDF en bloques usando el separador del diccionario.
    Si separador es None retorna lista con el texto completo como único elemento.
    """
    if not separador:
        return [texto]
    sep_norm = normalizar_texto(separador)
    texto_norm = normalizar_texto(texto)
    # Encontrar posiciones del separador en el texto normalizado
    partes = re.split(re.escape(sep_norm), texto_norm)
    # Si no hay separadores, retornar texto completo
    if len(partes) <= 1:
        return [texto]
    return partes


def extraer_descuentos_bloque(bloque: str, emisor: str) -> dict:
    """
    Aplica reglas de descuentos sobre un bloque de texto.
    Retorna dict con cada concepto y su monto.
    Conceptos no encontrados → 0.0.
    Conceptos con monto pero sin regla → acumulados en 'sin_categorizar'.
    """
    emisores = _cargar_emisores()
    config = emisores.get(emisor, {})
    descuentos_config = config.get("descuentos", {})

    resultado = {nombre: 0.0 for nombre in descuentos_config}
    resultado["sin_categorizar"] = 0.0
    resultado["_sin_categorizar_detalle"] = []

    for nombre, regla in descuentos_config.items():
        patron = regla.get("patron", "")
        tipo = regla.get("tipo", "unico")
        if patron:
            if tipo == "acumulable":
                # Suma todas las ocurrencias del patrón (ej: Arancel Tj.Crédito, Tj.Débito…)
                montos = extraer_todos_montos_regex(bloque, patron)
                resultado[nombre] = sum(montos)
            else:
                resultado[nombre] = extraer_monto_regex(bloque, patron)

    # Detectar posibles montos no categorizados
    # Buscar líneas con montos que no matcheen ninguna regla conocida
    texto_norm = normalizar_texto(bloque)
    lineas = texto_norm.split("\n")
    patrones_conocidos = [
        normalizar_texto(r.get("patron", ""))
        for r in descuentos_config.values()
        if r.get("patron")
    ]

    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        # Buscar montos en la línea
        montos_en_linea = re.findall(r"[\-\(]?\d[\d.,]+", linea)
        if not montos_en_linea:
            continue
        # Verificar si la línea ya fue procesada por alguna regla
        ya_procesada = any(p in linea for p in patrones_conocidos if p)
        if not ya_procesada and montos_en_linea:
            for m in montos_en_linea:
                valor = convertir_monto(m)
                if abs(valor) > 0.01:
                    resultado["sin_categorizar"] += abs(valor)
                    resultado["_sin_categorizar_detalle"].append({
                        "texto": linea[:100],
                        "monto": valor,
                    })

    return resultado


def acumular_descuentos(lista_bloques: list, emisor: str) -> dict:
    """
    Suma los descuentos de todos los bloques y retorna totales mensuales.
    """
    totales = {}
    detalles_sin_cat = []

    for bloque in lista_bloques:
        descuentos = extraer_descuentos_bloque(bloque, emisor)
        for clave, valor in descuentos.items():
            if clave == "_sin_categorizar_detalle":
                detalles_sin_cat.extend(valor)
                continue
            totales[clave] = totales.get(clave, 0.0) + (valor if isinstance(valor, float) else 0.0)

    totales["_sin_categorizar_detalle"] = detalles_sin_cat
    return totales


def validar_neto(neto_calculado: float, neto_encabezado: float) -> dict:
    """
    Compara neto calculado vs declarado en encabezado.
    Tolerancia de $0.01 por redondeos.
    """
    diferencia = abs(neto_calculado - neto_encabezado)
    coincide = diferencia <= 0.01
    return {
        "coincide": coincide,
        "neto_calculado": neto_calculado,
        "neto_encabezado": neto_encabezado,
        "diferencia": diferencia,
    }


def procesar_pdf(archivo) -> dict:
    """
    Función principal. Orquesta todo el flujo de extracción.
    Retorna objeto resultado completo o dict con error.
    """
    try:
        texto_completo = ""
        with pdfplumber.open(archivo) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text() or ""
                texto_completo += texto_pagina + "\n"

        if not texto_completo.strip():
            return {"error": "El PDF no contiene texto extraíble (puede ser imagen)."}

        emisor = identificar_emisor(texto_completo)
        if emisor == "desconocido":
            return {
                "error": "Emisor no reconocido.",
                "emisor": "desconocido",
                "texto_muestra": texto_completo[:500],
            }

        emisores = _cargar_emisores()
        config = emisores[emisor]
        separador = config.get("separador_bloque")

        encabezado = extraer_encabezado(texto_completo, emisor)
        bloques = dividir_en_bloques(texto_completo, separador)
        descuentos = acumular_descuentos(bloques, emisor)

        # Calcular neto desde total presentado y descuentos
        total = encabezado.get("total_presentado", 0.0)
        suma_descuentos = sum(
            v for k, v in descuentos.items()
            if not k.startswith("_") and isinstance(v, float)
        )
        neto_calculado = total - suma_descuentos
        validacion = validar_neto(neto_calculado, encabezado.get("neto", 0.0))

        # Mapear campos de descuentos a columnas estándar
        def _d(clave):
            return descuentos.get(clave, 0.0)

        resultado = {
            "emisor": emisor,
            "razon_social": encabezado.get("razon_social", ""),
            "cuit": encabezado.get("cuit", ""),
            "nro_comercio": encabezado.get("nro_comercio", ""),
            "marca_tarjeta": encabezado.get("marca_tarjeta", emisor.upper()),
            "total_presentado": total,
            "arancel": _d("arancel"),
            "iva_arancel": _d("iva_arancel"),
            "ret_iibb_sirtac": _d("ret_iibb_sirtac"),
            "per_iibb": _d("per_iibb"),
            "per_iva": _d("per_iva"),
            "otros": _d("otros"),
            "sin_categorizar": _d("sin_categorizar"),
            "sin_categorizar_detalle": descuentos.get("_sin_categorizar_detalle", []),
            "neto_acreditado": encabezado.get("neto", 0.0),
            "neto_calculado": neto_calculado,
            "validacion": validacion,
            "descuentos_raw": {
                k: v for k, v in descuentos.items()
                if not k.startswith("_") and isinstance(v, float)
            },
        }
        return resultado

    except Exception as e:
        return {"error": f"Error al procesar el PDF: {str(e)}"}
