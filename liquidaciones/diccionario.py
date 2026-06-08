"""
Diccionario central de emisores. Define identificadores, patrones de campos
y reglas de descuentos por emisor.

Este diccionario es la fuente de verdad por defecto. La app también persiste
la configuración en SQLite para permitir edición desde la interfaz.
"""

EMISORES = {
    "fiserv": {
        "identificadores": [
            "fiserv",
            "resumen mensual de liquidaciones a comercios",
        ],
        "campos": {
            "razon_social": "comercio",
            "cuit": "cuit",
            "nro_comercio": "n° comercio",
            "marca_tarjeta": "tarjeta de",
            "total_presentado": "total presentado",
            "neto": "neto de pagos",
        },
        "descuentos": {
            "arancel": {
                "patron": "arancel",
                "tipo": "acumulable",
                "obligatorio": True,
            },
            "iva_arancel": {
                "patron": "iva cred.fisc.comercio s/aranc",
                "tipo": "acumulable",
                "obligatorio": True,
            },
            "ret_iibb_sirtac": {
                "patron": "retencion ing.brutos sirtac",
                "tipo": "acumulable",
                "obligatorio": True,
            },
            "per_iibb": {
                "patron": "per b.a.i.br.dn.01/04",
                "tipo": "acumulable",
                "obligatorio": False,
            },
        },
        "separador_bloque": "f.de pago: acred.en cta.cte.nro",
    },
    "naranja": {
        "identificadores": [
            "naranja x",
            "tarjeta naranja",
            "detalle de cupones liquidados",
        ],
        "campos": {
            "razon_social": "la fonte",
            "cuit": "cuit:",
            "nro_comercio": "550.",
            "marca_tarjeta": "naranja x",
            "total_presentado": "totales",
            "neto": "neto liquidado",
        },
        "descuentos": {
            "arancel": {
                "patron": "arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "iva_arancel": {
                "patron": "iva",
                "tipo": "unico",
                "obligatorio": True,
            },
            "per_iibb_ba": {
                "patron": "percepcion ingresos brutos buenos aires",
                "tipo": "unico",
                "obligatorio": False,
            },
            "per_iva": {
                "patron": "percepcion de iva",
                "tipo": "unico",
                "obligatorio": False,
            },
            "ret_iibb_sirtac": {
                "patron": "sirtac",
                "tipo": "unico",
                "obligatorio": True,
            },
        },
        "separador_bloque": None,
    },
    "cabal": {
        "identificadores": [
            "cabal",
            "liquidacion cabal",
            "red cabal",
        ],
        "campos": {
            "razon_social": "razon social",
            "cuit": "cuit",
            "nro_comercio": "nro. comercio",
            "marca_tarjeta": "cabal",
            "total_presentado": "total bruto",
            "neto": "importe neto",
        },
        "descuentos": {
            "arancel": {
                "patron": "arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "iva_arancel": {
                "patron": "iva s/arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "ret_iibb_sirtac": {
                "patron": "ret. iibb sirtac",
                "tipo": "unico",
                "obligatorio": False,
            },
            "per_iibb": {
                "patron": "per. iibb",
                "tipo": "unico",
                "obligatorio": False,
            },
        },
        "separador_bloque": None,
    },
    "favacard": {
        "identificadores": [
            "favacard",
            "liquidacion favacard",
        ],
        "campos": {
            "razon_social": "comercio",
            "cuit": "cuit",
            "nro_comercio": "nro comercio",
            "marca_tarjeta": "favacard",
            "total_presentado": "total presentado",
            "neto": "neto a acreditar",
        },
        "descuentos": {
            "arancel": {
                "patron": "arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "iva_arancel": {
                "patron": "iva arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "ret_iibb_sirtac": {
                "patron": "ret. ingresos brutos",
                "tipo": "unico",
                "obligatorio": False,
            },
        },
        "separador_bloque": None,
    },
    "payway": {
        "identificadores": [
            "payway",
            "pay way",
            "liquidacion payway",
        ],
        "campos": {
            "razon_social": "razon social",
            "cuit": "cuit",
            "nro_comercio": "nro. comercio",
            "marca_tarjeta": "visa",
            "total_presentado": "importe bruto",
            "neto": "importe neto",
        },
        "descuentos": {
            "arancel": {
                "patron": "arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "iva_arancel": {
                "patron": "iva s/arancel",
                "tipo": "unico",
                "obligatorio": True,
            },
            "ret_iibb_sirtac": {
                "patron": "ret. iibb sirtac",
                "tipo": "unico",
                "obligatorio": False,
            },
            "per_iibb": {
                "patron": "per. iibb",
                "tipo": "unico",
                "obligatorio": False,
            },
            "per_iva": {
                "patron": "per. iva",
                "tipo": "unico",
                "obligatorio": False,
            },
        },
        "separador_bloque": None,
    },
}
