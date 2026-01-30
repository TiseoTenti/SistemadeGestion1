# routes/api_insumos.py
from flask import Blueprint, request, jsonify
from models import db, Insumo, AlertaStock
from flask_login import login_required, current_user

insumos_bp = Blueprint('insumos_bp', __name__, url_prefix='/api/v1/insumos')


# Esta ruta busca todos los inusmos
@insumos_bp.route('/buscar', methods=['GET'])
def buscar_insumos():
    q = request.args.get('q', '').strip()

    if not q:
        return jsonify([])

    insumos = Insumo.query.filter(
        Insumo.nombre.ilike(f"%{q}%")
    ).order_by(Insumo.nombre).limit(10).all()

    return jsonify([
        {
            "id_insumo": i.id_insumo,
            "nombre": i.nombre,
            "stock":i.cantidad,
        } for i in insumos
    ])



#Esta ruta lista todos los insumos
@insumos_bp.route('/', methods=['GET'])
def listar_insumos():
    insumos = Insumo.query.all()
    return jsonify([i.to_dict() for i in insumos])


#Esta ruta es para buscar insumo por id
@insumos_bp.route('/<int:id_insumo>', methods=['GET'])
def obtener_insumo(id_insumo):
    insumo = Insumo.query.get_or_404(id_insumo)
    return jsonify(insumo.to_dict())




# Esta ruta es para crear un insumo
@insumos_bp.route('/', methods=['POST'])
def crear_insumo():
    data = request.json
    nuevo = Insumo(
        nombre=data['nombre'],
        cantidad=data.get('cantidad', 0),
        unidad_medida=data['unidad_medida'],
        stock_minimo=data.get('stock_minimo', 0)
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.to_dict()), 201



# Esa ruta es para editar un insumo
@insumos_bp.route('/<int:id_insumo>', methods=['PUT'])
@login_required
def actualizar_insumo(id_insumo):
    if current_user.role != 'administrador':
        return jsonify({'error': 'Solo el administrador puede editar insumos'}), 403

    insumo = Insumo.query.get_or_404(id_insumo)
    data = request.json

    for campo in ['nombre','cantidad','unidad_medida','stock_minimo']:
        if campo in data:
            setattr(insumo, campo, data[campo])

    db.session.commit()

    if float(insumo.cantidad) < float(insumo.stock_minimo):
        alerta = AlertaStock(
            id_insumo=insumo.id_insumo,
            cantidad_actual=insumo.cantidad,
            stock_minimo=insumo.stock_minimo
        )
        db.session.add(alerta)
        db.session.commit()

    return jsonify(insumo.to_dict())



# Esta ruta es para relacionarla con las aletas de stock 
@insumos_bp.route('/alertas', methods=['GET'])
def listar_alertas():
    alertas = AlertaStock.query.filter_by(estado='Pendiente').all()
    return jsonify([a.to_dict() for a in alertas])


@insumos_bp.route('/dashboard', methods=['GET'])
def insumos_dashboard():
    """
    Devuelve solo insumos con stock <= 120% del stock mínimo
    (Crítico + Alerta)
    """
    insumos = Insumo.query.filter(
        Insumo.cantidad <= (Insumo.stock_minimo * 1.2)
    ).order_by(Insumo.nombre).all()

    return jsonify([
        {
            "id_insumo": i.id_insumo,
            "nombre": i.nombre,
            "cantidad": float(i.cantidad),
            "stock_minimo": float(i.stock_minimo)
        }
        for i in insumos
    ])



@insumos_bp.route('/ultimos100', methods=['GET'])
def ultimos_100_insumos():
    insumos = (
        Insumo.query
        .order_by(Insumo.id_insumo.desc())
        .limit(100)
        .all()
    )

    return jsonify([i.to_dict() for i in insumos])




@insumos_bp.route('/criticos', methods=['GET'])
def insumos_criticos():
    insumos = (
        Insumo.query
        .filter(Insumo.cantidad <= (Insumo.stock_minimo * 1.2))
        .order_by(Insumo.cantidad.asc())
        .all()
    )

    return jsonify([i.to_dict() for i in insumos])








