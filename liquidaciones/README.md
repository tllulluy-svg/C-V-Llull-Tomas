# Lector de Liquidaciones de Tarjetas

Herramienta para procesar y consolidar liquidaciones de procesadoras de tarjetas de crédito/débito.

## Emisores soportados
- Fiserv
- Payway
- Naranja X
- Cabal
- Favacard

## Instalación

### Requisitos
- Python 3.10 o superior

### Pasos

1. Descomprimí la carpeta del proyecto

2. Abrí una terminal en la carpeta `liquidaciones/`

3. Instalá las dependencias:

```
pip install -r requirements.txt
```

4. Ejecutá la aplicación:

```
streamlit run app.py
```

5. Se abrirá automáticamente en tu navegador en `http://localhost:8501`

## Uso

### Cargar PDFs
1. Ir a la sección **Cargar PDF**
2. Subir uno o más PDFs de liquidaciones
3. Ingresar el período (MM/AAAA) manualmente
4. Verificar el resumen de cada PDF
5. Confirmar para guardar o descartar

### Ver historial
1. Ir a la sección **Historial**
2. Filtrar por N° de Comercio si es necesario
3. Ver totales consolidados
4. Descargar CSV con el botón de descarga

### Agregar nuevo emisor
1. Ir a **Administración → Agregar nuevo emisor**
2. Completar los campos con las palabras clave del emisor
3. Guardar

## Archivos del proyecto
- `app.py` → interfaz principal
- `extractor.py` → lógica de extracción de PDFs
- `diccionario.py` → palabras clave por emisor
- `database.py` → base de datos SQLite
- `utils.py` → funciones auxiliares
- `liquidaciones.db` → base de datos (se crea automáticamente al iniciar)
