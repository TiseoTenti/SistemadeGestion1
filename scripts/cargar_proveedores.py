import sys
import os
import pandas as pd

# ================================
# AÑADIR LA RAÍZ DEL PROYECTO AL PYTHONPATH
# ================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Proveedor  # ajustá según tu proyecto

# ================================
# CONFIGURACIÓN
# ================================
CSV_PATH = "/app/scripts/proveedores.csv"  # <-- Ruta de tu CSV dentro del contenedor
REEMPLAZO_DEFAULT = "-"  # Valor para campos vacíos

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
columnas_necesarias = ['nombre', 'razon_social', 'cuit', 'direccion', 'telefono', 'email']
for col in columnas_necesarias:
    if col not in df.columns:
        df[col] = REEMPLAZO_DEFAULT

# Reemplazar valores faltantes con "-"
df.fillna(REEMPLAZO_DEFAULT, inplace=True)

# ================================
# OBTENER PROVEEDORES EXISTENTES
# ================================
proveedores_existentes = {
    p.nombre.strip().upper()
    for p in db.session.query(Proveedor.nombre).all()
}

insertados = 0
omitidos = 0

# ================================
# INSERTAR SOLO LOS NUEVOS
# ================================
for _, row in df.iterrows():
    nombre = str(row['nombre']).strip().upper()

    if nombre in proveedores_existentes:
        omitidos += 1
        continue

    proveedor = Proveedor(
        nombre=nombre,
        razon_social=str(row['razon_social']).strip().upper(),
        cuit=row['cuit'],
        direccion=row['direccion'],
        telefono=row['telefono'],
        email=row['email']
    )

    db.session.add(proveedor)
    proveedores_existentes.add(nombre)
    insertados += 1

db.session.commit()

print(f"Carga finalizada.")
print(f"Proveedores insertados: {insertados}")
print(f"Proveedores omitidos (duplicados): {omitidos}")


