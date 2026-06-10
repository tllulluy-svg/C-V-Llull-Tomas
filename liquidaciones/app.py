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
    defaults = {
        "pdf_actual": None,
        "resultado_actual": None,
        "periodo_actual": "",
        "emisor_forzado": None,
        "procesando": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_estado_inicial()


def _emisores_disponibles():
    """Retorna lista de emisores para el selector."""
    emisores = db.obtener_emisores()
    return ["Auto-detectar"] + [e.upper() for e in sorted(emisores.keys())]


# ─────────────────────────────────────────────────────────────
# SECCIÓN 1 — Carga y procesamiento
# ─────────────────────────────────────────────────────────────

def seccion_carga():
    st.header("📂 Carga de liquidación")

    # ── Panel de configuración (siempre visible cuando no hay PDF en proceso) ──
    if st.session_state.resultado_actual is None:
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            archivo = st.file_uploader(
                "Seleccioná un PDF",
                type=["pdf"],
                accept_multiple_files=False,
                key="uploader",
            )
        with col2:
            periodo = st.text_input(
                "Período",
                placeholder="01/2025",
                key="periodo_input",
            )
        with col3:
            opciones_emisor = _emisores_disponibles()
            emisor_sel = st.selectbox(
                "Emisor",
                options=opciones_emisor,
                key="sel_emisor",
                help="Seleccioná el emisor si sabés cuál es. 'Auto-detectar' lo busca automáticamente.",
            )

        if archivo:
            if st.button("Analizar PDF", type="primary"):
                emisor_forzado = None if emisor_sel == "Auto-detectar" else emisor_sel.lower()
                with st.spinner("Extrayendo datos del PDF..."):
                    resultado = extractor.procesar_pdf(archivo, emisor_forzado=emisor_forzado)
                st.session_state.resultado_actual = resultado
                st.session_state.periodo_actual = periodo
                st.session_state.pdf_actual = archivo.name
                st.rerun()
        return

    # ── Hay resultado para revisar ──
    resultado = st.session_state.resultado_actual
    st.info(f"📄 **{st.session_state.pdf_actual}**")

    if "error" in resultado:
        st.error(f"⚠️ {resultado['error']}")
        if resultado.get("emisor") == "desconocido":
            st.info("El emisor no se reconoció. Podés seleccionarlo manualmente desde el selector de arriba.")
            if resultado.get("texto_muestra"):
                with st.expander("Ver muestra del texto extraído"):
                    st.text(resultado["texto_muestra"])
        if st.button("Intentar con otro emisor / Cancelar"):
            st.session_state.resultado_actual = None
            st.rerun()
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
            _limpiar_resultado()


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
    _limpiar_resultado()


def _limpiar_resultado():
    st.session_state.resultado_actual = None
    st.session_state.pdf_actual = None
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

CONCEPTOS_ETIQUETAS = {
    "arancel": "Arancel",
    "iva_arancel": "IVA s/Arancel",
    "ret_iibb_sirtac": "Retención IIBB SIRTAC",
    "per_iibb": "Percepción IIBB",
    "per_iva": "Percepción IVA",
    "otros": "Otros descuentos",
}

CONCEPTOS_OPCIONES = [
    "Arancel",
    "IVA s/Arancel",
    "Retención IIBB SIRTAC",
    "Percepción IIBB",
    "Percepción IVA",
    "Otros descuentos",
]

CONCEPTOS_CLAVES = {v: k for k, v in CONCEPTOS_ETIQUETAS.items()}


def _renderizar_emisor(nombre, config, idx):
    """Muestra un emisor como tarjeta visual sin código."""
    identificadores = config.get("identificadores", [])
    descuentos = config.get("descuentos", {})

    with st.expander(f"**{nombre.upper()}**", expanded=False):
        # Palabras clave de identificación
        st.markdown("**Palabras clave que identifican este emisor en el PDF:**")
        if identificadores:
            cols = st.columns(min(len(identificadores), 4))
            for i, ident in enumerate(identificadores):
                cols[i % 4].markdown(
                    f"<span style='background:#e8f4fd;padding:4px 10px;"
                    f"border-radius:12px;font-size:0.85em;color:#1a73e8'>"
                    f"🔍 {ident}</span>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin palabras clave definidas.")

        st.divider()

        # Conceptos de descuento
        st.markdown("**Conceptos y sus palabras clave en el PDF:**")
        if descuentos:
            for nombre_d, regla in descuentos.items():
                etiqueta = CONCEPTOS_ETIQUETAS.get(nombre_d, nombre_d.replace("_", " ").title())
                patron = regla.get("patron", "")
                obligatorio = regla.get("obligatorio", False)
                badge_oblig = (
                    "<span style='background:#fce8e6;color:#c62828;padding:2px 7px;"
                    "border-radius:10px;font-size:0.75em'>obligatorio</span>"
                    if obligatorio
                    else "<span style='background:#f1f3f4;color:#5f6368;padding:2px 7px;"
                    "border-radius:10px;font-size:0.75em'>opcional</span>"
                )
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:10px;margin:6px 0'>"
                    f"<span style='min-width:180px;font-weight:500'>{etiqueta}</span>"
                    f"<span style='background:#f8f9fa;border:1px solid #dadce0;padding:3px 10px;"
                    f"border-radius:6px;font-family:monospace;font-size:0.85em'>{patron}</span>"
                    f"{badge_oblig}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.caption("Sin conceptos definidos.")

        st.divider()

        # Botón para editar
        if st.button(f"✏️ Editar {nombre.upper()}", key=f"btn_editar_{idx}"):
            st.session_state[f"editando_emisor"] = nombre
            st.rerun()


def _form_editar_emisor(nombre, config):
    """Formulario de edición visual de un emisor."""
    st.subheader(f"Editando: {nombre.upper()}")

    identificadores_actuales = config.get("identificadores", [])
    descuentos_actuales = config.get("descuentos", {})
    campos_actuales = config.get("campos", {})

    with st.form(f"form_editar_{nombre}"):
        st.markdown("#### Palabras clave de identificación")
        st.caption("Fragmentos de texto que aparecen en el PDF y permiten identificar el emisor.")

        nuevos_ident = []
        for i in range(5):
            val = identificadores_actuales[i] if i < len(identificadores_actuales) else ""
            inp = st.text_input(
                f"Palabra clave {i+1}",
                value=val,
                placeholder="ej: fiserv o resumen mensual de liquidaciones",
                key=f"edit_ident_{nombre}_{i}",
            )
            if inp.strip():
                nuevos_ident.append(inp.strip())

        st.divider()
        st.markdown("#### Conceptos de descuento")
        st.caption("Para cada concepto, escribí el texto exacto como aparece en el PDF.")

        nuevos_descuentos = {}
        conceptos_orden = list(CONCEPTOS_ETIQUETAS.items()) + [
            (k, k.replace("_", " ").title())
            for k in descuentos_actuales
            if k not in CONCEPTOS_ETIQUETAS
        ]

        for clave, etiqueta in conceptos_orden:
            regla_actual = descuentos_actuales.get(clave, {})
            patron_actual = regla_actual.get("patron", "")
            oblig_actual = regla_actual.get("obligatorio", False)

            c1, c2, c3 = st.columns([2, 3, 1])
            with c1:
                st.markdown(f"**{etiqueta}**")
            with c2:
                patron_nuevo = st.text_input(
                    "Texto en el PDF",
                    value=patron_actual,
                    placeholder="ej: arancel",
                    key=f"edit_patron_{nombre}_{clave}",
                    label_visibility="collapsed",
                )
            with c3:
                oblig_nuevo = st.checkbox(
                    "Oblig.",
                    value=oblig_actual,
                    key=f"edit_oblig_{nombre}_{clave}",
                )
            if patron_nuevo.strip():
                nuevos_descuentos[clave] = {
                    "patron": patron_nuevo.strip(),
                    "tipo": regla_actual.get("tipo", "unico"),
                    "obligatorio": oblig_nuevo,
                }

        col_g, col_c = st.columns(2)
        with col_g:
            guardar = st.form_submit_button("💾 Guardar cambios", type="primary")
        with col_c:
            cancelar = st.form_submit_button("Cancelar")

    if guardar:
        config["identificadores"] = nuevos_ident
        config["descuentos"] = nuevos_descuentos
        config["campos"] = campos_actuales
        db.guardar_emisor(nombre, config)
        del st.session_state["editando_emisor"]
        st.success("Cambios guardados.")
        st.rerun()

    if cancelar:
        del st.session_state["editando_emisor"]
        st.rerun()


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
            editando = st.session_state.get("editando_emisor")
            if editando and editando in emisores:
                _form_editar_emisor(editando, emisores[editando])
            else:
                for idx, (nombre, config) in enumerate(emisores.items()):
                    _renderizar_emisor(nombre, config, idx)

    # ── Tab 2: Agregar nuevo emisor ───────────────────────────
    with tab_nuevo:
        st.subheader("Nuevo emisor")
        st.caption("Completá los datos del nuevo emisor. Podés editar los detalles después desde la lista.")

        with st.form("form_nuevo_emisor"):
            nombre_emisor = st.text_input(
                "Nombre del emisor",
                placeholder="ej: prisma",
            )

            st.markdown("#### Palabras clave de identificación")
            st.caption("Fragmentos de texto que aparecen en el PDF y permiten identificar el emisor.")
            idents = []
            for i in range(4):
                val = st.text_input(
                    f"Palabra clave {i+1}",
                    placeholder="ej: prisma" if i == 0 else "ej: liquidacion prisma",
                    key=f"new_ident_{i}",
                )
                if val.strip():
                    idents.append(val.strip())

            st.divider()
            st.markdown("#### Conceptos de descuento")
            st.caption("Para cada concepto que aparece en este PDF, escribí el texto que lo identifica.")

            nuevos_descuentos = {}
            for clave, etiqueta in CONCEPTOS_ETIQUETAS.items():
                c1, c2, c3 = st.columns([2, 3, 1])
                with c1:
                    st.markdown(f"**{etiqueta}**")
                with c2:
                    patron = st.text_input(
                        "Texto en el PDF",
                        placeholder="ej: arancel",
                        key=f"new_patron_{clave}",
                        label_visibility="collapsed",
                    )
                with c3:
                    oblig = st.checkbox("Oblig.", key=f"new_oblig_{clave}")
                if patron.strip():
                    nuevos_descuentos[clave] = {
                        "patron": patron.strip(),
                        "tipo": "unico",
                        "obligatorio": oblig,
                    }

            submitted = st.form_submit_button("Guardar emisor", type="primary")
            if submitted:
                if not nombre_emisor.strip():
                    st.error("El nombre del emisor es obligatorio.")
                elif not idents:
                    st.error("Agregá al menos una palabra clave de identificación.")
                else:
                    db.guardar_emisor(nombre_emisor.lower().strip(), {
                        "identificadores": idents,
                        "campos": {},
                        "descuentos": nuevos_descuentos,
                        "separador_bloque": None,
                    })
                    st.success(f"Emisor '{nombre_emisor.upper()}' guardado. Podés editarlo desde la lista.")
                    st.rerun()

        # Probar con PDF
        st.divider()
        st.subheader("Probar con un PDF")
        st.caption("Subí un PDF para verificar qué extrae la herramienta antes de configurar.")
        pdf_prueba = st.file_uploader("Seleccionar PDF de prueba", type=["pdf"], key="pdf_prueba")
        if pdf_prueba and st.button("Probar extracción", key="btn_probar"):
            with st.spinner("Procesando..."):
                res = extractor.procesar_pdf(pdf_prueba)
            if "error" in res:
                st.error(res["error"])
            else:
                st.success(f"Emisor detectado: **{res.get('emisor', '').upper()}**")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Razón Social:** {res.get('razon_social', '-')}")
                    st.markdown(f"**CUIT:** {res.get('cuit', '-')}")
                    st.markdown(f"**N° Comercio:** {res.get('nro_comercio', '-')}")
                with col2:
                    st.markdown(f"**Total Presentado:** {fmt_monto(res.get('total_presentado', 0))}")
                    st.markdown(f"**Neto Acreditado:** {fmt_monto(res.get('neto_acreditado', 0))}")
                st.markdown("**Descuentos detectados:**")
                for clave, etiqueta in CONCEPTOS_ETIQUETAS.items():
                    val = res.get(clave, 0.0)
                    if val:
                        st.markdown(f"- {etiqueta}: {fmt_monto(val)}")
                if res.get("sin_categorizar_detalle"):
                    st.warning("Conceptos no reconocidos en el PDF:")
                    for item in res["sin_categorizar_detalle"]:
                        st.markdown(f"- `{item['texto']}` → {fmt_monto(item['monto'])}")

    # ── Tab 3: Conceptos sin categorizar ─────────────────────
    with tab_sin_cat:
        conceptos = db.obtener_conceptos_sin_categorizar()
        if not conceptos:
            st.info("No hay conceptos pendientes de categorizar.")
        else:
            st.info(
                f"**{len(conceptos)}** concepto(s) encontrados en PDFs anteriores que no pudieron "
                "identificarse automáticamente. Asignales un concepto para que se reconozcan en el futuro."
            )
            for concepto in conceptos:
                with st.expander(
                    f"{concepto['emisor'].upper()} · {concepto['texto_original'][:55]} · {fmt_monto(concepto['monto'])}"
                ):
                    st.markdown(f"**Emisor:** {concepto['emisor'].upper()}")
                    st.markdown(f"**Texto en el PDF:** `{concepto['texto_original']}`")
                    st.markdown(f"**Monto:** {fmt_monto(concepto['monto'])}")
                    st.markdown(f"**Fecha:** {concepto['fecha']}")
                    st.divider()
                    st.markdown("**¿A qué concepto corresponde?**")
                    with st.form(f"form_cat_{concepto['id']}"):
                        concepto_sel = st.selectbox(
                            "Concepto",
                            options=CONCEPTOS_OPCIONES,
                            key=f"sel_concepto_{concepto['id']}",
                            label_visibility="collapsed",
                        )
                        texto_clave = st.text_input(
                            "Texto a buscar en el PDF (podés ajustarlo)",
                            value=concepto["texto_original"][:50],
                            key=f"texto_clave_{concepto['id']}",
                        )
                        if st.form_submit_button("Asignar concepto"):
                            clave_interna = CONCEPTOS_CLAVES.get(concepto_sel, concepto_sel.lower().replace(" ", "_"))
                            emisores_db = db.obtener_emisores()
                            config_emisor = emisores_db.get(concepto["emisor"], {})
                            descuentos_act = config_emisor.get("descuentos", {})
                            descuentos_act[clave_interna] = {
                                "patron": texto_clave.strip(),
                                "tipo": "unico",
                                "obligatorio": False,
                            }
                            config_emisor["descuentos"] = descuentos_act
                            db.guardar_emisor(concepto["emisor"], config_emisor)
                            db.marcar_concepto_convertido(concepto["id"])
                            st.success(f"Asignado como '{concepto_sel}'. Se usará en futuros PDFs.")
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
