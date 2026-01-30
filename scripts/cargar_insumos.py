import sys
import os
import pandas as pd

# ================================
# AÑADIR LA RAÍZ DEL PROYECTO AL PYTHONPATH
# ================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Insumo  # ajustá según tu proyecto

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ================================
# CONFIGURACIÓN
# ================================
CSV_PATH = os.path.join(BASE_DIR, "insumos_limpio2.csv")  # <-- Ruta de tu CSV
CANTIDAD_DEFAULT = 1000
UNIDAD_DEFAULT = "Unidad"
STOCK_MINIMO_DEFAULT = 1

# ================================
# INICIALIZAR APP Y CONTEXTO DB
# ================================
app.app_context().push()

# ================================
# LEER CSV
# ================================
if not os.path.isfile(CSV_PATH):
    raise FileNotFoundError(f"No se encuentra el archivo CSV en {CSV_PATH}")

df = pd.read_csv(CSV_PATH)

# Asegurarse de que tenga las columnas correctas
columnas_necesarias = ['nombre', 'cantidad', 'unidad_medida', 'stock_minimo']
for col in columnas_necesarias:
    if col not in df.columns:
        if col == 'cantidad':
            df[col] = CANTIDAD_DEFAULT
        elif col == 'unidad_medida':
            df[col] = UNIDAD_DEFAULT
        elif col == 'stock_minimo':
            df[col] = STOCK_MINIMO_DEFAULT
        else:
            df[col] = ""

# Reemplazar valores faltantes con los defaults
df['nombre'] = df['nombre'].str.slice(0, 100)
df['cantidad'] = df['cantidad'].fillna(CANTIDAD_DEFAULT)
df['unidad_medida'] = df['unidad_medida'].fillna(UNIDAD_DEFAULT)
df['stock_minimo'] = df['stock_minimo'].fillna(STOCK_MINIMO_DEFAULT)
# ================================
# INSERTAR EN LA BASE DE DATOS
# ================================
for _, row in df.iterrows():
    insumo = Insumo(
        nombre=row['nombre'],
        cantidad=row['cantidad'],
        unidad_medida=row['unidad_medida'],
        stock_minimo=row['stock_minimo']
    )
    db.session.add(insumo)

db.session.commit()

print(f"Carga completada! Se agregaron {len(df)} insumos a la base de datos.")
