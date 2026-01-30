import sys
import os
import pandas as pd
from decimal import Decimal
from datetime import datetime

# ================================
# AÑADIR LA RAÍZ DEL PROYECTO AL PYTHONPATH
# ================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ================================
# IMPORTAR APP Y MODELOS
# ================================
from app import app, db
from models import Compra, Proveedor, Insumo

# ================================
# CONFIGURACIÓN
# ================================
CSV_PATH = "/app/scripts/compras_limpio1.csv"  # Ruta a tu CSV
REEMPLAZO_DEFAULT = "-"                        # Valor por defecto para campos vacíos
UNIDAD_MEDIDA_DEFAULT = "Unidad"              # Unidad por defecto para insumos nuevos

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
df.fillna(REEMPLAZO_DEFAULT, inplace=True)

# ================================
# LIMPIAR DATOS Y ASEGURAR CAMPOS
# ================================
for col in ['id_proveedor', 'insumo']:
    if col in df.columns:
        df[col] = df[col].astype(str).str.upper().str.strip()

# ================================
# CARGAR COMPRAS
# ================================
compras_cargadas = 0
for _, row in df.iterrows():
    # Buscar proveedor
    proveedor_nombre = row['id_proveedor']
    proveedor = Proveedor.query.filter_by(nombre=proveedor_nombre).first()
    if not proveedor:
        print(f"Proveedor '{proveedor_nombre}' no encontrado, se omite esta compra.")
        continue

    # Buscar o crear insumo
    insumo_nombre = row['insumo']
    insumo = Insumo.query.filter_by(nombre=insumo_nombre).first()
    try:
        precio_unitario = Decimal(str(row['precio_unitario']))
        if precio_unitario <= 0:
            precio_unitario = None
    except Exception:
        precio_unitario = None

    try:
        cantidad = Decimal(str(row['cantidad']))
    except Exception:
        cantidad = Decimal(0)

    total = (precio_unitario or Decimal(0)) * cantidad

    if not insumo:
        # Crear insumo con unidad y precio
        insumo = Insumo(
            nombre=insumo_nombre,
            cantidad=Decimal(0),
            unidad_medida=UNIDAD_MEDIDA_DEFAULT,
            stock_minimo=Decimal(0),
            ultimo_precio=precio_unitario or Decimal(0)
        )
        db.session.add(insumo)
        db.session.flush()  # para obtener id_insumo

    # Fecha
    try:
        fecha = pd.to_datetime(row['fecha']).date()
    except Exception:
        continue

    # Evitar duplicados exactos de fecha + proveedor + insumo
    existe = Compra.query.filter_by(
        fecha=fecha,
        id_proveedor=proveedor.id_proveedor,
        id_insumo=insumo.id_insumo
    ).first()
    if existe:
        continue

    # Crear compra
    compra = Compra(
        fecha=fecha,
        id_proveedor=proveedor.id_proveedor,
        id_insumo=insumo.id_insumo,
        cantidad=cantidad,
        precio_unitario=precio_unitario or Decimal(0),
        total=total
    )
    db.session.add(compra)
    compras_cargadas += 1

    # Actualizar último precio solo si precio_unitario existe
    if precio_unitario:
        insumo.ultimo_precio = precio_unitario
# ================================
# COMMIT FINAL
# ================================
db.session.commit()
print(f"Carga completada! Se agregaron {compras_cargadas} compras a la base de datos y se actualizaron precios de insumos.")

