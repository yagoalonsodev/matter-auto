#!/usr/bin/env python3
"""
Convierte archivos del Paso 3 (Formatos) al formato Paso 4 (Productos) para Cerámica.

Lee un Excel del paso 3 y genera un Excel del paso 4. Usa IA (Ollama/DeepSeek)
para mapear correctamente los campos del producto.
Mismas variables en .env: USE_OLLAMA, OLLAMA_MODEL, api_key_deepseek.
"""

import json
import re
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# Columnas del Paso 4 (orden del template)
COLUMNAS_PASO4 = [
    "id",
    "detailed_type",
    "public_category_id",
    "uom_id",
    "uom_po_id",
    "x_product_grcost",
    "ce_product_m2box",
    "x_original_reference",
    "x_original_code",
    "x_product_typology",
    "x_product_matter",
    "x_producto_color",
    "x_producto_formato",
    "x_producto_acabado",
    "list_price",
    "standard_price",
    "public_categ_ids",
    "x_product_name_desc",
    "x_product_froz",
    "x_product_grip",
    "x_product_thick",
    "x_product_grout",
    "x_product_mos",
    "x_product_precut",
    "x_product_relief",
    "x_product_texture",
    "x_product_rect",
    "x_product_detonation",
    "image_1920",
]


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
        max_tokens=4000,
    )
    return response.choices[0].message.content.strip()


def obtener_config_ia():
    """Devuelve (base_url, api_key, model) según .env (Ollama o DeepSeek)."""
    use_ollama = os.getenv("USE_OLLAMA", "").lower() in ("1", "true", "yes")
    if use_ollama:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        return base_url, "ollama", os.getenv("OLLAMA_MODEL", "deepseek-coder:6.7b")
    api_key = os.getenv("api_key_deepseek") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None, None, None
    return "https://api.deepseek.com", api_key, "deepseek-chat"


def leer_paso3(archivo_entrada):
    """Lee el Excel del paso 3."""
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)
    df = pd.read_excel(archivo_entrada, engine="openpyxl")
    if len(df) == 0:
        print("✗ El archivo del paso 3 no tiene filas.")
        sys.exit(1)
    return df


def paso3_a_texto_para_ia(df_paso3):
    """Convierte el paso 3 a texto para la IA."""
    row = df_paso3.iloc[0]
    lineas = []
    for c in df_paso3.columns:
        v = row.get(c)
        lineas.append(f"{c}: {v}")
    return "\n".join(lineas)


def obtener_paso4_con_ia(texto_paso3):
    """
    Pide a la IA que rellene una fila del Paso 4 (producto) a partir del Paso 3.
    Devuelve dict con las claves de Paso 4 o None si falla.
    """
    base_url, api_key, model = obtener_config_ia()
    if base_url is None:
        return None

    if (api_key or "").lower() == "ollama":
        print(f"✓ Usando modelo local Ollama: {model}")
    else:
        print("✓ Usando DeepSeek en la nube.")

    columnas_str = ", ".join(f'"{c}"' for c in COLUMNAS_PASO4)

    prompt = f"""Tienes una fila del Paso 3 (Formatos de una colección de cerámica). Debes rellenar UNA fila del Paso 4 (Producto / ficha de producto).

**Datos del Paso 3:**
```
{texto_paso3}
```

**Columnas del Paso 4 que debes rellenar (todas en el JSON):**
{columnas_str}

**Instrucciones:**
- name del P3 → public_category_id y base para x_original_reference
- child_id/x_studio_field_qZO8q = fabricante (puede aparecer en referencia o código)
- x_ce_formatos_ids es una lista de formatos separados por comas; elige UN formato para x_producto_formato (ej: "Cuadrado 60,00x60,00")
- Rellena x_original_reference como: "<nombre colección> - <color o código> - <formato> - <espesor>" (ej: "Florim - B&W - Blanco - 60,00x60,00 - 6mm")
- x_product_typology: Polivalente; x_product_matter: Porcelánico esmaltado (o similar); detailed_type: Almacenable; uom_id y uom_po_id: m2
- list_price, standard_price, ce_product_m2box: números (pueden ser 0 o ejemplos); x_original_code: número
- x_product_froz, x_product_mos, x_product_precut, x_product_relief, x_product_texture: boolean true/false; x_product_rect: true
- x_product_thick: número (ej 6.0); x_product_grip: "Clase 2"; x_product_grout: "2mm"
- id, public_categ_ids, image_1920, x_product_detonation: null o vacío si no aplica
- x_producto_color, x_producto_acabado: valores razonables para cerámica (ej Antracita, R+Ptv)

Responde ÚNICAMENTE con un JSON de un solo objeto con todas las claves del Paso 4. Usa null para campos vacíos.
Claves exactas: id, detailed_type, public_category_id, uom_id, uom_po_id, x_product_grcost, ce_product_m2box, x_original_reference, x_original_code, x_product_typology, x_product_matter, x_producto_color, x_producto_formato, x_producto_acabado, list_price, standard_price, public_categ_ids, x_product_name_desc, x_product_froz, x_product_grip, x_product_thick, x_product_grout, x_product_mos, x_product_precut, x_product_relief, x_product_texture, x_product_rect, x_product_detonation, image_1920
Responde solo el JSON."""

    try:
        texto = _llamada_ia(base_url, api_key, model, prompt)
    except Exception as e:
        print(f"⚠ IA no disponible ({e}). Usando mapeo por defecto.")
        return None

    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", texto)
    if json_match:
        texto = json_match.group(1).strip()
    texto = texto.strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        print(f"✗ La IA no devolvió JSON válido: {e}")
        print("Respuesta recibida:", texto[:500])
        return None

    return data


def fila_paso4_desde_paso3(df_paso3):
    """Fallback: construye una fila de Paso 4 a partir del Paso 3 sin IA."""
    r = df_paso3.iloc[0]
    name = str(r.get("name", "") or "").strip()
    fabricante = str(r.get("child_id/x_studio_field_qZO8q", "") or "").strip()
    formatos = str(r.get("x_ce_formatos_ids", "") or "").strip()
    primer_formato = formatos.split(",")[0].strip() if formatos else ""

    return {
        "id": None,
        "detailed_type": "Almacenable",
        "public_category_id": name,
        "uom_id": "m2",
        "uom_po_id": "m2",
        "x_product_grcost": "",
        "ce_product_m2box": 0.0,
        "x_original_reference": f"{name} - {primer_formato} - 6mm" if name else "",
        "x_original_code": None,
        "x_product_typology": "Polivalente",
        "x_product_matter": "Porcelánico esmaltado",
        "x_producto_color": "",
        "x_producto_formato": primer_formato,
        "x_producto_acabado": "",
        "list_price": 0.0,
        "standard_price": 0.0,
        "public_categ_ids": None,
        "x_product_name_desc": "",
        "x_product_froz": True,
        "x_product_grip": "Clase 2",
        "x_product_thick": 6.0,
        "x_product_grout": "2mm",
        "x_product_mos": False,
        "x_product_precut": False,
        "x_product_relief": False,
        "x_product_texture": False,
        "x_product_rect": True,
        "x_product_detonation": None,
        "image_1920": None,
    }


def normalizar_fila_paso4(data):
    """Asegura tipos correctos y todas las columnas."""
    if not isinstance(data, dict):
        data = {}
    fila = {}
    for c in COLUMNAS_PASO4:
        v = data.get(c)
        if v is None:
            fila[c] = None
            continue
        if c in ("list_price", "standard_price", "ce_product_m2box", "x_product_thick"):
            try:
                fila[c] = float(v)
            except (TypeError, ValueError):
                fila[c] = 0.0
        elif c in ("x_product_froz", "x_product_mos", "x_product_precut", "x_product_relief", "x_product_texture", "x_product_rect"):
            fila[c] = bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "yes", "sí")
        elif c == "x_original_code" and v is not None:
            try:
                s = str(v).strip()
                fila[c] = int(float(v)) if s and s not in ("nan", "None") else None
            except (TypeError, ValueError):
                fila[c] = None
        else:
            try:
                if v is None:
                    fila[c] = None
                elif hasattr(v, "shape") and getattr(v, "shape", None):
                    fila[c] = None
                elif pd.isna(v):
                    fila[c] = None
                else:
                    s = str(v).strip()
                    fila[c] = v if s and s.lower() not in ("nan", "none") else None
            except Exception:
                fila[c] = None
    return fila


def generar_paso4(fila_dict):
    """Genera el DataFrame del paso 4 (una fila)."""
    fila = normalizar_fila_paso4(fila_dict)
    return pd.DataFrame([fila])[COLUMNAS_PASO4]


def carpeta_timestamp():
    """Carpeta con timestamp. Si existe env OUTPUT_CARPETA se usa esa."""
    return os.getenv("OUTPUT_CARPETA") or os.path.join("output", "ceramica", datetime.now().strftime("%Y%m%d_%H%M%S"))


def slug_nombremarca(nombre):
    """Convierte nombre de marca/colección a slug para el archivo."""
    if not nombre or not str(nombre).strip():
        return "salida"
    s = re.sub(r"[^a-zA-Z0-9\u00C0-\u024F]+", "_", str(nombre).strip())
    return (s.strip("_")[:50]) or "salida"


def guardar_paso4(df_paso4, archivo_salida):
    dir_salida = os.path.dirname(archivo_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    df_paso4.to_excel(archivo_salida, index=False, engine="openpyxl")
    print(f"✓ Salida guardada: {archivo_salida}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 convertir_paso3_a_paso4_ceramica.py <paso3.xlsx> [salida.xlsx]")
        print("Ejemplo: python3 convertir_paso3_a_paso4_ceramica.py output/ceramica/03_Formatos.xlsx")
        sys.exit(1)

    archivo_entrada = sys.argv[1]

    print("Paso 3 → Paso 4 (Cerámica - Productos)")
    print("-" * 50)
    df_paso3 = leer_paso3(archivo_entrada)
    print(f"✓ Paso 3 leído: {archivo_entrada} ({len(df_paso3)} fila(s))")

    texto_paso3 = paso3_a_texto_para_ia(df_paso3)
    fila_paso4 = obtener_paso4_con_ia(texto_paso3)

    if fila_paso4 is None:
        print("✓ Mapeo por defecto (sin IA).")
        fila_paso4 = fila_paso4_desde_paso3(df_paso3)
    else:
        print("✓ Mapeo recibido de la IA.")

    df_paso4 = generar_paso4(fila_paso4)
    print(f"✓ Paso 4 generado: 1 fila (producto)")

    carpeta = carpeta_timestamp()
    os.makedirs(carpeta, exist_ok=True)
    nombremarca = slug_nombremarca(
        fila_paso4.get("public_category_id") or fila_paso4.get("name") or df_paso3.iloc[0].get("name", "")
    )
    base = Path(sys.argv[2]).stem if len(sys.argv) >= 3 else "04_Producto"
    archivo_salida = os.path.join(carpeta, f"{base}_{nombremarca}.xlsx")
    guardar_paso4(df_paso4, archivo_salida)
    print("-" * 50)
    print("Listo.")


if __name__ == "__main__":
    main()
