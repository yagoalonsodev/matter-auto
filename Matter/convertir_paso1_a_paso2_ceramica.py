#!/usr/bin/env python3
"""
Convierte archivos del Paso 1 (Colecciones) al formato Paso 2 (Colores) para Cerámica.

Acepta entrada en CSV o Excel (.xlsx).
Salida siempre en Excel (.xlsx) con el formato del paso 2.
"""

import pandas as pd
import sys
import os
from pathlib import Path


# Columnas esperadas en el paso 1 (CSV o Excel)
COLUMNAS_PASO1 = [
    'id', 'name', 'product_type_id', 'x_studio_field_qZO8q', 'x_ce_original_series'
]

# Valores por defecto para el paso 2 (personalizables)
DEFAULT_APPEARANCE = "Mármol"
DEFAULT_TIPOLOGIA = "Polivalente"

# Colores por defecto si no se pasan en un archivo de configuración
DEFAULT_COLORES = [
    {'color_revestimiento': 'Blanco', 'colormatch': 'White', 'acabado_inicial': 'Natural'},
    {'color_revestimiento': 'Negro', 'colormatch': 'Black'},
    {'color_revestimiento': 'Wave', 'colormatch': 'Wave'},
    {'color_revestimiento': 'Fragment', 'colormatch': 'Fragment'},
    {'color_revestimiento': 'Breach', 'colormatch': 'Breach'},
    {'color_revestimiento': 'Peble', 'colormatch': 'Peble'},
    {'color_revestimiento': 'Flow', 'colormatch': 'Flow'},
    {'color_revestimiento': 'Fall', 'colormatch': 'Fall'},
]


def leer_paso1(archivo_entrada):
    """
    Lee el archivo del paso 1 (CSV o Excel).
    """
    path = Path(archivo_entrada)
    if not path.exists():
        print(f"✗ No existe el archivo: {archivo_entrada}")
        sys.exit(1)

    sufijo = path.suffix.lower()
    try:
        if sufijo == '.csv':
            df = None
            for encoding in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
                for sep in (',', ';', '\t'):
                    try:
                        df = pd.read_csv(archivo_entrada, sep=sep, encoding=encoding)
                        if len(df.columns) >= 2:
                            break
                    except Exception:
                        df = None
                        continue
                if df is not None and len(df.columns) >= 2:
                    break
            if df is None:
                df = pd.read_csv(archivo_entrada, sep=',', encoding='utf-8')
        else:
            df = pd.read_excel(archivo_entrada, engine='openpyxl')
    except Exception as e:
        print(f"✗ Error al leer {archivo_entrada}: {e}")
        sys.exit(1)

    # Normalizar nombres de columnas (quitar espacios, etc.)
    df.columns = df.columns.str.strip()
    # Mapeo por si el CSV trae nombres ligeramente distintos
    mapeo = {
        'nombre': 'name',
        'collection': 'name',
        'product_type': 'product_type_id',
        'fabricante': 'x_studio_field_qZO8q',
        'original_series': 'x_ce_original_series',
    }
    df = df.rename(columns=mapeo)

    if len(df) == 0:
        print("✗ El archivo no tiene filas de datos.")
        sys.exit(1)

    print(f"✓ Entrada leída: {archivo_entrada} ({len(df)} fila(s))")
    return df


def generar_paso2(df_paso1, datos_colores=None, appearance=None, tipologia=None):
    """
    Genera el DataFrame del paso 2 a partir del paso 1.
    """
    if datos_colores is None:
        datos_colores = DEFAULT_COLORES
    if appearance is None:
        appearance = DEFAULT_APPEARANCE
    if tipologia is None:
        tipologia = DEFAULT_TIPOLOGIA

    coleccion = df_paso1.iloc[0]
    name = coleccion.get('name', coleccion.get('nombre', ''))
    x_studio = coleccion.get('x_studio_field_qZO8q', '')

    filas = []
    for idx, color_data in enumerate(datos_colores):
        color_rev = color_data.get('color_revestimiento', '')
        colormatch = color_data.get('colormatch', '')
        tipologia_color = color_data.get('tipologia', tipologia)
        acabado = color_data.get('acabado_inicial', 'Mate')

        fila_color = {
            'id': None,
            'x_ce_collection_appearance': appearance if idx == 0 else None,
            'x_studio_field_qZO8q': x_studio if idx == 0 else None,
            'name': name if idx == 0 else None,
            'x_ce_collection_typologies': tipologia if idx == 0 else None,
            'x_ce_color_ids/x_ce_color_revestimiento': color_rev,
            'x_ce_color_ids/x_ce_tipologia': tipologia_color,
            'x_ce_color_ids/x_ce_acabados_ids/x_acabados_id': acabado,
            'x_ce_color_ids/x_colormatch': colormatch,
        }
        filas.append(fila_color)

        fila_brillante = {
            'id': None,
            'x_ce_collection_appearance': None,
            'x_studio_field_qZO8q': None,
            'name': None,
            'x_ce_collection_typologies': None,
            'x_ce_color_ids/x_ce_color_revestimiento': None,
            'x_ce_color_ids/x_ce_tipologia': None,
            'x_ce_color_ids/x_ce_acabados_ids/x_acabados_id': 'Brillante',
            'x_ce_color_ids/x_colormatch': None,
        }
        filas.append(fila_brillante)

    columnas = [
        'id', 'x_ce_collection_appearance', 'x_studio_field_qZO8q', 'name',
        'x_ce_collection_typologies', 'x_ce_color_ids/x_ce_color_revestimiento',
        'x_ce_color_ids/x_ce_tipologia',
        'x_ce_color_ids/x_ce_acabados_ids/x_acabados_id',
        'x_ce_color_ids/x_colormatch',
    ]
    df_paso2 = pd.DataFrame(filas)[columnas]
    print(f"✓ Paso 2 generado: {len(df_paso2)} filas")
    return df_paso2


def guardar_paso2(df_paso2, archivo_salida):
    """Guarda el paso 2 en Excel."""
    dir_salida = os.path.dirname(archivo_salida)
    if dir_salida:
        os.makedirs(dir_salida, exist_ok=True)
    df_paso2.to_excel(archivo_salida, index=False, engine='openpyxl')
    print(f"✓ Salida guardada: {archivo_salida}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 convertir_paso1_a_paso2_ceramica.py <entrada.csv|.xlsx> [salida.xlsx]")
        print("Ejemplo: python3 convertir_paso1_a_paso2_ceramica.py mi_coleccion.csv output/ceramica/paso2.xlsx")
        sys.exit(1)

    archivo_entrada = sys.argv[1]
    if len(sys.argv) >= 3:
        archivo_salida = sys.argv[2]
    else:
        base = Path(archivo_entrada).stem
        archivo_salida = f"output/ceramica/02_Colores_{base}.xlsx"

    print("Paso 1 → Paso 2 (Cerámica)")
    print("-" * 50)
    df_paso1 = leer_paso1(archivo_entrada)
    df_paso2 = generar_paso2(df_paso1)
    guardar_paso2(df_paso2, archivo_salida)
    print("-" * 50)
    print("Listo.")


if __name__ == "__main__":
    main()
