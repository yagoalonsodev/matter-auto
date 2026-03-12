#!/usr/bin/env python3
"""
Convierte archivos del Paso 2 (Colores) al formato Paso 3 (Formatos) para Cerámica.

Lee un Excel del paso 2 y genera un Excel del paso 3. Usa IA (Ollama/DeepSeek)
para mapear correctamente los campos y sugerir la lista de formatos.
Mismas variables en .env que el script Paso 1→2: USE_OLLAMA, OLLAMA_MODEL, api_key_deepseek.
"""

import json
import re
import pandas as pd
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Columnas del Paso 3 (orden)
COLUMNAS_PASO3 = [
    "id",
    "child_id/x_studio_field_qZO8q",
    "name",
    "x_ce_original_series",
    "product_type_id",
    "x_ce_formatos_ids",
]

DEFAULT_FORMATOS = (
    "Cuadrado 60,00x60,00,Rectangular 60,00x120,00,Cuadrado 120,00x120,00,"
    "Rectangular 160,00x320,00,Rectangular 120,00x240,00,Rectangular 30,00x60,00,"
    "Rectangular 120,00x280,00,Rodapié 4,60x60,00"
)


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


def leer_paso2(archivo_entrada):
    """Lee el Excel del paso 2."""
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)
    df = pd.read_excel(archivo_entrada, engine="openpyxl")
    if len(df) == 0:
        print("✗ El archivo del paso 2 no tiene filas.")
        sys.exit(1)
    return df


def paso2_a_texto_para_ia(df_paso2):
    """Convierte el paso 2 a texto (cabeceras + filas con datos) para enviar a la IA."""
    # Solo filas donde hay al menos un valor no nulo en columnas clave
    columnas = list(df_paso2.columns)
    lineas = [",".join(columnas)]
    for _, row in df_paso2.head(20).iterrows():
        vals = [str(v) if pd.notna(v) and str(v).strip() else "" for v in row]
        lineas.append(",".join(vals))
    return "\n".join(lineas)


def obtener_paso3_con_ia(texto_paso2):
    """
    Pide a la IA que mapee los datos del paso 2 al esquema del paso 3
    y que sugiera la lista de formatos. Devuelve dict con los campos del paso 3 o None si falla.
    """
    base_url, api_key, model = obtener_config_ia()
    if base_url is None:
        return None

    if "ollama" in (api_key or "").lower() or (api_key == "ollama"):
        print(f"✓ Usando modelo local Ollama: {model}")
    else:
        print("✓ Usando DeepSeek en la nube.")

    prompt = f"""Tienes datos de un Excel del Paso 2 (Colores) de una colección de cerámica. Debes rellenar UNA fila del Paso 3 (Formatos).

**Datos del Paso 2 (cabecera y filas):**
```
{texto_paso2}
```

En el Paso 2 la primera fila con "name" relleno tiene el nombre de la colección y "x_studio_field_qZO8q" es el fabricante. El resto de filas repiten colores/acabados.

**Esquema del Paso 3 (una sola fila):**
- child_id/x_studio_field_qZO8q = fabricante (tomar de x_studio_field_qZO8q del paso 2)
- name = nombre de la colección (tomar "name" del paso 2)
- x_ce_original_series = serie original (usar el mismo nombre de colección si no hay otro dato)
- product_type_id = "Ceramica"
- x_ce_formatos_ids = lista de formatos de cerámica separados por comas. Ejemplos: "Cuadrado 60,00x60,00", "Rectangular 60,00x120,00", "Cuadrado 120,00x120,00", "Rectangular 120,00x240,00", "Rodapié 4,60x60,00". Devuelve una lista razonable para una colección de cerámica (entre 4 y 10 formatos).

Responde ÚNICAMENTE con un JSON válido, sin markdown ni texto alrededor:
{{
  "child_id/x_studio_field_qZO8q": "<fabricante del paso 2>",
  "name": "<nombre de la colección>",
  "x_ce_original_series": "<nombre o serie>",
  "product_type_id": "Ceramica",
  "x_ce_formatos_ids": "Formato1,Formato2,Formato3,..."
}}
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
        print("Respuesta recibida:", texto[:400])
        return None

    # Asegurar claves del paso 3
    name = data.get("name") or ""
    return {
        "child_id/x_studio_field_qZO8q": data.get("child_id/x_studio_field_qZO8q") or "",
        "name": name,
        "x_ce_original_series": data.get("x_ce_original_series") or name,
        "product_type_id": data.get("product_type_id") or "Ceramica",
        "x_ce_formatos_ids": data.get("x_ce_formatos_ids") or DEFAULT_FORMATOS,
    }


def extraer_coleccion_paso2(df_paso2):
    """Fallback: obtiene nombre y fabricante del paso 2 sin IA."""
    for _, row in df_paso2.iterrows():
        name = row.get("name")
        if pd.notna(name) and str(name).strip():
            x_studio = row.get("x_studio_field_qZO8q")
            return {
                "child_id/x_studio_field_qZO8q": str(x_studio).strip() if pd.notna(x_studio) else "",
                "name": str(name).strip(),
                "x_ce_original_series": str(name).strip(),
                "product_type_id": "Ceramica",
                "x_ce_formatos_ids": DEFAULT_FORMATOS,
            }
    print("✗ No se encontró ninguna fila con 'name' en el paso 2.")
    sys.exit(1)


def generar_paso3(fila_paso3):
    """Genera el DataFrame del paso 3 (una fila)."""
    fila = {
        "id": None,
        "child_id/x_studio_field_qZO8q": fila_paso3["child_id/x_studio_field_qZO8q"],
        "name": fila_paso3["name"],
        "x_ce_original_series": fila_paso3["x_ce_original_series"],
        "product_type_id": fila_paso3["product_type_id"],
        "x_ce_formatos_ids": fila_paso3["x_ce_formatos_ids"],
    }
    return pd.DataFrame([fila])[COLUMNAS_PASO3]


def guardar_paso3(df_paso3, archivo_salida):
    dir_salida = os.path.dirname(archivo_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    df_paso3.to_excel(archivo_salida, index=False, engine="openpyxl")
    print(f"✓ Salida guardada: {archivo_salida}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 convertir_paso2_a_paso3_ceramica.py <paso2.xlsx> [salida.xlsx]")
        print("Ejemplo: python3 convertir_paso2_a_paso3_ceramica.py output/ceramica/02_Colores_desde_csv.xlsx output/ceramica/03_Formatos.xlsx")
        sys.exit(1)

    archivo_entrada = sys.argv[1]
    archivo_salida = (
        sys.argv[2]
        if len(sys.argv) >= 3
        else f"output/ceramica/03_Formatos_{Path(archivo_entrada).stem}.xlsx"
    )

    print("Paso 2 → Paso 3 (Cerámica - Formatos)")
    print("-" * 50)
    df_paso2 = leer_paso2(archivo_entrada)
    print(f"✓ Paso 2 leído: {archivo_entrada} ({len(df_paso2)} filas)")

    texto_paso2 = paso2_a_texto_para_ia(df_paso2)
    fila_paso3 = obtener_paso3_con_ia(texto_paso2)

    if fila_paso3 is None:
        print("✓ Mapeo por defecto (sin IA).")
        fila_paso3 = extraer_coleccion_paso2(df_paso2)
    else:
        print("✓ Mapeo recibido de la IA.")

    df_paso3 = generar_paso3(fila_paso3)
    print(f"✓ Paso 3 generado: 1 fila (colección '{fila_paso3['name']}')")
    guardar_paso3(df_paso3, archivo_salida)
    print("-" * 50)
    print("Listo.")


if __name__ == "__main__":
    main()
