import sqlite3
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / "liquidaciones.db"


def _conexion():
    return sqlite3.connect(DB_PATH)


def _migrar_db(conn):
    """Agrega columnas nuevas a tablas existentes si todavía no están."""
    try:
        conn.execute("ALTER TABLE emisores_config ADD COLUMN separador_resumen TEXT")
    except Exception:
        pass  # Ya existe


def crear_tablas():
    """Crea las tablas necesarias si no existen."""
    with _conexion() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS liquidaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                razon_social TEXT,
                cuit TEXT,
                nro_comercio TEXT,
                marca_tarjeta TEXT,
                emisor TEXT,
                periodo TEXT,
                total_presentado REAL,
                arancel REAL,
                iva_arancel REAL,
                ret_iibb_sirtac REAL,
                per_iibb REAL,
                per_iva REAL,
                otros REAL,
                sin_categorizar REAL,
                neto_acreditado REAL,
                fecha_carga TEXT
            );

            CREATE TABLE IF NOT EXISTS emisores_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE,
                identificadores TEXT,
                campos TEXT,
                descuentos TEXT,
                separador_bloque TEXT,
                separador_resumen TEXT
            );
            -- migración: agregar columna si no existe (SQLite ignora el error si ya existe)


            CREATE TABLE IF NOT EXISTS conceptos_sin_categorizar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                texto_original TEXT,
                monto REAL,
                emisor TEXT,
                fecha TEXT,
                convertido INTEGER DEFAULT 0
            );
        """)
        _migrar_db(conn)


def guardar_liquidacion(datos: dict):
    """Inserta un registro de liquidación procesada."""
    sql = """
        INSERT INTO liquidaciones (
            razon_social, cuit, nro_comercio, marca_tarjeta, emisor,
            periodo, total_presentado, arancel, iva_arancel,
            ret_iibb_sirtac, per_iibb, per_iva, otros,
            sin_categorizar, neto_acreditado, fecha_carga
        ) VALUES (
            :razon_social, :cuit, :nro_comercio, :marca_tarjeta, :emisor,
            :periodo, :total_presentado, :arancel, :iva_arancel,
            :ret_iibb_sirtac, :per_iibb, :per_iva, :otros,
            :sin_categorizar, :neto_acreditado, :fecha_carga
        )
    """
    datos.setdefault("fecha_carga", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with _conexion() as conn:
        conn.execute(sql, datos)


def obtener_historial(filtro_nro_comercio=None):
    """Retorna todos los registros de liquidaciones, opcionalmente filtrados."""
    sql = "SELECT * FROM liquidaciones"
    params = []
    if filtro_nro_comercio:
        sql += " WHERE nro_comercio LIKE ?"
        params.append(f"%{filtro_nro_comercio}%")
    sql += " ORDER BY fecha_carga DESC"
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def exportar_csv(filtro=None):
    """Genera DataFrame pandas con el historial listo para descarga."""
    registros = obtener_historial(filtro_nro_comercio=filtro)
    if not registros:
        return pd.DataFrame()
    return pd.DataFrame(registros)


def obtener_emisores():
    """Retorna la configuración de emisores desde la base."""
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM emisores_config").fetchall()
    resultado = {}
    for r in rows:
        resultado[r["nombre"]] = {
            "identificadores": json.loads(r["identificadores"]),
            "campos": json.loads(r["campos"]),
            "descuentos": json.loads(r["descuentos"]),
            "separador_bloque": r["separador_bloque"],
            "separador_resumen": r["separador_resumen"],
        }
    return resultado


def guardar_emisor(nombre: str, datos: dict):
    """Inserta o actualiza un emisor en emisores_config."""
    sql = """
        INSERT INTO emisores_config (nombre, identificadores, campos, descuentos, separador_bloque, separador_resumen)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            identificadores=excluded.identificadores,
            campos=excluded.campos,
            descuentos=excluded.descuentos,
            separador_bloque=excluded.separador_bloque,
            separador_resumen=excluded.separador_resumen
    """
    with _conexion() as conn:
        conn.execute(sql, (
            nombre,
            json.dumps(datos.get("identificadores", []), ensure_ascii=False),
            json.dumps(datos.get("campos", {}), ensure_ascii=False),
            json.dumps(datos.get("descuentos", {}), ensure_ascii=False),
            datos.get("separador_bloque"),
            datos.get("separador_resumen"),
        ))


def sincronizar_emisores_desde_diccionario(emisores_dict: dict):
    """
    Sincroniza el diccionario base en SQLite.
    Inserta emisores nuevos y actualiza los existentes que vengan del diccionario base
    (no sobreescribe emisores creados manualmente que no estén en el diccionario base).
    """
    for nombre, datos in emisores_dict.items():
        guardar_emisor(nombre, datos)


def guardar_concepto_sin_categorizar(texto: str, monto: float, emisor: str):
    """Persiste un concepto no reconocido para revisión posterior."""
    sql = """
        INSERT INTO conceptos_sin_categorizar (texto_original, monto, emisor, fecha)
        VALUES (?, ?, ?, ?)
    """
    with _conexion() as conn:
        conn.execute(sql, (texto, monto, emisor, datetime.now().strftime("%Y-%m-%d")))


def obtener_conceptos_sin_categorizar():
    """Retorna conceptos sin categorizar pendientes de revisión."""
    sql = "SELECT * FROM conceptos_sin_categorizar WHERE convertido = 0 ORDER BY fecha DESC"
    with _conexion() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def marcar_concepto_convertido(concepto_id: int):
    """Marca un concepto como ya convertido a regla."""
    with _conexion() as conn:
        conn.execute(
            "UPDATE conceptos_sin_categorizar SET convertido = 1 WHERE id = ?",
            (concepto_id,),
        )
