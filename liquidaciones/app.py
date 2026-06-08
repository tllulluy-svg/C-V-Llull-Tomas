"""
Interfaz principal Streamlit para procesamiento de liquidaciones de tarjetas.
"""

import sys
from pathlib import Path

# Asegurar que los módulos del proyecto estén en el path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import json
from io import BytesIO

import database as db
import extractor
from diccionario import EMISORES

st.set_page_config(
    page_title="Liquidaciones de Tarjetas",
    page_icon="💳",
    layout="wide",
)

# Inicializar base de datos y cargar diccionario base
db.crear_tablas()
db.sincronizar_emisores_desde_diccionario(EMISORES)


# ─────────────────────────────────────────────────────────────
# Helpers de formato
# ─────────────────────────────────────────────────────────────

def fmt_monto(valor):
    try:
        return f"$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(valor)


def _estado_inicial():
    if "cola_pdfs" not in st.session_state:
        st.session_state.cola_pdfs = []
    if "indice_actual" not in st.session_state:
        st.session_state.indice_actual = 0
    if "resultado_actual" not in st.session_state:
        st.session_state.resultado_actual = None
    if "periodo_actual" not in st.session_state:
        st.session_state.periodo_actual = ""


_estado_inicial()


# ─────────────────────────────────────────────────────────────
# SECCIÓN 1 — Carga y procesamiento
# ─────────────────────────────────────────────────────────────

def seccion_carga():
    st.header("📂 Carga y procesamiento de PDFs")

    col1, col2 = st.columns([3, 1])
    with col1:
        archivos = st.file_uploader(
            "Seleccioná uno o más archivos PDF",
            type=["pdf"],
            accept_multiple_files=True,
            key="uploader",
        )
    with col2:
        periodo = st.text_input(
            "Período (MM/AAAA)",
            placeholder="01/2025",
            key="periodo_input",
        )

    if archivos and st.button("Procesar PDFs", type="primary"):
        st.session_state.cola_pdfs = archivos
        st.session_state.indice_actual = 0
        st.session_state.resultado_actual = None
        st.session_state.periodo_actual = periodo
        st.rerun()

    # Mostrar resumen del PDF actual en la cola
    if st.session_state.cola_pdfs:
        idx = st.session_state.indice_actual
        total = len(st.session_state.cola_pdfs)

        if idx >= total:
            st.success(f"✅ Se procesaron los {total} PDFs.")
            st.session_state.cola_pdfs = []
            st.session_state.indice_actual = 0
            st.session_state.resultado_actual = None
            return

        archivo = st.session_state.cola_pdfs[idx]
        st.info(f"Procesando {idx + 1} de {total}: **{archivo.name}**")

        if st.session_state.resultado_actual is None:
            with st.spinner("Extrayendo datos del PDF..."):
                st.session_state.resultado_actual = extractor.procesar_pdf(archivo)

        resultado = st.session_state.resultado_actual

        if "error" in resultado:
            st.error(f"⚠️ {resultado['error']}")
            if resultado.get("emisor") == "desconocido":
                st.info("Este emisor no está configurado. Podés agregarlo en la sección **Administración de emisores**.")
                if resultado.get("texto_muestra"):
                    with st.expander("Ver muestra del texto extraído"):
                        st.text(resultado["texto_muestra"])
            col_desc, col_sig = st.columns(2)
            with col_desc:
                if st.button("Descartar y continuar", key="btn_descartar_error"):
                    _avanzar_cola()
            return

        mostrar_resumen(resultado)


def mostrar_resumen(r: dict):
    """Muestra el resumen del resultado de extracción."""
    st.subheader("Resumen de liquidación")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Razón Social:** {r.get('razon_social', '-')}")
        st.markdown(f"**CUIT:** {r.get('cuit', '-')}")
        st.markdown(f"**N° Comercio:** {r.get('nro_comercio', '-')}")
    with col2:
        st.markdown(f"**Emisor:** {r.get('emisor', '-').upper()}")
        st.markdown(f"**Marca Tarjeta:** {r.get('marca_tarjeta', '-')}")
        st.markdown(f"**Período:** {st.session_state.periodo_actual or '-'}")
    with col3:
        st.markdown(f"**Total Presentado:** {fmt_monto(r.get('total_presentado', 0))}")
        st.markdown(f"**Neto Acreditado:** {fmt_monto(r.get('neto_acreditado', 0))}")

    st.divider()
    st.subheader("Descuentos")

    etiquetas = {
        "arancel": "Arancel",
        "iva_arancel": "IVA s/Arancel",
        "ret_iibb_sirtac": "Ret. IIBB SIRTAC",
        "per_iibb": "Per. IIBB",
        "per_iva": "Per. IVA",
        "otros": "Otros",
    }

    for clave, etiqueta in etiquetas.items():
        valor = r.get(clave, 0.0)
        if valor and valor != 0.0:
            st.markdown(f"- **{etiqueta}:** {fmt_monto(valor)}")

    sin_cat = r.get("sin_categorizar", 0.0)
    if sin_cat and sin_cat > 0.01:
        st.markdown(
            f"- :orange[**Conceptos sin categorizar:** {fmt_monto(sin_cat)}]"
        )
        with st.expander("Ver detalle de conceptos sin categorizar"):
            for item in r.get("sin_categorizar_detalle", []):
                st.text(f"  {item['texto']}  →  {fmt_monto(item['monto'])}")

    st.divider()
    # Validación de neto
    val = r.get("validacion", {})
    if val.get("coincide"):
        st.success("✅ El neto calculado coincide con el neto del documento.")
    else:
        st.warning(
            f"⚠️ Diferencia de {fmt_monto(val.get('diferencia', 0))} "
            f"(calculado: {fmt_monto(val.get('neto_calculado', 0))} | "
            f"documento: {fmt_monto(val.get('neto_encabezado', 0))})"
        )

    st.divider()
    col_conf, col_desc = st.columns(2)
    with col_conf:
        if st.button("✅ Confirmar y guardar", type="primary", key="btn_confirmar"):
            _guardar_y_avanzar(r)
    with col_desc:
        if st.button("🗑️ Descartar", key="btn_descartar"):
            _avanzar_cola()


def _guardar_y_avanzar(resultado: dict):
    datos = {
        "razon_social": resultado.get("razon_social", ""),
        "cuit": resultado.get("cuit", ""),
        "nro_comercio": resultado.get("nro_comercio", ""),
        "marca_tarjeta": resultado.get("marca_tarjeta", ""),
        "emisor": resultado.get("emisor", ""),
        "periodo": st.session_state.periodo_actual,
        "total_presentado": resultado.get("total_presentado", 0.0),
        "arancel": resultado.get("arancel", 0.0),
        "iva_arancel": resultado.get("iva_arancel", 0.0),
        "ret_iibb_sirtac": resultado.get("ret_iibb_sirtac", 0.0),
        "per_iibb": resultado.get("per_iibb", 0.0),
        "per_iva": resultado.get("per_iva", 0.0),
        "otros": resultado.get("otros", 0.0),
        "sin_categorizar": resultado.get("sin_categorizar", 0.0),
        "neto_acreditado": resultado.get("neto_acreditado", 0.0),
    }
    db.guardar_liquidacion(datos)

    # Guardar conceptos sin categorizar para revisión
    for item in resultado.get("sin_categorizar_detalle", []):
        db.guardar_concepto_sin_categorizar(
            item["texto"], item["monto"], resultado.get("emisor", "")
        )

    st.toast("Liquidación guardada correctamente.")
    _avanzar_cola()


def _avanzar_cola():
    st.session_state.indice_actual += 1
    st.session_state.resultado_actual = None
    st.rerun()


# ─────────────────────────────────────────────────────────────
# SECCIÓN 2 — Historial acumulado
# ─────────────────────────────────────────────────────────────

def seccion_historial():
    st.header("📊 Historial acumulado")

    col_filtro, col_btn = st.columns([3, 1])
    with col_filtro:
        filtro = st.text_input("Filtrar por N° de comercio", placeholder="Ingresá parte del número")
    with col_btn:
        st.write("")  # espaciador
        exportar = st.button("⬇️ Descargar CSV")

    registros = db.obtener_historial(filtro_nro_comercio=filtro if filtro else None)

    if not registros:
        st.info("No hay liquidaciones guardadas aún.")
        return

    df = pd.DataFrame(registros)

    # Columnas más legibles
    renombrar = {
        "id": "ID",
        "razon_social": "Razón Social",
        "cuit": "CUIT",
        "nro_comercio": "N° Comercio",
        "marca_tarjeta": "Tarjeta",
        "emisor": "Emisor",
        "periodo": "Período",
        "total_presentado": "Total Presentado",
        "arancel": "Arancel",
        "iva_arancel": "IVA Arancel",
        "ret_iibb_sirtac": "Ret. IIBB SIRTAC",
        "per_iibb": "Per. IIBB",
        "per_iva": "Per. IVA",
        "otros": "Otros",
        "sin_categorizar": "Sin Categorizar",
        "neto_acreditado": "Neto Acreditado",
        "fecha_carga": "Fecha Carga",
    }
    df = df.rename(columns=renombrar)

    # Columnas numéricas con formato
    cols_montos = [
        "Total Presentado", "Arancel", "IVA Arancel", "Ret. IIBB SIRTAC",
        "Per. IIBB", "Per. IVA", "Otros", "Sin Categorizar", "Neto Acreditado",
    ]
    st.dataframe(
        df.style.format({c: "{:,.2f}" for c in cols_montos if c in df.columns}),
        use_container_width=True,
        hide_index=True,
    )

    if exportar:
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="Descargar CSV",
            data=csv,
            file_name=f"liquidaciones_{filtro or 'todas'}.csv",
            mime="text/csv",
        )


# ─────────────────────────────────────────────────────────────
# SECCIÓN 3 — Administración de emisores
# ─────────────────────────────────────────────────────────────

def seccion_emisores():
    st.header("⚙️ Administración de emisores")

    emisores = db.obtener_emisores()
    tab_lista, tab_nuevo, tab_sin_cat = st.tabs(
        ["Emisores configurados", "Agregar emisor", "Conceptos sin categorizar"]
    )

    # ── Tab 1: Lista de emisores ──────────────────────────────
    with tab_lista:
        if not emisores:
            st.info("No hay emisores configurados.")
        else:
            for nombre, config in emisores.items():
                with st.expander(f"📋 {nombre.upper()}"):
                    st.json(config)

    # ── Tab 2: Agregar nuevo emisor ───────────────────────────
    with tab_nuevo:
        st.subheader("Nuevo emisor")
        with st.form("form_nuevo_emisor"):
            nombre_emisor = st.text_input("Nombre del emisor (ej: prisma)")
            identificadores_raw = st.text_area(
                "Palabras clave de identificación (una por línea)",
                placeholder="prisma\nliquidacion prisma",
            )
            st.markdown("**Campos del encabezado** (patron → nombre del campo en el PDF)")
            col_campos = {
                "razon_social": st.text_input("Patrón razón social", placeholder="comercio"),
                "cuit": st.text_input("Patrón CUIT", placeholder="cuit"),
                "nro_comercio": st.text_input("Patrón N° comercio", placeholder="nro. comercio"),
                "marca_tarjeta": st.text_input("Patrón marca tarjeta", placeholder="visa"),
                "total_presentado": st.text_input("Patrón total presentado", placeholder="total bruto"),
                "neto": st.text_input("Patrón neto", placeholder="importe neto"),
            }
            separador = st.text_input(
                "Separador de bloques (dejar vacío si es bloque único)",
                placeholder="f.de pago:",
            )
            st.markdown("**Descuentos** — Agregar hasta 6")
            descuentos_nuevos = {}
            for i in range(1, 7):
                c1, c2, c3 = st.columns([2, 2, 1])
                with c1:
                    nombre_d = st.text_input(f"Nombre descuento {i}", key=f"d_nombre_{i}")
                with c2:
                    patron_d = st.text_input(f"Patrón {i}", key=f"d_patron_{i}")
                with c3:
                    oblig_d = st.checkbox(f"Oblig.", key=f"d_oblig_{i}")
                if nombre_d and patron_d:
                    descuentos_nuevos[nombre_d] = {
                        "patron": patron_d,
                        "tipo": "unico",
                        "obligatorio": oblig_d,
                    }

            submitted = st.form_submit_button("Guardar emisor")
            if submitted:
                if not nombre_emisor:
                    st.error("El nombre del emisor es obligatorio.")
                else:
                    datos = {
                        "identificadores": [
                            l.strip() for l in identificadores_raw.split("\n") if l.strip()
                        ],
                        "campos": {k: v for k, v in col_campos.items() if v},
                        "descuentos": descuentos_nuevos,
                        "separador_bloque": separador if separador else None,
                    }
                    db.guardar_emisor(nombre_emisor.lower().strip(), datos)
                    st.success(f"Emisor '{nombre_emisor}' guardado correctamente.")
                    st.rerun()

        # Sub-sección: probar emisor con PDF
        st.subheader("Probar emisor con PDF")
        pdf_prueba = st.file_uploader("Subí un PDF para probar la extracción", type=["pdf"], key="pdf_prueba")
        if pdf_prueba and st.button("Probar extracción", key="btn_probar"):
            with st.spinner("Procesando..."):
                resultado_prueba = extractor.procesar_pdf(pdf_prueba)
            st.subheader("Resultado de prueba")
            if "error" in resultado_prueba:
                st.error(resultado_prueba["error"])
            else:
                st.json({
                    k: v for k, v in resultado_prueba.items()
                    if k != "sin_categorizar_detalle"
                })
                if resultado_prueba.get("sin_categorizar_detalle"):
                    st.warning("Conceptos sin categorizar detectados:")
                    for item in resultado_prueba["sin_categorizar_detalle"]:
                        st.text(f"  {item['texto']}  →  {fmt_monto(item['monto'])}")

    # ── Tab 3: Conceptos sin categorizar ─────────────────────
    with tab_sin_cat:
        conceptos = db.obtener_conceptos_sin_categorizar()
        if not conceptos:
            st.info("No hay conceptos sin categorizar pendientes.")
        else:
            st.info(
                f"Hay **{len(conceptos)}** concepto(s) sin categorizar. "
                "Podés convertirlos en regla para futuros PDFs."
            )
            for concepto in conceptos:
                with st.expander(
                    f"[{concepto['emisor'].upper()}] {concepto['texto_original'][:60]}  →  {fmt_monto(concepto['monto'])}"
                ):
                    st.text(f"Emisor: {concepto['emisor']}")
                    st.text(f"Texto: {concepto['texto_original']}")
                    st.text(f"Monto: {fmt_monto(concepto['monto'])}")
                    st.text(f"Fecha: {concepto['fecha']}")
                    with st.form(f"form_convertir_{concepto['id']}"):
                        nombre_regla = st.text_input("Nombre de la regla", key=f"regla_nombre_{concepto['id']}")
                        patron_regla = st.text_input(
                            "Patrón (texto a buscar)",
                            value=concepto["texto_original"][:40],
                            key=f"regla_patron_{concepto['id']}",
                        )
                        oblig_regla = st.checkbox("Obligatorio", key=f"regla_oblig_{concepto['id']}")
                        if st.form_submit_button("Convertir en regla"):
                            if nombre_regla and patron_regla:
                                emisores_db = db.obtener_emisores()
                                config_emisor = emisores_db.get(concepto["emisor"], {})
                                descuentos_actuales = config_emisor.get("descuentos", {})
                                descuentos_actuales[nombre_regla] = {
                                    "patron": patron_regla,
                                    "tipo": "unico",
                                    "obligatorio": oblig_regla,
                                }
                                config_emisor["descuentos"] = descuentos_actuales
                                db.guardar_emisor(concepto["emisor"], config_emisor)
                                db.marcar_concepto_convertido(concepto["id"])
                                st.success("Regla guardada y concepto marcado como convertido.")
                                st.rerun()


# ─────────────────────────────────────────────────────────────
# NAVEGACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────

st.title("💳 Liquidaciones de Tarjetas")
st.caption("Procesamiento automático de liquidaciones de Fiserv, Naranja, Cabal, Favacard y Payway.")

tab1, tab2, tab3 = st.tabs(["📂 Carga", "📊 Historial", "⚙️ Emisores"])

with tab1:
    seccion_carga()

with tab2:
    seccion_historial()

with tab3:
    seccion_emisores()
