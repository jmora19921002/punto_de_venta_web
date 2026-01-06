from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from functools import wraps
from database import DatabaseManager
import hashlib
from datetime import datetime, date
import json
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Cambiar en producción por una clave segura

# Inicializar base de datos
db = DatabaseManager()

# Decorador para requerir autenticación
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir rol específico
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user_role = session.get('user_role')
            if user_role not in roles:
                flash('No tiene permisos para acceder a esta sección', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ========== RUTAS DE AUTENTICACIÓN ==========

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('punto_venta'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember')
        
        if not username or not password:
            flash('Por favor ingrese usuario y contraseña', 'error')
            return render_template('login.html')
        
        usuario = db.validar_usuario(username, password)
        
        if usuario:
            session['user_id'] = usuario['id']
            session['username'] = usuario['username']
            session['nombre_completo'] = usuario['nombre_completo']
            session['user_role'] = usuario['rol']
            
            if remember:
                session.permanent = True
            
            flash(f'¡Bienvenido {usuario["nombre_completo"]}!', 'success')
            return redirect(url_for('punto_venta'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sesión cerrada correctamente', 'info')
    return redirect(url_for('login'))

# ========== RUTAS PRINCIPALES ==========

@app.route('/punto-venta')
@login_required
def punto_venta():
    """Pantalla principal de punto de venta"""
    # Obtener productos y categorías
    productos = db.get_productos()
    categorias = db.get_categorias()
    monedas = db.get_monedas_activas()
    tasa_cambio = db.get_tasa_cambio()
    
    # Obtener cliente si hay uno en sesión
    cliente_id = session.get('cliente_seleccionado')
    cliente_info = None
    if cliente_id:
        clientes = db.get_clientes()
        for c in clientes:
            if c['id'] == cliente_id:
                cliente_info = c
                break
    
    return render_template('punto_venta.html',
                         productos=productos,
                         categorias=categorias,
                         monedas=monedas,
                         tasa_cambio=tasa_cambio,
                         cliente_info=cliente_info,
                         usuario=session)

# ========== RUTAS API PARA PRODUCTOS ==========

@app.route('/api/productos')
@login_required
def api_productos():
    """API para obtener productos (con filtros)"""
    categoria_id = request.args.get('categoria_id', type=int)
    busqueda = request.args.get('busqueda', '').strip()
    
    if busqueda:
        productos = db.buscar_productos(busqueda)
    else:
        productos = db.get_productos(categoria_id)
    
    return jsonify(productos)

@app.route('/api/producto/<int:producto_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_producto(producto_id):
    """API para obtener, actualizar o eliminar un producto"""
    if request.method == 'GET':
        conn = db.get_connection()
        cursor = conn.cursor()
        # Verificar columnas existentes primero
        cursor.execute("PRAGMA table_info(productos)")
        cols_info = cursor.fetchall()
        existing_cols = {row[1] for row in cols_info}
        
        # Construir query dinámicamente
        base_cols = ['p.id', 'p.codigo_barras', 'p.nombre', 'p.descripcion', 'p.precio_venta', 
                     'p.precio_venta_usd', 'p.precio_compra', 'p.precio_compra_usd', 'p.stock_actual', 
                     'p.tasa_camb', 'p.vende_al_mayor', 'p.unidades_por_bulto', 'p.stock_minimo',
                     'p.categoria_id', 'c.nombre as categoria']
        
        optional_cols = []
        if 'tipo_producto' in existing_cols:
            optional_cols.append('p.tipo_producto')
        if 'marca' in existing_cols:
            optional_cols.append('p.marca')
        if 'color' in existing_cols:
            optional_cols.append('p.color')
        if 'unidad_medida_mayor' in existing_cols:
            optional_cols.append('p.unidad_medida_mayor')
        
        all_cols = base_cols + optional_cols
        query = f"""
            SELECT {', '.join(all_cols)}
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.id = ?
        """
        cursor.execute(query, (producto_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # Construir lista de nombres de columnas dinámicamente
            base_col_names = ['id', 'codigo_barras', 'nombre', 'descripcion', 'precio_venta', 
                             'precio_venta_usd', 'precio_compra', 'precio_compra_usd', 'stock_actual', 
                             'tasa_camb', 'vende_al_mayor', 'unidades_por_bulto', 'stock_minimo',
                             'categoria_id', 'categoria']
            optional_col_names = []
            if 'tipo_producto' in existing_cols:
                optional_col_names.append('tipo_producto')
            if 'marca' in existing_cols:
                optional_col_names.append('marca')
            if 'color' in existing_cols:
                optional_col_names.append('color')
            if 'unidad_medida_mayor' in existing_cols:
                optional_col_names.append('unidad_medida_mayor')
            
            all_col_names = base_col_names + optional_col_names
            producto = dict(zip(all_col_names, row))
            # Convertir valores booleanos y establecer defaults
            producto['vende_al_mayor'] = bool(producto.get('vende_al_mayor', 0))
            producto.setdefault('tipo_producto', 'Otros')
            producto.setdefault('marca', '')
            producto.setdefault('color', '')
            producto.setdefault('unidad_medida_mayor', 'unidad')
            return jsonify(producto)
        return jsonify({'error': 'Producto no encontrado'}), 404
    
    elif request.method == 'PUT':
        data = request.json
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Verificar columnas existentes
            cursor.execute("PRAGMA table_info(productos)")
            cols_info = cursor.fetchall()
            existing_cols = {row[1] for row in cols_info}
            
            # Obtener tasa de cambio
            tasa = db.get_tasa_cambio()
            precio_venta_ves = round(float(data.get('precio_venta_usd', 0)) * tasa, 2)
            precio_compra_usd = float(data.get('precio_compra_usd', 0)) or None
            precio_compra_ves = round(precio_compra_usd * tasa, 2) if precio_compra_usd else None
            
            # Construir UPDATE dinámicamente según columnas existentes
            updates = ['codigo_barras = ?', 'nombre = ?', 'descripcion = ?', 'categoria_id = ?',
                      'precio_venta_usd = ?', 'precio_venta = ?', 'precio_compra_usd = ?', 'precio_compra = ?',
                      'stock_actual = ?', 'stock_minimo = ?', 'vende_al_mayor = ?', 'unidades_por_bulto = ?']
            values = [
                data.get('codigo_barras', '').strip() or None,
                data.get('nombre', '').strip(),
                data.get('descripcion', '').strip() or None,
                int(data.get('categoria_id')) if data.get('categoria_id') else None,
                float(data.get('precio_venta_usd', 0)),
                precio_venta_ves,
                float(data.get('precio_compra_usd', 0)) or None,
                precio_compra_ves or None,
                float(data.get('stock_actual', 0)),
                float(data.get('stock_minimo', 0)),
                int(data.get('vende_al_mayor', 0)),
                int(data.get('unidades_por_bulto', 1)) if data.get('vende_al_mayor') else None
            ]
            
            # Agregar columnas opcionales si existen
            if 'tipo_producto' in existing_cols:
                updates.append('tipo_producto = ?')
                values.append(data.get('tipo_producto', 'Otros'))
            if 'marca' in existing_cols:
                updates.append('marca = ?')
                values.append(data.get('marca', '').strip() or None)
            if 'color' in existing_cols:
                updates.append('color = ?')
                values.append(data.get('color', '').strip() or None)
            if 'unidad_medida_mayor' in existing_cols:
                updates.append('unidad_medida_mayor = ?')
                values.append(data.get('unidad_medida', 'unidad'))
            
            values.append(producto_id)
            
            sql = f"UPDATE productos SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(sql, tuple(values))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE productos SET activo = 0 WHERE id = ?", (producto_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/producto', methods=['POST'])
@login_required
@role_required('sistema', 'soporte', 'admin')
def api_crear_producto():
    """API para crear un nuevo producto"""
    data = request.json
    
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Obtener tasa de cambio
        tasa = db.get_tasa_cambio()
        precio_venta_ves = round(float(data.get('precio_venta_usd', 0)) * tasa, 2)
        precio_compra_usd = float(data.get('precio_compra_usd', 0)) or None
        precio_compra_ves = round(precio_compra_usd * tasa, 2) if precio_compra_usd else None
        
        # Verificar columnas existentes
        cursor.execute("PRAGMA table_info(productos)")
        cols_info = cursor.fetchall()
        existing_cols = {row[1] for row in cols_info}
        
        # Construir INSERT dinámicamente
        base_cols = ['codigo_barras', 'nombre', 'descripcion', 'categoria_id',
                    'precio_venta_usd', 'precio_venta', 'precio_compra_usd', 'precio_compra',
                    'stock_actual', 'stock_minimo', 'vende_al_mayor', 'unidades_por_bulto']
        base_values = [
            data.get('codigo_barras', '').strip() or None,
            data.get('nombre', '').strip(),
            data.get('descripcion', '').strip() or None,
            int(data.get('categoria_id')) if data.get('categoria_id') else None,
            float(data.get('precio_venta_usd', 0)),
            precio_venta_ves,
            precio_compra_usd,
            precio_compra_ves,
            float(data.get('stock_actual', 0)),
            float(data.get('stock_minimo', 0)),
            int(data.get('vende_al_mayor', 0)),
            int(data.get('unidades_por_bulto', 1)) if data.get('vende_al_mayor') else None
        ]
        
        # Agregar columnas opcionales si existen
        if 'tipo_producto' in existing_cols:
            base_cols.append('tipo_producto')
            base_values.append(data.get('tipo_producto', 'Otros'))
        if 'marca' in existing_cols:
            base_cols.append('marca')
            base_values.append(data.get('marca', '').strip() or None)
        if 'color' in existing_cols:
            base_cols.append('color')
            base_values.append(data.get('color', '').strip() or None)
        if 'unidad_medida_mayor' in existing_cols:
            base_cols.append('unidad_medida_mayor')
            base_values.append(data.get('unidad_medida', 'unidad'))
        
        placeholders = ', '.join(['?' for _ in base_cols])
        sql = f"INSERT INTO productos ({', '.join(base_cols)}) VALUES ({placeholders})"
        cursor.execute(sql, tuple(base_values))
        
        producto_id = cursor.lastrowid
        
        # Registrar movimiento de inventario inicial si hay stock
        stock_inicial = float(data.get('stock_actual', 0))
        if stock_inicial > 0:
            db.registrar_movimiento_inventario(
                producto_id, 'entrada', stock_inicial, 0, stock_inicial,
                'Stock inicial', 'Sistema', cursor
            )
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'id': producto_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== RUTAS API PARA CLIENTES ==========

@app.route('/api/clientes')
@login_required
def api_clientes():
    """API para obtener clientes"""
    busqueda = request.args.get('busqueda', '').strip()
    
    if busqueda:
        clientes = db.buscar_cliente(busqueda)
    else:
        clientes = db.get_clientes()
    
    return jsonify(clientes)

@app.route('/api/cliente', methods=['POST'])
@login_required
def api_crear_cliente():
    """API para crear un nuevo cliente"""
    data = request.json
    
    try:
        cliente_id = db.agregar_cliente(
            nombre=data.get('nombre', '').strip(),
            apellido=data.get('apellido', '').strip(),
            telefono=data.get('telefono', '').strip(),
            email=data.get('email', '').strip(),
            direccion=data.get('direccion', '').strip(),
            rif=data.get('rif')
        )
        return jsonify({'success': True, 'id': cliente_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/cliente/<int:cliente_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_cliente(cliente_id):
    """API para obtener, actualizar o eliminar un cliente"""
    if request.method == 'GET':
        clientes = db.get_clientes()
        cliente = next((c for c in clientes if c['id'] == cliente_id), None)
        if cliente:
            return jsonify(cliente)
        return jsonify({'error': 'Cliente no encontrado'}), 404
    
    elif request.method == 'PUT':
        data = request.json
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE clientes 
                SET nombre = ?, apellido = ?, telefono = ?, email = ?, direccion = ?, rif = ?
                WHERE id = ?
            """, (
                data.get('nombre', '').strip(),
                data.get('apellido', '').strip(),
                data.get('telefono', '').strip(),
                data.get('email', '').strip(),
                data.get('direccion', '').strip(),
                data.get('rif'),
                cliente_id
            ))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE clientes SET activo = 0 WHERE id = ?", (cliente_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

# ========== RUTAS API PARA VENTAS ==========

@app.route('/api/venta', methods=['POST'])
@login_required
def api_crear_venta():
    """API para crear una venta"""
    data = request.json
    
    try:
        items_venta = data.get('items', [])
        cliente_id = data.get('cliente_id')
        metodo_pago = data.get('metodo_pago', 'efectivo')
        descuento = float(data.get('descuento', 0))
        impuesto = float(data.get('impuesto', 0))
        notas = data.get('notas', '')
        
        if not items_venta:
            return jsonify({'success': False, 'error': 'El carrito está vacío'}), 400
        
        venta_id = db.crear_venta(
            items_venta=items_venta,
            cliente_id=cliente_id,
            metodo_pago=metodo_pago,
            descuento=descuento,
            impuesto=impuesto,
            notas=notas
        )
        
        # Registrar pagos si se proporcionan
        pagos = data.get('pagos', [])
        for pago in pagos:
            db.registrar_pago_documento(
                venta_id=venta_id,
                numero_documento=pago.get('numero_documento'),
                tipo_pago=pago.get('tipo_pago', 'efectivo'),
                monto_pagado=float(pago.get('monto_pagado', 0)),
                moneda_pago=pago.get('moneda_pago', 'USD'),
                tasa_cambio=float(pago.get('tasa_cambio', 1.0)),
                detalles_pago=json.dumps(pago.get('detalles', {}))
            )
        
        return jsonify({'success': True, 'venta_id': venta_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== RUTAS PARA GESTIÓN ==========

@app.route('/inventario')
@login_required
@role_required('sistema', 'soporte', 'admin')
def inventario():
    """Gestión de inventario"""
    productos = db.get_productos()
    categorias = db.get_categorias()
    return render_template('inventario.html', productos=productos, categorias=categorias)

@app.route('/clientes')
@login_required
def clientes():
    """Gestión de clientes"""
    clientes_list = db.get_clientes()
    return render_template('clientes.html', clientes=clientes_list)

@app.route('/compras')
@login_required
@role_required('sistema', 'soporte', 'admin')
def compras():
    """Gestión de compras"""
    compras_list = db.get_compras()
    proveedores = db.get_proveedores()
    return render_template('compras.html', compras=compras_list, proveedores=proveedores)

@app.route('/corte-dia')
@login_required
@role_required('sistema', 'soporte', 'admin')
def corte_dia():
    """Corte del día"""
    fecha = request.args.get('fecha', date.today().strftime('%Y-%m-%d'))
    corte = db.get_corte_dia(fecha)
    return render_template('corte_dia.html', corte=corte, fecha=fecha)

@app.route('/usuarios')
@login_required
@role_required('sistema')
def usuarios():
    """Gestión de usuarios"""
    usuarios_list = db.get_usuarios()
    return render_template('usuarios.html', usuarios=usuarios_list)

@app.route('/configuracion', methods=['GET', 'POST'])
@login_required
@role_required('sistema', 'soporte')
def configuracion():
    """Configuración de la empresa"""
    if request.method == 'POST':
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Obtener columnas existentes
            cursor.execute("PRAGMA table_info(configuracion)")
            cols_info = cursor.fetchall()
            existing_cols = {row[1] for row in cols_info}
            
            # Actualizar solo las columnas que existen
            updates = []
            values = []
            campos_permitidos = ['nombre_tienda', 'rif', 'direccion_tienda', 'telefono_tienda', 'impuesto_por_defecto']
            
            for campo in campos_permitidos:
                if campo in existing_cols and campo in request.form:
                    updates.append(f"{campo} = ?")
                    values.append(request.form.get(campo, '').strip())
            
            if updates:
                values.append(1)  # id = 1
                sql = f"UPDATE configuracion SET {', '.join(updates)} WHERE id = ?"
                cursor.execute(sql, tuple(values))
                conn.commit()
                flash('Configuración guardada correctamente', 'success')
            
            conn.close()
        except Exception as e:
            flash(f'Error al guardar: {str(e)}', 'error')
    
    # Obtener configuración actual
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM configuracion LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    config = {}
    if row:
        cols = [col[0] for col in cursor.description]
        config = dict(zip(cols, row))
    
    return render_template('configuracion.html', config=config)

# ========== RUTAS API ADICIONALES ==========

@app.route('/api/categorias')
@login_required
def api_categorias():
    """API para obtener categorías"""
    categorias = db.get_categorias()
    return jsonify(categorias)

@app.route('/api/tasa-cambio', methods=['GET', 'POST'])
@login_required
def api_tasa_cambio():
    """API para obtener/actualizar tasa de cambio"""
    if request.method == 'GET':
        tasa = db.get_tasa_cambio()
        return jsonify({'tasa': tasa})
    elif request.method == 'POST':
        data = request.json
        nueva_tasa = float(data.get('tasa', 0))
        if nueva_tasa > 0:
            db.actualizar_tasa_cambio(nueva_tasa)
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Tasa inválida'}), 400

@app.route('/api/operaciones-espera', methods=['GET', 'POST'])
@login_required
def api_operaciones_espera():
    """API para operaciones en espera"""
    if request.method == 'GET':
        operaciones = db.get_operaciones_espera()
        return jsonify(operaciones)
    elif request.method == 'POST':
        data = request.json
        nombre = data.get('nombre_operacion')
        carrito_data = data.get('carrito_data')
        cliente_id = data.get('cliente_id')
        
        if nombre and carrito_data:
            operacion_id = db.guardar_operacion_espera(nombre, carrito_data, cliente_id)
            return jsonify({'success': True, 'id': operacion_id})
        return jsonify({'success': False, 'error': 'Datos incompletos'}), 400

@app.route('/api/operaciones-espera/<int:operacion_id>', methods=['DELETE'])
@login_required
def api_eliminar_operacion_espera(operacion_id):
    """API para eliminar operación en espera"""
    db.eliminar_operacion_espera(operacion_id)
    return jsonify({'success': True})

# ========== RUTAS API PARA PROVEEDORES ==========

@app.route('/api/proveedores')
@login_required
def api_proveedores():
    """API para obtener proveedores"""
    proveedores = db.get_proveedores()
    return jsonify(proveedores)

@app.route('/api/proveedor/<int:proveedor_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_proveedor(proveedor_id):
    """API para obtener, actualizar o eliminar un proveedor"""
    if request.method == 'GET':
        proveedor = db.get_proveedor_by_id(proveedor_id)
        if proveedor:
            return jsonify(proveedor)
        return jsonify({'error': 'Proveedor no encontrado'}), 404
    
    elif request.method == 'PUT':
        data = request.json
        try:
            db.actualizar_proveedor(
                proveedor_id,
                nombre=data.get('nombre', '').strip(),
                contacto=data.get('contacto', '').strip() or None,
                telefono=data.get('telefono', '').strip() or None,
                email=data.get('email', '').strip() or None,
                direccion=data.get('direccion', '').strip() or None,
                rif=data.get('rif', '').strip() or None,
                notas=data.get('notas', '').strip() or None
            )
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            db.eliminar_proveedor(proveedor_id)
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/proveedor', methods=['POST'])
@login_required
def api_crear_proveedor():
    """API para crear un nuevo proveedor"""
    data = request.json
    
    try:
        proveedor_id = db.agregar_proveedor(
            nombre=data.get('nombre', '').strip(),
            contacto=data.get('contacto', '').strip() or None,
            telefono=data.get('telefono', '').strip() or None,
            email=data.get('email', '').strip() or None,
            direccion=data.get('direccion', '').strip() or None,
            rif=data.get('rif', '').strip() or None,
            notas=data.get('notas', '').strip() or None
        )
        return jsonify({'success': True, 'id': proveedor_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

# ========== RUTAS API PARA USUARIOS ==========

@app.route('/api/usuarios')
@login_required
@role_required('sistema')
def api_usuarios():
    """API para obtener usuarios"""
    usuarios = db.get_usuarios()
    return jsonify(usuarios)

@app.route('/api/usuario/<int:usuario_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
@role_required('sistema')
def api_usuario(usuario_id):
    """API para obtener, actualizar o eliminar un usuario"""
    if request.method == 'GET':
        usuarios = db.get_usuarios()
        usuario = next((u for u in usuarios if u['id'] == usuario_id), None)
        if usuario:
            # No devolver el password_hash
            usuario.pop('password_hash', None)
            return jsonify(usuario)
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    elif request.method == 'PUT':
        data = request.json
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            
            # Si hay contraseña, actualizarla
            if data.get('password'):
                import hashlib
                password_hash = hashlib.sha256(data['password'].encode()).hexdigest()
                cursor.execute("""
                    UPDATE usuarios 
                    SET nombre_completo = ?, rol = ?, password_hash = ?
                    WHERE id = ?
                """, (
                    data.get('nombre_completo', '').strip(),
                    data.get('rol', 'cajero'),
                    password_hash,
                    usuario_id
                ))
            else:
                # Solo actualizar nombre y rol
                cursor.execute("""
                    UPDATE usuarios 
                    SET nombre_completo = ?, rol = ?
                    WHERE id = ?
                """, (
                    data.get('nombre_completo', '').strip(),
                    data.get('rol', 'cajero'),
                    usuario_id
                ))
            
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (usuario_id,))
            conn.commit()
            conn.close()
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/usuario', methods=['POST'])
@login_required
@role_required('sistema')
def api_crear_usuario():
    """API para crear un nuevo usuario"""
    data = request.json
    
    try:
        if not data.get('password'):
            return jsonify({'success': False, 'error': 'La contraseña es requerida'}), 400
        
        usuario_id = db.crear_usuario(
            username=data.get('username', '').strip(),
            password=data.get('password', ''),
            nombre_completo=data.get('nombre_completo', '').strip(),
            rol=data.get('rol', 'cajero')
        )
        return jsonify({'success': True, 'id': usuario_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

