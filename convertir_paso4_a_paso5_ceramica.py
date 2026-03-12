#!/usr/bin/env python3
"""
Convierte archivos del Paso 4 (Productos) al formato Paso 5 (Compra) para Cerámica.

Lee un Excel del paso 4 y genera un Excel del paso 5. Usa IA (Ollama/DeepSeek)
para mapear correctamente los campos de compra/proveedor.
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

# Columnas del Paso 5 (orden del template)
COLUMNAS_PASO5 = [
    "id",
    "x_original_reference",
    "seller_ids/partner_id",
    "detailed_type",
    "seller_ids/company_id/name",
    "seller_ids/x_studio_field_bnrc7/id",
    "seller_ids/x_studio_field_bnrc7/x_name",
    "seller_ids/product_code",
    "seller_ids/product_name",
    "seller_ids/min_qty",
    "seller_ids/currency_id",
    "seller_ids/compute_price",
    "seller_ids/x_price",
    "seller_ids/delay",
    "seller_ids/company_id/id",
    "x_product_grcost",
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


def leer_paso4(archivo_entrada):
    """Lee el Excel del paso 4."""
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)
    df = pd.read_excel(archivo_entrada, engine="openpyxl")
    if len(df) == 0:
        print("✗ El archivo del paso 4 no tiene filas.")
        sys.exit(1)
    return df


def paso4_a_texto_para_ia(df_paso4):
    """Convierte el paso 4 a texto para la IA."""
    row = df_paso4.iloc[0]
    lineas = []
    for c in df_paso4.columns:
        v = row.get(c)
        lineas.append(f"{c}: {v}")
    return "\n".join(lineas)


def obtener_paso5_con_ia(texto_paso4):
    """
    Pide a la IA que rellene una fila del Paso 5 (Compra) a partir del Paso 4.
    Devuelve dict con las claves de Paso 5 o None si falla.
    """
    base_url, api_key, model = obtener_config_ia()
    if base_url is None:
        return None

    if (api_key or "").lower() == "ollama":
        print(f"✓ Usando modelo local Ollama: {model}")
    else:
        print("✓ Usando DeepSeek en la nube.")

    columnas_str = ", ".join(f'"{c}"' for c in COLUMNAS_PASO5)

    prompt = f"""Tienes una fila del Paso 4 (Producto de cerámica). Debes rellenar UNA fila del Paso 5 (Compra / datos de proveedor).

**Datos del Paso 4:**
```
{texto_paso4}
```

**Columnas del Paso 5 que debes rellenar (todas en el JSON):**
{columnas_str}

**Instrucciones:**
- x_original_reference: copiar del Paso 4 (referencia del producto)
- seller_ids/partner_id: nombre del proveedor/fabricante (puede ser public_category_id o fabricante del contexto)
- detailed_type: "Almacenable"
- seller_ids/company_id/name: nombre de la empresa compradora (ej: "Matter Atelier, S.L" o similar)
- seller_ids/x_studio_field_bnrc7/id y x_name: null si no hay
- seller_ids/product_code: código de producto (x_original_code del P4 o número)
- seller_ids/product_name: igual que x_original_reference
- seller_ids/min_qty: 0
- seller_ids/currency_id: "EUR"
- seller_ids/compute_price: precio (list_price del P4 o un número ejemplo)
- seller_ids/x_price: 0
- seller_ids/delay: días de entrega (ej: 15)
- seller_ids/company_id/id: "base.main_company"
- x_product_grcost: código de coste (x_product_grcost del P4 si existe, o inventado)
- id: null o dejar vacío

Responde ÚNICAMENTE con un JSON de un solo objeto con todas las claves del Paso 5. Usa null para campos vacíos.
Claves exactas: id, x_original_reference, seller_ids/partner_id, detailed_type, seller_ids/company_id/name, seller_ids/x_studio_field_bnrc7/id, seller_ids/x_studio_field_bnrc7/x_name, seller_ids/product_code, seller_ids/product_name, seller_ids/min_qty, seller_ids/currency_id, seller_ids/compute_price, seller_ids/x_price, seller_ids/delay, seller_ids/company_id/id, x_product_grcost
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

    # Rellenar campos que la IA pueda dejar null (valores por defecto)
    if not data.get("x_original_reference") and "x_original_reference" in [k for k in data]:
        pass  # ya está en data
    if not data.get("seller_ids/currency_id"):
        data["seller_ids/currency_id"] = "EUR"
    if data.get("seller_ids/min_qty") is None:
        data["seller_ids/min_qty"] = 0
    if data.get("seller_ids/x_price") is None:
        data["seller_ids/x_price"] = 0
    if data.get("seller_ids/delay") is None:
        data["seller_ids/delay"] = 15
    if not data.get("seller_ids/company_id/id"):
        data["seller_ids/company_id/id"] = "base.main_company"
    if data.get("detailed_type") is None or data.get("detailed_type") == "":
        data["detailed_type"] = "Almacenable"
    return data


def fila_paso5_desde_paso4(df_paso4):
    """Fallback: construye una fila de Paso 5 a partir del Paso 4 sin IA."""
    r = df_paso4.iloc[0]
    ref = str(r.get("x_original_reference", "") or "").strip()
    partner = str(r.get("public_category_id", "") or "").strip()
    grcost = str(r.get("x_product_grcost", "") or "").strip()
    code = r.get("x_original_code")
    list_price = r.get("list_price")
    try:
        code = int(float(code)) if code is not None and str(code).strip() and str(code).lower() not in ("nan", "none") else 0
    except (TypeError, ValueError):
        code = 0
    try:
        price = float(list_price) if list_price is not None else 0.0
    except (TypeError, ValueError):
        price = 0.0

    return {
        "id": None,
        "x_original_reference": ref or "Producto",
        "seller_ids/partner_id": partner or "Proveedor",
        "detailed_type": "Almacenable",
        "seller_ids/company_id/name": "Matter Atelier, S.L",
        "seller_ids/x_studio_field_bnrc7/id": None,
        "seller_ids/x_studio_field_bnrc7/x_name": None,
        "seller_ids/product_code": code,
        "seller_ids/product_name": ref or "Producto",
        "seller_ids/min_qty": 0,
        "seller_ids/currency_id": "EUR",
        "seller_ids/compute_price": price,
        "seller_ids/x_price": 0,
        "seller_ids/delay": 15,
        "seller_ids/company_id/id": "base.main_company",
        "x_product_grcost": grcost or "",
    }


def normalizar_fila_paso5(data):
    """Asegura tipos correctos y todas las columnas."""
    if not isinstance(data, dict):
        data = {}
    fila = {}
    for c in COLUMNAS_PASO5:
        v = data.get(c)
        if v is None:
            fila[c] = None
            continue
        if c in ("seller_ids/min_qty", "seller_ids/x_price", "seller_ids/delay"):
            try:
                fila[c] = int(float(v))
            except (TypeError, ValueError):
                fila[c] = 0
        elif c == "seller_ids/product_code":
            try:
                s = str(v).strip()
                fila[c] = int(float(v)) if s and s.lower() not in ("nan", "none") else 0
            except (TypeError, ValueError):
                fila[c] = 0
        elif c == "seller_ids/compute_price":
            try:
                fila[c] = float(v)
            except (TypeError, ValueError):
                fila[c] = 0.0
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


def generar_paso5(fila_dict):
    """Genera el DataFrame del paso 5 (una fila)."""
    fila = normalizar_fila_paso5(fila_dict)
    return pd.DataFrame([fila])[COLUMNAS_PASO5]


def carpeta_timestamp():
    """Carpeta con timestamp. Si existe env OUTPUT_CARPETA se usa esa."""
    return os.getenv("OUTPUT_CARPETA") or os.path.join("output", "ceramica", datetime.now().strftime("%Y%m%d_%H%M%S"))


def slug_nombremarca(nombre):
    """Convierte nombre a slug para el archivo."""
    if not nombre or not str(nombre).strip():
        return "salida"
    s = re.sub(r"[^a-zA-Z0-9\u00C0-\u024F]+", "_", str(nombre).strip())
    return (s.strip("_")[:50]) or "salida"


def guardar_paso5(df_paso5, archivo_salida):
    dir_salida = os.path.dirname(archivo_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    df_paso5.to_excel(archivo_salida, index=False, engine="openpyxl")
    print(f"✓ Salida guardada: {archivo_salida}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 convertir_paso4_a_paso5_ceramica.py <paso4.xlsx> [salida.xlsx]")
        print("Ejemplo: python3 convertir_paso4_a_paso5_ceramica.py output/ceramica/04_Producto.xlsx")
        sys.exit(1)

    archivo_entrada = sys.argv[1]

    print("Paso 4 → Paso 5 (Cerámica - Compra)")
    print("-" * 50)
    df_paso4 = leer_paso4(archivo_entrada)
    print(f"✓ Paso 4 leído: {archivo_entrada} ({len(df_paso4)} fila(s))")

    texto_paso4 = paso4_a_texto_para_ia(df_paso4)
    fila_paso5 = obtener_paso5_con_ia(texto_paso4)

    if fila_paso5 is None:
        print("✓ Mapeo por defecto (sin IA).")
        fila_paso5 = fila_paso5_desde_paso4(df_paso4)
    else:
        print("✓ Mapeo recibido de la IA.")
        # Rellenar huecos con datos del Paso 4
        fallback = fila_paso5_desde_paso4(df_paso4)
        for k in fallback:
            if fila_paso5.get(k) is None or (isinstance(fila_paso5.get(k), str) and not fila_paso5.get(k).strip()):
                fila_paso5[k] = fallback[k]

    df_paso5 = generar_paso5(fila_paso5)
    print(f"✓ Paso 5 generado: 1 fila (compra)")

    carpeta = carpeta_timestamp()
    os.makedirs(carpeta, exist_ok=True)
    nombremarca = slug_nombremarca(
        fila_paso5.get("seller_ids/partner_id") or fila_paso5.get("x_original_reference") or df_paso4.iloc[0].get("public_category_id", "")
    )
    base = Path(sys.argv[2]).stem if len(sys.argv) >= 3 else "05_Compra"
    archivo_salida = os.path.join(carpeta, f"{base}_{nombremarca}.xlsx")
    guardar_paso5(df_paso5, archivo_salida)
    print("-" * 50)
    print("Listo.")


if __name__ == "__main__":
    main()
