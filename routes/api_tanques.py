# routes/api_tanques.py
from flask import Blueprint, request, jsonify
from models import db, TanqueFabricado, TanqueInsumo, Insumo, Compra
from decimal import Decimal
from datetime import datetime
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from flask import send_file
import io
from flask_login import login_required, current_user



tanques_bp = Blueprint('tanques_bp', __name__, url_prefix='/api/v1/tanques')

@tanques_bp.route('/', methods=['GET'])
def listar_tanques():
    tanques = TanqueFabricado.query.order_by(TanqueFabricado.fecha.desc()).all()
    return jsonify([t.to_dict() for t in tanques])


# GET /api/v1/tanques/activos
@tanques_bp.route('/activos', methods=['GET'])
def listar_tanques_activos():
    # Solo tanques que no estén finalizados
    tanques = TanqueFabricado.query.filter_by(finalizado=False).all()
    resultado = []
    for t in tanques:
        resultado.append({
            "id_tanque": t.id_tanque,
            "modelo": t.modelo,
            "fecha": t.fecha.strftime('%Y-%m-%d'),
            "cliente": t.cliente,
            "costo_total": float(t.costo_total or 0),
            "finalizado": t.finalizado
        })
    return jsonify(resultado), 200




@tanques_bp.route('/', methods=['POST'])
def crear_tanque():
    data = request.json

    fecha_str = data.get('fecha')
    fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else datetime.utcnow().date()

    tanque = TanqueFabricado(
        modelo=data['modelo'],
        fecha=fecha,
        cliente=data.get('cliente')
    )

    db.session.add(tanque)
    db.session.flush() # para tener tanque.id_tanque

    costo_total = Decimal('0')
    for item in data.get('insumos', []):
        id_insumo = item['id_insumo']
        cantidad_usada = Decimal(str(item['cantidad_usada']))
        costo_unitario = Decimal(str(item['costo_unitario']))

        insumo = Insumo.query.get_or_404(id_insumo)

        ti = TanqueInsumo(
            id_tanque = tanque.id_tanque,
            id_insumo = insumo.id_insumo,
            cantidad_usada = cantidad_usada,
            costo_unitario = costo_unitario
        )
        db.session.add(ti)
        costo_total += cantidad_usada * costo_unitario
        # NOTA: según requisitos iniciales NO descontamos stock automáticamente al fabricar un tanque
        # si en el futuro querés descontar, descomentar la siguiente línea:
        insumo.cantidad = Decimal(insumo.cantidad) - cantidad_usada

    tanque.costo_total = costo_total
    db.session.commit()
    return jsonify(tanque.to_dict()), 201

@tanques_bp.route('/<int:id_tanque>', methods=['GET'])
def obtener_tanque(id_tanque):
    tanque = TanqueFabricado.query.get_or_404(id_tanque)
    return jsonify(tanque.to_dict())

@tanques_bp.route('/<int:id_tanque>/insumos', methods=['GET'])
def insumos_tanque(id_tanque):
    tanque = TanqueFabricado.query.get_or_404(id_tanque)
    return jsonify([ti.to_dict() for ti in tanque.tanque_insumo])


@tanques_bp.route('/clientes', methods=['GET'])
def buscar_clientes():
    q = request.args.get('q', '').strip()

    if not q:
        return jsonify([])

    clientes = (
        db.session.query(TanqueFabricado.cliente)
        .filter(TanqueFabricado.cliente.ilike(f"%{q}%"))
        .distinct()
        .limit(10)
        .all()
    )

    return jsonify([c[0] for c in clientes if c[0]])




@tanques_bp.route('/<int:id_tanque>/finalizar', methods=['PUT'])
@login_required
def finalizar_tanque(id_tanque):
    if current_user.role != 'administrador':
        return jsonify({'error': 'Solo el administrador puede finalizar tanques'}), 403

    tanque = TanqueFabricado.query.get_or_404(id_tanque)
    
    if tanque.finalizado:
        return jsonify({'error': 'Este tanque ya fue finalizado'}), 400

    insumos = TanqueInsumo.query.filter_by(id_tanque=id_tanque).all()
    if not insumos:
        return jsonify({'error': 'El tanque no tiene insumos registrados'}), 400

    # Marcar como finalizado
    costo_total = sum(i.cantidad_usada * i.costo_unitario for i in insumos)
    tanque.costo_total = costo_total
    tanque.finalizado = True
    db.session.commit()

    # Generar PDF en memoria
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)
    pdf.setTitle(f"Tanque_{tanque.id_tanque}_Finalizado")
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, height - 50, f"Informe de Tanque ID {tanque.id_tanque}")
    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, height - 80, f"Cliente: {tanque.cliente or '-'}")
    pdf.drawString(50, height - 95, f"Modelo: {tanque.modelo or '-'}")
    pdf.drawString(50, height - 110, f"Fecha: {tanque.fecha.strftime('%Y-%m-%d')}")
    pdf.drawString(50, height - 125, f"Costo Total: ${float(costo_total):.2f}")

    y_start = height - 150
    row_height = 20
    x_positions = [40, 110, 165, 395, 480, 560, 640]
    headers = ["Fecha salida","Cantidad","Insumo","Precio Unitario","Precio Total","Proveedor","Fecha compra"]

    def dibujar_fila(y, valores, bold=False):
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        for i, val in enumerate(valores):
            pdf.drawString(x_positions[i] + 2, y + 5, str(val))
        pdf.line(x_positions[0], y, x_positions[-1] + 80, y)

    y = y_start
    dibujar_fila(y, headers, bold=True)
    y -= row_height

    for ti in tanque.tanque_insumo:
        if y < 80:
            pdf.showPage()
            y = height - 50
            dibujar_fila(y, headers, bold=True)
            y -= row_height

        fecha_salida = ti.fecha_registro.strftime('%Y-%m-%d') if ti.fecha_registro else '-'
        cantidad = f"{float(ti.cantidad_usada):.2f}"
        insumo_nombre = ti.insumo.nombre if ti.insumo else '-'
        precio_unitario = f"${float(ti.costo_unitario):.2f}"
        precio_total = f"${float(ti.cantidad_usada * ti.costo_unitario):.2f}"

        proveedor_nombre = '-'
        fecha_compra = '-'

        if ti.insumo and getattr(ti.insumo, 'proveedor_insumo', None):
            prov_list = ti.insumo.proveedor_insumo
            if prov_list:
                prov = prov_list[0]
                proveedor_nombre = prov.proveedor.nombre if prov.proveedor else '-'
                ultima_compra = Compra.query.filter_by(
                    id_insumo=ti.insumo.id_insumo,
                    id_proveedor=prov.id_proveedor
                ).order_by(Compra.fecha.desc()).first()
                if ultima_compra:
                    fecha_compra = ultima_compra.fecha.strftime('%Y-%m-%d')

        dibujar_fila(y, [fecha_salida, cantidad, insumo_nombre, precio_unitario, precio_total, proveedor_nombre, fecha_compra])
        y -= row_height

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Tanque_{tanque.id_tanque}_Finalizado.pdf",
        mimetype='application/pdf'
    )









@tanques_bp.route('/<int:id_tanque>/desfinalizar', methods=['PUT'])
@login_required
def desfinalizar_tanque(id_tanque):
    # Solo administrador puede desfinalizar
    if current_user.role != 'administrador':
        return jsonify({'error': 'Solo el administrador puede desfinalizar tanques'}), 403

    tanque = TanqueFabricado.query.get_or_404(id_tanque)

    if not tanque.finalizado:
        return jsonify({'error': 'El tanque ya no está finalizado'}), 400

    tanque.finalizado = False
    db.session.commit()

    return jsonify({'ok': True, 'msg': 'Tanque desfinalizado correctamente'})
