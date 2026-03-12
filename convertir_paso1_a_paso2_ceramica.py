#!/usr/bin/env python3
"""
Convierte archivos del Paso 1 (Colecciones) al formato Paso 2 (Colores) para Cerámica.

Acepta entrada en CSV o Excel (.xlsx). Usa IA para mapear los campos al esquema correcto.
Puedes usar:
  - Modelo local con Ollama: en .env pon USE_OLLAMA=1 y opcionalmente OLLAMA_MODEL=deepseek-coder:6.7b
  - DeepSeek en la nube: en .env pon api_key_deepseek=tu_key
Salida siempre en Excel (.xlsx) con el formato del paso 2.
"""

import json
import re
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Cargar variables de .env
load_dotenv()

# Columnas del Paso 1 (esquema destino)
COLUMNAS_PASO1 = [
    "id",
    "name",
    "product_type_id",
    "x_studio_field_qZO8q",
    "x_ce_original_series",
]

# Columnas del Paso 2 (orden final)
COLUMNAS_PASO2 = [
    "id",
    "x_ce_collection_appearance",
    "x_studio_field_qZO8q",
    "name",
    "x_ce_collection_typologies",
    "x_ce_color_ids/x_ce_color_revestimiento",
    "x_ce_color_ids/x_ce_tipologia",
    "x_ce_color_ids/x_ce_acabados_ids/x_acabados_id",
    "x_ce_color_ids/x_colormatch",
]

# Colores por defecto si la IA no devuelve ninguno
DEFAULT_COLORES = [
    {"color_revestimiento": "Blanco", "colormatch": "White", "acabado_inicial": "Natural"},
    {"color_revestimiento": "Negro", "colormatch": "Black"},
    {"color_revestimiento": "Wave", "colormatch": "Wave"},
    {"color_revestimiento": "Fragment", "colormatch": "Fragment"},
    {"color_revestimiento": "Breach", "colormatch": "Breach"},
    {"color_revestimiento": "Peble", "colormatch": "Peble"},
    {"color_revestimiento": "Flow", "colormatch": "Flow"},
    {"color_revestimiento": "Fall", "colormatch": "Fall"},
]


def leer_csv_raw(archivo_entrada):
    """Lee el CSV y devuelve (DataFrame raw, texto para la IA)."""
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)

    df = None
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        for sep in (",", ";", "\t"):
            try:
                df = pd.read_csv(archivo_entrada, sep=sep, encoding=encoding)
                if len(df.columns) >= 1:
                    break
            except Exception:
                df = None
                continue
        if df is not None and len(df.columns) >= 1:
            break
    if df is None:
        df = pd.read_csv(archivo_entrada, sep=",", encoding="utf-8")

    df.columns = df.columns.str.strip()
    if len(df) == 0:
        print("✗ El archivo no tiene filas de datos.")
        sys.exit(1)

    # Texto para enviar a la IA: cabeceras + primeras filas
    lineas = [",".join(df.columns)]
    for _, row in df.head(5).iterrows():
        lineas.append(",".join(str(v) if pd.notna(v) else "" for v in row))
    texto_csv = "\n".join(lineas)

    return df, texto_csv


def leer_excel_raw(archivo_entrada):
    """Lee el Excel y devuelve (DataFrame, texto para la IA)."""
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)
    df = pd.read_excel(archivo_entrada, engine="openpyxl")
    df.columns = df.columns.str.strip()
    if len(df) == 0:
        print("✗ El archivo no tiene filas de datos.")
        sys.exit(1)
    lineas = [",".join(df.columns)]
    for _, row in df.head(5).iterrows():
        lineas.append(",".join(str(v) if pd.notna(v) else "" for v in row))
    texto_csv = "\n".join(lineas)
    return df, texto_csv


def _llamada_ia(base_url, api_key, model, prompt):
    """Llama al modelo (Ollama local o DeepSeek en la nube)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Eres un asistente que solo responde con JSON válido, sin explicaciones ni markdown.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    return response.choices[0].message.content.strip()


def obtener_mapeo_con_deepseek(texto_csv):
    """
    Pide a la IA (Ollama local o DeepSeek en la nube) que mapee las columnas del CSV
    al esquema Paso 1/Paso 2 y que sugiera colores. Devuelve (mapeo, appearance, typology, colores).
    """
    use_ollama = os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes")
    ollama_model = os.getenv("OLLAMA_MODEL", "deepseek-coder:6.7b")

    if use_ollama:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        api_key = "ollama"  # Ollama no lo usa, pero el cliente lo pide
        model = ollama_model
        print(f"✓ Usando modelo local Ollama: {model}")
    else:
        api_key = os.getenv("api_key_deepseek") or os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            print("✗ Falta la API key de DeepSeek. Pon api_key_deepseek en .env o usa USE_OLLAMA=1 para modelo local.")
            sys.exit(1)
        base_url = "https://api.deepseek.com"
        model = "deepseek-chat"
        print("✓ Usando DeepSeek en la nube.")

    esquema_paso1 = ", ".join(COLUMNAS_PASO1)
    esquema_paso2_colores = "color_revestimiento, colormatch, tipologia (ej: Polivalente), acabado_inicial (Natural solo el primero, luego Mate)"

    prompt = f"""Eres un asistente que mapea datos de un CSV de colecciones de cerámica al esquema de importación.

**Datos del CSV (cabecera y primeras filas):**
```
{texto_csv}
```

**Esquema destino Paso 1 (columnas que debemos rellenar):**
{esquema_paso1}

- name = nombre de la colección
- product_type_id = tipo de producto (ej: Ceramica)
- x_studio_field_qZO8q = fabricante / marca
- x_ce_original_series = serie original (puede ser igual que name si no hay)

**Para el Paso 2 además necesitamos:**
- x_ce_collection_appearance: apariencia (ej: Mármol, Piedra, Madera, etc.)
- x_ce_collection_typologies: tipología (ej: Polivalente)
- colores: lista de objetos con: {esquema_paso2_colores}. El primer color debe tener acabado_inicial "Natural"; el resto "Mate". Para cada color se generan 2 filas (Mate/Natural + Brillante).

Responde ÚNICAMENTE con un JSON válido, sin markdown ni texto alrededor, con esta estructura exacta:
{{
  "mapping": {{
    "name": "<nombre exacto de la columna del CSV para el nombre de colección>",
    "product_type_id": "<columna o valor fijo ej: Ceramica>",
    "x_studio_field_qZO8q": "<columna para fabricante>",
    "x_ce_original_series": "<columna para serie o nombre>"
  }},
  "x_ce_collection_appearance": "Mármol",
  "x_ce_collection_typologies": "Polivalente",
  "colores": [
    {{ "color_revestimiento": "...", "colormatch": "...", "acabado_inicial": "Natural" }},
    {{ "color_revestimiento": "...", "colormatch": "..." }}
  ]
}}

Si en el CSV no ves información de colores, inventa una lista razonable (Blanco/White, Negro/Black, etc.) con al menos 4 colores. El primer color debe tener acabado_inicial "Natural". Los demás no incluyas acabado_inicial (se usará Mate).
Responde solo el JSON."""

    try:
        texto = _llamada_ia(base_url, api_key, model, prompt)
    except Exception as e:
        print(f"⚠ IA no disponible ({e}). Usando mapeo por defecto.")
        return None

    # Extraer JSON (por si viene envuelto en ```json ... ```)
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto)
    if json_match:
        texto = json_match.group(1).strip()
    texto = texto.strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"✗ La IA no devolvió JSON válido: {e}")
        print("Respuesta recibida:", texto[:500])
        sys.exit(1)

    mapping = data.get("mapping") or {}
    appearance = data.get("x_ce_collection_appearance") or "Mármol"
    typology = data.get("x_ce_collection_typologies") or "Polivalente"
    colores = data.get("colores")
    if not colores or not isinstance(colores, list):
        colores = DEFAULT_COLORES

    # Normalizar colores: primer elemento con acabado_inicial Natural si no está
    for i, c in enumerate(colores):
        if not isinstance(c, dict):
            colores[i] = {"color_revestimiento": str(c), "colormatch": str(c)}
        if "acabado_inicial" not in c:
            c["acabado_inicial"] = "Natural" if i == 0 else "Mate"
    if colores and colores[0].get("acabado_inicial") != "Natural":
        colores[0]["acabado_inicial"] = "Natural"

    return mapping, appearance, typology, colores


def mapeo_por_defecto(columnas_csv):
    """Mapeo heurístico cuando DeepSeek no está disponible."""
    col_lower = {c.strip().lower(): c for c in columnas_csv}
    m = {}
    if "name" in columnas_csv:
        m["name"] = "name"
    elif "nombre" in col_lower:
        m["name"] = col_lower["nombre"]
    elif "collection" in col_lower:
        m["name"] = col_lower["collection"]
    else:
        m["name"] = columnas_csv[0] if columnas_csv else "name"

    if "x_studio_field_qzo8q" in col_lower:
        m["x_studio_field_qZO8q"] = col_lower["x_studio_field_qzo8q"]
    elif "fabricante" in col_lower:
        m["x_studio_field_qZO8q"] = col_lower["fabricante"]
    else:
        m["x_studio_field_qZO8q"] = columnas_csv[1] if len(columnas_csv) > 1 else ""

    if "product_type_id" in columnas_csv:
        m["product_type_id"] = "product_type_id"
    elif "product_type" in col_lower:
        m["product_type_id"] = col_lower["product_type"]
    else:
        m["product_type_id"] = "Ceramica"

    if "x_ce_original_series" in columnas_csv:
        m["x_ce_original_series"] = "x_ce_original_series"
    elif "original_series" in col_lower:
        m["x_ce_original_series"] = col_lower["original_series"]
    else:
        m["x_ce_original_series"] = m.get("name", "name")

    return m


def aplicar_mapeo(df_raw, mapping):
    """Construye un DataFrame normalizado (Paso 1) aplicando el mapeo de columnas."""
    filas = []
    for _, row in df_raw.iterrows():
        fila = {}
        for target_col in COLUMNAS_PASO1:
            source = mapping.get(target_col)
            if source is None:
                fila[target_col] = None
                continue
            if source in df_raw.columns:
                fila[target_col] = row.get(source)
            else:
                # Valor fijo (ej: "Ceramica")
                fila[target_col] = source
        filas.append(fila)
    return pd.DataFrame(filas)


def generar_paso2(df_paso1, colores, appearance, typology):
    """Genera el DataFrame del Paso 2 a partir del Paso 1 y la lista de colores."""
    coleccion = df_paso1.iloc[0]
    name = coleccion.get("name", "")
    x_studio = coleccion.get("x_studio_field_qZO8q", "")

    filas = []
    for idx, color_data in enumerate(colores):
        color_rev = color_data.get("color_revestimiento", "")
        colormatch = color_data.get("colormatch", "")
        tipologia_color = color_data.get("tipologia", typology)
        acabado = color_data.get("acabado_inicial", "Mate")

        fila_color = {
            "id": None,
            "x_ce_collection_appearance": appearance if idx == 0 else None,
            "x_studio_field_qZO8q": x_studio if idx == 0 else None,
            "name": name if idx == 0 else None,
            "x_ce_collection_typologies": typology if idx == 0 else None,
            "x_ce_color_ids/x_ce_color_revestimiento": color_rev,
            "x_ce_color_ids/x_ce_tipologia": tipologia_color,
            "x_ce_color_ids/x_ce_acabados_ids/x_acabados_id": acabado,
            "x_ce_color_ids/x_colormatch": colormatch,
        }
        filas.append(fila_color)

        fila_brillante = {
            "id": None,
            "x_ce_collection_appearance": None,
            "x_studio_field_qZO8q": None,
            "name": None,
            "x_ce_collection_typologies": None,
            "x_ce_color_ids/x_ce_color_revestimiento": None,
            "x_ce_color_ids/x_ce_tipologia": None,
            "x_ce_color_ids/x_ce_acabados_ids/x_acabados_id": "Brillante",
            "x_ce_color_ids/x_colormatch": None,
        }
        filas.append(fila_brillante)

    return pd.DataFrame(filas)[COLUMNAS_PASO2]


def carpeta_timestamp():
    """Carpeta con timestamp: output/ceramica/YYYYMMDD_HHMMSS/. Si existe env OUTPUT_CARPETA se usa esa."""
    return os.getenv("OUTPUT_CARPETA") or os.path.join("output", "ceramica", datetime.now().strftime("%Y%m%d_%H%M%S"))


def slug_nombremarca(nombre):
    """Convierte nombre de marca/colección a slug para el archivo (sin espacios ni caracteres raros)."""
    if not nombre or not str(nombre).strip():
        return "salida"
    s = re.sub(r"[^a-zA-Z0-9\u00C0-\u024F]+", "_", str(nombre).strip())
    return (s.strip("_")[:50]) or "salida"


def guardar_paso2(df_paso2, archivo_salida):
    dir_salida = os.path.dirname(archivo_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    df_paso2.to_excel(archivo_salida, index=False, engine="openpyxl")
    print(f"✓ Salida guardada: {archivo_salida}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 convertir_paso1_a_paso2_ceramica.py <entrada.csv|.xlsx> [salida.xlsx]")
        print("Ejemplo: python3 convertir_paso1_a_paso2_ceramica.py mi_coleccion.csv")
        sys.exit(1)

    archivo_entrada = sys.argv[1]

    sufijo = Path(archivo_entrada).suffix.lower()
    if sufijo == ".csv":
        df_raw, texto_csv = leer_csv_raw(archivo_entrada)
    else:
        df_raw, texto_csv = leer_excel_raw(archivo_entrada)

    print(f"✓ Entrada leída: {archivo_entrada} ({len(df_raw)} fila(s))")
    print("✓ Pidiendo a DeepSeek el mapeo de campos...")

    result = obtener_mapeo_con_deepseek(texto_csv)
    if result is None:
        mapping = mapeo_por_defecto(list(df_raw.columns))
        appearance, typology = "Mármol", "Polivalente"
        colores = [
            {**c, "acabado_inicial": "Natural" if i == 0 else c.get("acabado_inicial", "Mate")}
            for i, c in enumerate(DEFAULT_COLORES)
        ]
        print("✓ Mapeo por defecto aplicado.")
    else:
        mapping, appearance, typology, colores = result
        print("✓ Mapeo recibido de la IA.")

    df_paso1 = aplicar_mapeo(df_raw, mapping)
    df_paso2 = generar_paso2(df_paso1, colores, appearance, typology)
    print(f"✓ Paso 2 generado: {len(df_paso2)} filas")

    # Carpeta con timestamp y nombre de archivo con _nombremarca
    carpeta = carpeta_timestamp()
    os.makedirs(carpeta, exist_ok=True)
    nombremarca = slug_nombremarca(df_paso1.iloc[0].get("name", ""))
    if len(sys.argv) >= 3:
        base = Path(sys.argv[2]).stem
    else:
        base = "02_Colores"
    archivo_salida = os.path.join(carpeta, f"{base}_{nombremarca}.xlsx")
    guardar_paso2(df_paso2, archivo_salida)
    print("Listo.")


if __name__ == "__main__":
    main()
