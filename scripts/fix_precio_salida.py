# scripts/fix_precio_salida.py
import sys
import os
from decimal import Decimal

# Agregamos la carpeta raíz al path para poder importar app.py y models.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db  # Importamos app.py y db
from models import TanqueInsumo, ProveedorInsumo, Compra

# Creamos el contexto de aplicación
with app.app_context():

    # Buscar registros de TanqueInsumo con costo_unitario = 0
    registros = TanqueInsumo.query.filter(TanqueInsumo.costo_unitario == 0).all()
    print(f"Se encontraron {len(registros)} registros con costo 0")

    for r in registros:
        costo = 0.0

        # Intentar obtener desde ProveedorInsumo
        proveedor_insumo = ProveedorInsumo.query.filter_by(id_insumo=r.id_insumo)\
                            .order_by(ProveedorInsumo.id_proveedor_insumo.desc()).first()
        
        if proveedor_insumo and proveedor_insumo.precio_actual:
            costo = float(proveedor_insumo.precio_actual)
            fuente = "ProveedorInsumo"
        else:
            # Si no hay, buscar última compra confirmada
            ultima_compra = Compra.query.filter_by(id_insumo=r.id_insumo, confirmado=True)\
                                .order_by(Compra.fecha.desc()).first()
            if ultima_compra:
                costo = float(ultima_compra.precio_unitario)
                fuente = f"Compra #{ultima_compra.id_compra}"
            else:
                fuente = "Ninguna fuente disponible, costo 0"

        # Actualizar solo si encontramos algún costo
        r.costo_unitario = costo
        print(f"Registro {r.id_tanque_insumo} actualizado: costo_unitario={costo} ({fuente})")

    db.session.commit()
    print("Actualización completa.")

