import sys
import os
import pandas as pd
from decimal import Decimal
from datetime import datetime

# ================================
# AGREGAR RAÍZ DEL PROYECTO
# ================================
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import Compra, Proveedor, Insumo, ProveedorInsumo, HistorialPrecio

# ================================
# CONFIGURACIÓN
# ================================
CSV_PATH = "/app/scripts/compras.csv"
CUIT_DEFAULT = "00-00000000-0"
UNIDAD_MEDIDA_DEFAULT = "Unidad"

# ================================
# UTILIDADES
# ================================
def normalizar(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().upper()

def limitar(texto, max_len):
    return texto[:max_len] if texto else ""

def decimal_safe(valor):
    try:
        if pd.isna(valor):
            return Decimal("0.00")

        limpio = (
            str(valor)
            .replace("$", "")
            .replace(" ", "")
            .replace(".", "")
            .replace(",", ".")
        )

        return Decimal(limpio).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")

# ================================
# PROCESO PRINCIPAL
# ================================
with app.app_context():

    df = pd.read_csv(CSV_PATH)
    compras_insertadas = 0

    for _, row in df.iterrows():

        # ---------- PROVEEDOR ----------
        nombre_proveedor = limitar(normalizar(row.get("proveedor")), 100)

        proveedor = Proveedor.query.filter_by(nombre=nombre_proveedor).first()

        if not proveedor:
            proveedor = Proveedor(
                nombre=nombre_proveedor,
                cuit=CUIT_DEFAULT
            )
            db.session.add(proveedor)
            db.session.flush()

        # ---------- INSUMO ----------
        nombre_insumo = limitar(normalizar(row.get("insumo")), 100)

        insumo = Insumo.query.filter_by(nombre=nombre_insumo).first()

        if not insumo:
            insumo = Insumo(
                nombre=nombre_insumo,
                unidad_medida=UNIDAD_MEDIDA_DEFAULT,
                cantidad=Decimal("0")
            )
            db.session.add(insumo)
            db.session.flush()

        # ---------- FECHA ----------
        try:
            fecha = pd.to_datetime(row.get("fecha")).date()
        except Exception:
            fecha = datetime.utcnow().date()

        # ---------- CANTIDAD / PRECIO ----------
        cantidad = decimal_safe(row.get("cantidad"))
        precio_unitario = decimal_safe(row.get("precio_unitario"))
        total = (cantidad * precio_unitario).quantize(Decimal("0.01"))

        # ---------- COMPRA ----------
        compra = Compra(
            fecha=fecha,
            id_proveedor=proveedor.id_proveedor,
            id_insumo=insumo.id_insumo,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            total=total
        )

        db.session.add(compra)
        compras_insertadas += 1

        # ---------- PROVEEDOR - INSUMO ----------
        pi = ProveedorInsumo.query.filter_by(
            id_proveedor=proveedor.id_proveedor,
            id_insumo=insumo.id_insumo
        ).first()

        if not pi:
            pi = ProveedorInsumo(
                id_proveedor=proveedor.id_proveedor,
                id_insumo=insumo.id_insumo,
                precio_actual=precio_unitario
            )
            db.session.add(pi)
            db.session.flush()
        else:
            pi.precio_actual = precio_unitario

        # ---------- HISTORIAL DE PRECIOS ----------
        hist = HistorialPrecio(
            id_proveedor_insumo=pi.id_proveedor_insumo,
            precio=precio_unitario
        )
        db.session.add(hist)

    db.session.commit()
    print(f"✅ Carga finalizada. Compras insertadas: {compras_insertadas}")
