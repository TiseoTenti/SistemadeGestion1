# routes/api_compras.py
from flask import Blueprint, request, jsonify
from models import db, Compra, Proveedor, Insumo, ProveedorInsumo, HistorialPrecio, AlertaStock
from datetime import datetime
from decimal import Decimal
from flask_login import current_user, login_required
from flask import render_template

compras_bp = Blueprint('compras_bp', __name__, url_prefix='/api/v1/compras')

@compras_bp.route('/', methods=['GET'])
def listar_compras():
    compras = (
        db.session.query(Compra)
        .join(Proveedor)
        .join(Insumo)
        .order_by(Compra.id_compra.desc())
        .limit(20)
        .all()
    )
    return jsonify([c.to_dict() for c in compras])




@compras_bp.route('/insumos', methods=['GET'])
def listar_insumos():
    insumos = Insumo.query.order_by(Insumo.nombre).all()
    return jsonify([{'id_insumo': i.id_insumo, 'nombre': i.nombre} for i in insumos])



@compras_bp.route('/buscar', methods=['GET'])
def buscar_compras_por_insumo():
    nombre = request.args.get('nombre')

    if not nombre:
        return jsonify([])

    compras = (
        db.session.query(Compra)
        .join(Insumo)
        .filter(Insumo.nombre.ilike(f"%{nombre}%"))
        .order_by(Compra.id_compra.desc())
        .all()
    )

    return jsonify([c.to_dict() for c in compras])



@compras_bp.route('/<int:id_compra>/confirmar', methods=['PUT'])
@login_required
def confirmar_compra(id_compra):
    compra = Compra.query.get_or_404(id_compra)

    # Solo admin puede confirmar
    if getattr(current_user, 'role', 'user') != 'administrador':
        return jsonify({'error': 'No autorizado'}), 403

    compra.confirmado = True
    db.session.commit()
    return jsonify({'message': 'Compra confirmada', 'id_compra': id_compra})





@compras_bp.route('/<int:id_compra>/revisar', methods=['PUT'])
def marcar_revisado(id_compra):
    compra = Compra.query.get_or_404(id_compra)
    compra.revisado = True
    db.session.commit()
    return jsonify({'message': 'Compra marcada como revisada'})



@compras_bp.route('/', methods=['POST'])
def crear_compra():
    data = request.json
    # espera: { "id_proveedor":int, "id_insumo":int, "cantidad":n, "precio_unitario":n, "fecha": "YYYY-MM-DD" (opcional) }
    proveedor = Proveedor.query.get_or_404(data['id_proveedor'])
    insumo = Insumo.query.get_or_404(data['id_insumo'])

    cantidad = Decimal(str(data['cantidad']))
    precio_unitario = Decimal(str(data['precio_unitario']))
    total = cantidad * precio_unitario

    compra = Compra(
        fecha = datetime.strptime(data.get('fecha', datetime.utcnow().strftime('%Y-%m-%d')), '%Y-%m-%d'),
        id_proveedor = proveedor.id_proveedor,
        id_insumo = insumo.id_insumo,
        cantidad = cantidad,
        precio_unitario = precio_unitario,
        total = total
    )
    # Actualizar stock del insumo (las compras incrementan stock)
    insumo.cantidad = Decimal(insumo.cantidad) + cantidad

    db.session.add(compra)

    # Actualizar o crear registro proveedor_insumo y registrar historial de precio
    proveedor_insumo = ProveedorInsumo.query.filter_by(id_proveedor=proveedor.id_proveedor, id_insumo=insumo.id_insumo).first()
    if proveedor_insumo:
        proveedor_insumo.precio_actual = precio_unitario
    else:
        proveedor_insumo = ProveedorInsumo(id_proveedor=proveedor.id_proveedor, id_insumo=insumo.id_insumo, precio_actual=precio_unitario)
        db.session.add(proveedor_insumo)
        db.session.flush()  # para tener id_proveedor_insumo

    # Registrar historial de precios
    historial = HistorialPrecio(id_proveedor_insumo=proveedor_insumo.id_proveedor_insumo, precio=precio_unitario)
    db.session.add(historial)

    # Generar alerta si quedó por debajo del mínimo
    if float(insumo.cantidad) < float(insumo.stock_minimo):
        alerta = AlertaStock(id_insumo=insumo.id_insumo, cantidad_actual=insumo.cantidad, stock_minimo=insumo.stock_minimo)
        db.session.add(alerta)

    db.session.commit()
    return jsonify(compra.to_dict()), 201

@compras_bp.route('/proveedor/<string:nombre>', methods=['GET'])
def compras_por_proveedor(nombre):
    compras = (
        db.session.query(Compra)
        .join(Proveedor)
        .filter(Proveedor.nombre.ilike(f"%{nombre}%"))
        .order_by(Compra.id_compra.desc())
        .all()
    )
    return jsonify([c.to_dict() for c in compras])






@compras_bp.route('/insumo/<int:id_insumo>', methods=['GET'])
def compras_por_insumo(id_insumo):
    compras = Compra.query.filter_by(id_insumo=id_insumo).all()
    return jsonify([c.to_dict() for c in compras])



@login_required
@compras_bp.route('/<int:id_compra>', methods=['PUT'])
def actualizar_compra(id_compra):

    if getattr(current_user, 'role', 'user') != 'administrador':
        return jsonify({'error': 'No autorizado'}), 403

    data = request.json
    compra = Compra.query.get_or_404(id_compra)
    insumo = Insumo.query.get_or_404(compra.id_insumo)
    proveedor = Proveedor.query.get_or_404(compra.id_proveedor)

    # Guardamos stock original para ajustar correctamente
    cantidad_original = Decimal(compra.cantidad)
    precio_original = Decimal(compra.precio_unitario)

    # Nuevos valores
    nueva_cantidad = Decimal(str(data.get('cantidad', compra.cantidad)))
    nuevo_precio = Decimal(str(data.get('precio_unitario', compra.precio_unitario)))
    nueva_fecha = data.get('fecha', compra.fecha.strftime('%Y-%m-%d'))

    # Ajustamos stock del insumo
    # Primero revertimos la compra anterior
    insumo.cantidad = Decimal(insumo.cantidad) - cantidad_original
    # Sumamos la nueva cantidad
    insumo.cantidad += nueva_cantidad

    # Actualizamos campos de la compra
    compra.cantidad = nueva_cantidad
    compra.precio_unitario = nuevo_precio
    compra.total = nueva_cantidad * nuevo_precio
    compra.fecha = datetime.strptime(nueva_fecha, '%Y-%m-%d')

    # Actualizamos proveedor_insumo y historial de precios si cambió el precio
    proveedor_insumo = ProveedorInsumo.query.filter_by(
        id_proveedor=proveedor.id_proveedor,
        id_insumo=insumo.id_insumo
    ).first()

    if proveedor_insumo and proveedor_insumo.precio_actual != nuevo_precio:
        proveedor_insumo.precio_actual = nuevo_precio
        historial = HistorialPrecio(id_proveedor_insumo=proveedor_insumo.id_proveedor_insumo,
                                   precio=nuevo_precio)
        db.session.add(historial)

    # Verificar alertas de stock
    if float(insumo.cantidad) < float(insumo.stock_minimo):
        alerta = AlertaStock(id_insumo=insumo.id_insumo,
                             cantidad_actual=insumo.cantidad,
                             stock_minimo=insumo.stock_minimo)
        db.session.add(alerta)

    db.session.commit()
    return jsonify(compra.to_dict())
