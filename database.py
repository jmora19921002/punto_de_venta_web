
import sqlite3
import os
import sys
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

class DatabaseManager:
    @staticmethod
    def resource_path(relative_path: str) -> str:
        """Return absolute path to resource, works for dev and for PyInstaller onefile.

        When running frozen (onefile), PyInstaller extracts resources into sys._MEIPASS.
        """
        try:
            if getattr(sys, 'frozen', False):
                # When frozen, resources bundled with the app are extracted to _MEIPASS.
                # However, for data that should be persistent (like the DB) we want
                # it to live next to the executable. Use this helper primarily for
                # locating bundled read-only resources; callers can decide to use
                # the exe directory for writable data.
                base_path = sys._MEIPASS  # type: ignore[attr-defined]
            else:
                base_path = os.path.abspath(os.path.dirname(__file__))
        except Exception:
            base_path = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(base_path, relative_path)

    def registrar_pago_documento(self, venta_id, numero_documento=None, tipo_pago="efectivo", 
                                monto_pagado=0.0, moneda_pago="USD", tasa_cambio=1.0, 
                                detalles_pago=""):
        """
        Registra un pago en la tabla pagos_documentos.
        
        Args:
            venta_id: ID de la venta asociada
            numero_documento: Número de documento/transacción (opcional)
            tipo_pago: Tipo de pago (efectivo, tarjeta, transferencia, etc.)
            monto_pagado: Monto pagado en la moneda original
            moneda_pago: Moneda en que se realizó el pago (USD, VES)
            tasa_cambio: Tasa de cambio aplicada al momento del pago
            detalles_pago: Detalles adicionales del pago (JSON string)
        
        Returns:
            int: ID del registro de pago creado
        """
        # Asegurar que la tabla de pagos exista antes de intentar insertar
        try:
            self.ensure_pagos_tables()
        except Exception:
            pass

        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Calcular monto equivalente en USD
            if moneda_pago.upper() == "USD":
                monto_equivalente_usd = monto_pagado
            else:  # VES
                monto_equivalente_usd = monto_pagado / tasa_cambio if tasa_cambio > 0 else 0
            
            cursor.execute('''
                INSERT INTO pagos_documentos 
                (venta_id, numero_documento, tipo_pago, monto_pagado, moneda_pago, 
                 tasa_cambio, monto_equivalente_usd, detalles_pago)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (venta_id, numero_documento, tipo_pago, monto_pagado, moneda_pago, 
                  tasa_cambio, monto_equivalente_usd, detalles_pago))
            
            pago_id = cursor.lastrowid
            conn.commit()
            return pago_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_pagos_por_venta(self, venta_id):
        """Obtiene todos los pagos registrados para una venta específica"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, venta_id, numero_documento, tipo_pago, monto_pagado, 
                   moneda_pago, tasa_cambio, monto_equivalente_usd, 
                   detalles_pago, fecha_pago
            FROM pagos_documentos 
            WHERE venta_id = ?
            ORDER BY fecha_pago DESC
        ''', (venta_id,))
        
        pagos = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], pago)) for pago in pagos]
    
    def get_pagos_por_fecha(self, fecha_inicio, fecha_fin=None):
        """Obtiene todos los pagos registrados en un rango de fechas"""
        if fecha_fin is None:
            fecha_fin = fecha_inicio
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT pd.id, pd.venta_id, pd.numero_documento, pd.tipo_pago, 
                   pd.monto_pagado, pd.moneda_pago, pd.tasa_cambio, 
                   pd.monto_equivalente_usd, pd.detalles_pago, pd.fecha_pago,
                   v.fecha_venta, v.total as total_venta
            FROM pagos_documentos pd
            JOIN ventas v ON pd.venta_id = v.id
            WHERE DATE(pd.fecha_pago) BETWEEN ? AND ?
            ORDER BY pd.fecha_pago DESC
        ''', (fecha_inicio, fecha_fin))
        
        pagos = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], pago)) for pago in pagos]
    
    def get_resumen_pagos_dia(self, fecha=None):
        """Obtiene un resumen de pagos por tipo para un día específico"""
        if fecha is None:
            fecha = date.today().strftime('%Y-%m-%d')
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT tipo_pago, moneda_pago,
                   COUNT(*) as cantidad_pagos,
                   SUM(monto_pagado) as total_pagado,
                   SUM(monto_equivalente_usd) as total_usd,
                   AVG(tasa_cambio) as tasa_promedio
            FROM pagos_documentos 
            WHERE DATE(fecha_pago) = ?
            GROUP BY tipo_pago, moneda_pago
            ORDER BY total_pagado DESC
        ''', (fecha,))
        
        resumen = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], item)) for item in resumen]

    # Métodos mínimos para ventas usados por la ventana de pagos
    def crear_venta(self, items_venta, cliente_id=None, metodo_pago='efectivo', descuento=0.0, impuesto=0.0, notas=''):
        """Crea una venta simple y sus detalles. Retorna el id de la venta creada."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            subtotal = sum(i.get('cantidad', 0) * i.get('precio_unitario', 0.0) for i in items_venta)
            total = subtotal + impuesto - descuento
            cursor.execute('''
                INSERT INTO ventas (cliente_id, subtotal, impuesto, descuento, total, metodo_pago, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (cliente_id, subtotal, impuesto, descuento, total, metodo_pago, notas))
            venta_id = cursor.lastrowid
            # Insertar detalle de venta
            for it in items_venta:
                producto_id = it.get('producto_id')
                cantidad = it.get('cantidad', 0)
                precio = it.get('precio_unitario', 0.0)
                subtotal_item = cantidad * precio
                cursor.execute('''
                    INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                ''', (venta_id, producto_id, cantidad, precio, subtotal_item))
            conn.commit()
            return venta_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_venta_by_id(self, venta_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, cliente_id, fecha_venta, subtotal, impuesto, descuento, total, metodo_pago, estado, notas FROM ventas WHERE id = ?', (venta_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        cols = ['id','cliente_id','fecha_venta','subtotal','impuesto','descuento','total','metodo_pago','estado','notas']
        return dict(zip(cols, row))

    def get_items_venta(self, venta_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        # Unir con tabla productos para obtener el nombre del producto
        cursor.execute('''
            SELECT dv.id, dv.venta_id, dv.producto_id, p.nombre as nombre_producto, dv.cantidad, dv.precio_unitario, dv.subtotal
            FROM detalle_ventas dv
            LEFT JOIN productos p ON p.id = dv.producto_id
            WHERE dv.venta_id = ?
        ''', (venta_id,))
        rows = cursor.fetchall()
        conn.close()
        cols = ['id','venta_id','producto_id','nombre_producto','cantidad','precio_unitario','subtotal']
        return [dict(zip(cols, r)) for r in rows]

    def ensure_pagos_tables(self):
        """Asegura que las tablas necesarias para pagos existan (crea solo las tablas relacionadas con pagos)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pagos_documentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    venta_id INTEGER NOT NULL,
                    numero_documento TEXT,
                    tipo_pago TEXT NOT NULL,
                    monto_pagado REAL NOT NULL,
                    moneda_pago TEXT NOT NULL,
                    tasa_cambio REAL NOT NULL,
                    monto_equivalente_usd REAL,
                    detalles_pago TEXT,
                    fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (venta_id) REFERENCES ventas (id)
                )
            ''')
            conn.commit()
        finally:
            conn.close()
    
    def agregar_categoria(self, nombre, descripcion=None):
        """Agrega una nueva categoría"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO categorias (nombre, descripcion, activo) VALUES (?, ?, 1)", (nombre, descripcion))
        categoria_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return categoria_id

    def actualizar_categoria(self, categoria_id, nuevo_nombre, nueva_descripcion=None):
        """Actualiza el nombre y/o descripción de una categoría"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE categorias SET nombre = ?, descripcion = ? WHERE id = ?", (nuevo_nombre, nueva_descripcion, categoria_id))
        conn.commit()
        conn.close()

    def eliminar_categoria(self, categoria_id):
        """Elimina (desactiva) una categoría"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE categorias SET activo = 0 WHERE id = ?", (categoria_id,))
        conn.commit()
        conn.close()
    def __init__(self, db_name: str = "punto_venta.db"):
        # Determine where to place/use the database file.
        # Desired behavior: when running as a PyInstaller onefile executable we want
        # the database to be located next to the executable so it persists between runs
        # (and is writable). When running from source (not frozen) use the project
        # directory (same folder as this file).
        if os.path.isabs(db_name):
            self.db_name = db_name
        else:
            if getattr(sys, 'frozen', False):
                # Use the directory of the running executable for persistent DB
                exe_dir = os.path.abspath(os.path.dirname(sys.executable))
                self.db_name = os.path.join(exe_dir, db_name)
            else:
                # Running from source: keep DB next to this module
                try:
                    self.db_name = self.resource_path(db_name)
                except Exception:
                    self.db_name = os.path.join(os.path.dirname(__file__), db_name)
        self.init_database()

    def init_database(self):
        """Inicializa la base de datos y crea la tabla pagos_documentos si no existe."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pagos_documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id INTEGER NOT NULL,
                numero_documento TEXT,
                tipo_pago TEXT NOT NULL,
                monto_pagado REAL NOT NULL,
                moneda_pago TEXT NOT NULL,
                tasa_cambio REAL NOT NULL,
                monto_equivalente_usd REAL,
                detalles_pago TEXT,
                fecha_pago TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (venta_id) REFERENCES ventas (id)
            )
        ''')
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Obtiene una conexión a la base de datos"""
        conn = sqlite3.connect(self.db_name, timeout=30.0)
        # Configurar SQLite para mejor rendimiento y menos bloqueos
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=268435456;")  # 256MB
        return conn
    
    def actualizar_stock_producto(self, producto_id: int, cantidad_sumar: int, motivo: str = 'Compra de inventario', usuario: str = 'Sistema'):
        """Suma cantidad_sumar al stock_actual del producto indicado y registra el movimiento de inventario."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Obtener stock anterior
            cursor.execute("SELECT stock_actual FROM productos WHERE id = ?", (producto_id,))
            resultado = cursor.fetchone()
            if resultado is None:
                raise Exception(f"Producto con id {producto_id} no encontrado")
            stock_anterior = resultado[0]
            stock_nuevo = stock_anterior + cantidad_sumar
            # Actualizar stock
            cursor.execute("UPDATE productos SET stock_actual = ?, fecha_modificacion = CURRENT_TIMESTAMP WHERE id = ?", (stock_nuevo, producto_id))
            # Registrar movimiento de inventario
            self.registrar_movimiento_inventario(producto_id, 'entrada', cantidad_sumar, stock_anterior, stock_nuevo, motivo, usuario, cursor)
            conn.commit()
            return stock_nuevo
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_database(self):
        """Inicializa la base de datos con todas las tablas necesarias"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Tabla de categorías
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT,
                activo BOOLEAN DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de productos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_barras TEXT UNIQUE,
                nombre TEXT NOT NULL,
                descripcion TEXT,
                categoria_id INTEGER,
                precio_venta DECIMAL(10,2) NOT NULL,
                precio_compra DECIMAL(10,2),
                precio_venta_usd DECIMAL(10,2),
                precio_compra_usd DECIMAL(10,2),
                stock_actual INTEGER DEFAULT 0,
                stock_minimo INTEGER DEFAULT 0,
                tasa_camb DECIMAL(10,2) DEFAULT 36.50,
                activo BOOLEAN DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                fecha_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                vende_al_mayor BOOLEAN DEFAULT 0,
                unidades_por_bulto INTEGER,
                FOREIGN KEY (categoria_id) REFERENCES categorias (id)
            )
        ''')
        
        # Agregar columna tasa_camb si no existe (para bases de datos existentes)
        try:
            cursor.execute("ALTER TABLE productos ADD COLUMN tasa_camb DECIMAL(10,2) DEFAULT 36.50")
        except sqlite3.OperationalError:
            pass  # La columna ya existe
        # Agregar columna vende_al_mayor si no existe
        try:
            cursor.execute("ALTER TABLE productos ADD COLUMN vende_al_mayor BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        # Agregar columna unidades_por_bulto si no existe
        try:
            cursor.execute("ALTER TABLE productos ADD COLUMN unidades_por_bulto INTEGER")
        except sqlite3.OperationalError:
            pass
        
        # Tabla de proveedores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proveedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                contacto TEXT,
                telefono TEXT,
                email TEXT,
                direccion TEXT,
                rif TEXT,
                notas TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT 1
            )
        ''')
        
        # Tabla de clientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellido TEXT,
                rif TEXT,
                telefono TEXT,
                email TEXT,
                direccion TEXT,
                fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                activo BOOLEAN DEFAULT 1
            )
        ''')
        
        # Tabla de ventas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subtotal DECIMAL(10,2) NOT NULL,
                impuesto DECIMAL(10,2) DEFAULT 0,
                descuento DECIMAL(10,2) DEFAULT 0,
                total DECIMAL(10,2) NOT NULL,
                metodo_pago TEXT DEFAULT 'efectivo',
                estado TEXT DEFAULT 'completada',
                notas TEXT,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id)
            )
        ''')
        
        # Tabla de detalles de venta
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detalle_ventas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venta_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                cantidad REAL NOT NULL,
                precio_unitario DECIMAL(10,2) NOT NULL,
                subtotal DECIMAL(10,2) NOT NULL,
                FOREIGN KEY (venta_id) REFERENCES ventas (id),
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')
        
        # Tabla de movimientos de inventario
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimientos_inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto_id INTEGER NOT NULL,
                tipo_movimiento TEXT NOT NULL, -- 'entrada', 'salida', 'ajuste'
                cantidad REAL NOT NULL,
                cantidad_anterior REAL NOT NULL,
                cantidad_nueva REAL NOT NULL,
                motivo TEXT,
                fecha_movimiento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                usuario TEXT,
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')
        
        # Tabla de ventas en espera (carrito guardado)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ventas_espera (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_operacion TEXT NOT NULL,
                cliente_id INTEGER,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                datos_carrito TEXT, -- JSON con los productos del carrito
                notas TEXT,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id)
            )
        ''')
        
        # Tabla de configuración
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_tienda TEXT DEFAULT 'Mi Tienda',
                direccion_tienda TEXT,
                telefono_tienda TEXT,
                impuesto_por_defecto DECIMAL(5,2) DEFAULT 0.0,
                moneda TEXT DEFAULT '$',
                ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de usuarios
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nombre_completo TEXT NOT NULL,
                rol TEXT DEFAULT 'cajero',
                activo BOOLEAN DEFAULT 1,
                fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ultimo_login TIMESTAMP
            )
        ''')
        
        # Tabla de configuración multimoneda
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion_monedas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                valor TEXT NOT NULL,
                tipo TEXT DEFAULT 'general',
                descripcion TEXT,
                fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabla de compras (Cuentas por pagar)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                proveedor_id INTEGER NOT NULL,
                documento TEXT,
                fecha_compra DATE DEFAULT (DATE('now')),
                tasa_cambio DECIMAL(10,2) NOT NULL,
                subtotal_ves DECIMAL(12,2) NOT NULL,
                total_ves DECIMAL(12,2) NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                notas TEXT,
                FOREIGN KEY (proveedor_id) REFERENCES proveedores (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detalle_compras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compra_id INTEGER NOT NULL,
                producto_id INTEGER NOT NULL,
                cantidad REAL NOT NULL,
                precio_unitario_usd DECIMAL(10,2) NOT NULL,
                precio_unitario_ves DECIMAL(10,2) NOT NULL,
                subtotal_ves DECIMAL(12,2) NOT NULL,
                FOREIGN KEY (compra_id) REFERENCES compras (id),
                FOREIGN KEY (producto_id) REFERENCES productos (id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
        # Insertar datos iniciales
        self.insert_initial_data()
    
    def insert_initial_data(self):
        """Inserta datos iniciales en la base de datos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        
        # Verificar si ya existe configuración
        cursor.execute("SELECT COUNT(*) FROM configuracion")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO configuracion (nombre_tienda, impuesto_por_defecto) 
                VALUES ('Mi Punto de Venta', 0.0)
            """)
        
        # Configuración inicial de monedas
        cursor.execute("SELECT COUNT(*) FROM configuracion_monedas")
        if cursor.fetchone()[0] == 0:
            configuracion_monedas = [
                ('tasa_usd_ves', '36.50', 'moneda', 'Tasa de cambio USD a VES'),
                ('moneda_principal', 'VES', 'moneda', 'Moneda principal del sistema'),
                ('moneda_secundaria', 'USD', 'moneda', 'Moneda secundaria del sistema'),
                ('mostrar_ambas_monedas', '1', 'display', 'Mostrar precios en ambas monedas'),
                ('simbolo_ves', 'Bs.', 'display', 'Símbolo para bolívares'),
                ('simbolo_usd', '$', 'display', 'Símbolo para dólares')
            ]
            
            cursor.executemany("""
                INSERT INTO configuracion_monedas (nombre, valor, tipo, descripcion) 
                VALUES (?, ?, ?, ?)
            """, configuracion_monedas)
        
        # Usuario soporte por defecto
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            import hashlib
            password_hash = hashlib.sha256('soporte123'.encode()).hexdigest()
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre_completo, rol)
                VALUES ('soporte', ?, 'Soporte', 'sistema')
            """, (password_hash,))
        
        conn.commit()
        conn.close()
    
    # MÉTODOS PARA CONFIGURACIÓN DE MONEDAS
    def get_configuracion_moneda(self, nombre):
        """Obtiene un valor de configuración de moneda"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT valor FROM configuracion_monedas WHERE nombre = ?", (nombre,))
        resultado = cursor.fetchone()
        conn.close()
        
        return resultado[0] if resultado else None
    
    def actualizar_configuracion_moneda(self, nombre, valor):
        """Actualiza un valor de configuración de moneda"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE configuracion_monedas 
            SET valor = ?, fecha_actualizacion = CURRENT_TIMESTAMP 
            WHERE nombre = ?
        """, (valor, nombre))
        
        conn.commit()
        conn.close()
    
    def get_tasa_cambio(self):
        """Obtiene la tasa de cambio actual USD a VES"""
        tasa = self.get_configuracion_moneda('tasa_usd_ves')
        return float(tasa) if tasa else 36.50
    
    def actualizar_tasa_cambio(self, nueva_tasa):
        """Actualiza la tasa de cambio USD a VES y recalcula precios VES"""
        # Actualizar la tasa de cambio
        self.actualizar_configuracion_moneda('tasa_usd_ves', str(nueva_tasa))
        
        # Recalcular automáticamente los precios VES de todos los productos
        self.recalcular_precios_ves(nueva_tasa)
    
    def recalcular_precios_ves(self, nueva_tasa=None):
        """Recalcula todos los precios VES usando los precios USD base y la nueva tasa"""
        if nueva_tasa is None:
            nueva_tasa = self.get_tasa_cambio()
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Fórmula correcta: precio_venta = precio_venta_usd * tasa_cambio
            cursor.execute("""
                UPDATE productos 
                SET precio_venta = ROUND(precio_venta_usd * ?, 2),
                    precio_compra = ROUND(precio_compra_usd * ?, 2),
                    tasa_camb = ?
                WHERE precio_venta_usd IS NOT NULL AND precio_compra_usd IS NOT NULL
            """, (nueva_tasa, nueva_tasa, nueva_tasa))
            
            productos_actualizados = cursor.rowcount
            conn.commit()
            
            return productos_actualizados
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def recalcular_precios_usd(self, nueva_tasa=None):
        """Método legacy - ahora usa recalcular_precios_ves"""
        return self.recalcular_precios_ves(nueva_tasa)

    # MÉTODOS PARA COMPRAS (CUENTAS POR PAGAR)
    def crear_compra(self, proveedor_id: int, documento: str, fecha_compra: str, tasa_cambio: float, items: List[Dict], notas: str = "") -> int:
        """
        Crea una compra con sus detalles y actualiza inventario y precios de compra.
        items: lista de dicts con claves: producto_id, cantidad, precio_unitario_usd
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("BEGIN IMMEDIATE;")
            # Calcular totales
            subtotal_ves = 0.0
            for it in items:
                precio_ves = round((it.get('precio_unitario_usd', 0.0) or 0.0) * tasa_cambio, 2)
                subtotal_ves += round(precio_ves * it['cantidad'], 2)
            total_ves = subtotal_ves
            # Insertar compra
            cursor.execute(
                """
                INSERT INTO compras (proveedor_id, documento, fecha_compra, tasa_cambio, subtotal_ves, total_ves, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (proveedor_id, documento, fecha_compra, tasa_cambio, subtotal_ves, total_ves, notas)
            )
            compra_id = cursor.lastrowid
            # Insertar detalles y actualizar inventario y costos
            for it in items:
                prod_id = it['producto_id']
                cant = float(it['cantidad'])
                precio_usd = float(it.get('precio_unitario_usd', 0.0) or 0.0)
                precio_ves = round(precio_usd * tasa_cambio, 2)
                subtotal_item_ves = round(precio_ves * cant, 2)
                cursor.execute(
                    """
                    INSERT INTO detalle_compras (compra_id, producto_id, cantidad, precio_unitario_usd, precio_unitario_ves, subtotal_ves)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (compra_id, prod_id, cant, precio_usd, precio_ves, subtotal_item_ves)
                )
                # Actualizar precio de compra en producto (USD y VES) y tasa_camb usada
                cursor.execute(
                    """
                    UPDATE productos
                    SET precio_compra_usd = ?,
                        precio_compra = ?,
                        tasa_camb = ?
                    WHERE id = ?
                    """,
                    (precio_usd, precio_ves, tasa_cambio, prod_id)
                )
                # Actualizar stock e insertar movimiento
                cursor.execute("SELECT stock_actual FROM productos WHERE id = ?", (prod_id,))
                row = cursor.fetchone()
                if not row:
                    raise Exception(f"Producto id {prod_id} no encontrado")
                stock_anterior = float(row[0])
                stock_nuevo = stock_anterior + cant
                cursor.execute("UPDATE productos SET stock_actual = ? WHERE id = ?", (stock_nuevo, prod_id))
                # movimiento inventario
                cursor.execute(
                    """
                    INSERT INTO movimientos_inventario (producto_id, tipo_movimiento, cantidad, cantidad_anterior, cantidad_nueva, motivo, usuario)
                    VALUES (?, 'entrada', ?, ?, ?, ?, ?)
                    """,
                    (prod_id, cant, stock_anterior, stock_nuevo, f'Compra #{compra_id}', 'Sistema')
                )
            conn.commit()
            return compra_id
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_compras(self):
        """Obtiene compras con datos del proveedor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT co.id, co.documento, co.fecha_compra, co.tasa_cambio, co.subtotal_ves, co.total_ves, co.estado,
                   pr.nombre as proveedor_nombre, pr.rif, pr.telefono
            FROM compras co
            JOIN proveedores pr ON pr.id = co.proveedor_id
            ORDER BY co.fecha_compra DESC, co.id DESC
            """
        )
        rows = cursor.fetchall()
        result = [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        conn.close()
        return result

    def get_detalle_compra(self, compra_id: int):
        """Obtiene el detalle de una compra con nombres de productos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT dc.id, p.nombre as producto, dc.cantidad, dc.precio_unitario_usd, dc.precio_unitario_ves, dc.subtotal_ves
            FROM detalle_compras dc
            JOIN productos p ON p.id = dc.producto_id
            WHERE dc.compra_id = ?
            """,
            (compra_id,)
        )
        rows = cursor.fetchall()
        result = [dict(zip([col[0] for col in cursor.description], row)) for row in rows]
        conn.close()
        return result
    
    def convertir_usd_a_ves(self, monto_usd):
        """Convierte monto de USD a VES"""
        tasa = self.get_tasa_cambio()
        return monto_usd * tasa
    
    def convertir_ves_a_usd(self, monto_ves):
        """Convierte monto de VES a USD"""
        tasa = self.get_tasa_cambio()
        return monto_ves / tasa if tasa > 0 else 0
    
    def mostrar_ambas_monedas(self):
        """Verifica si se deben mostrar ambas monedas"""
        mostrar = self.get_configuracion_moneda('mostrar_ambas_monedas')
        return mostrar == '1' if mostrar else True
    
    def get_simbolos_monedas(self):
        """Obtiene los símbolos de ambas monedas"""
        simbolo_ves = self.get_configuracion_moneda('simbolo_ves') or 'Bs.'
        simbolo_usd = self.get_configuracion_moneda('simbolo_usd') or '$'
        return {'VES': simbolo_ves, 'USD': simbolo_usd}

    def get_monedas_activas(self):
        """Devuelve la lista de monedas activas configuradas en el sistema"""
        monedas = []
        # VES siempre está activa
        simbolo_ves = self.get_configuracion_moneda('simbolo_ves') or 'Bs.'
        monedas.append({'codigo': 'VES', 'simbolo': simbolo_ves})
        # USD puede estar activa si la tasa está configurada
        tasa_usd = self.get_tasa_cambio()
        if tasa_usd and tasa_usd > 0:
            simbolo_usd = self.get_configuracion_moneda('simbolo_usd') or '$'
            monedas.append({'codigo': 'USD', 'simbolo': simbolo_usd})
        return monedas
    
    # MÉTODOS PARA PRODUCTOS
    def get_productos(self, categoria_id=None, activos_solo=True):
        """Obtiene todos los productos, opcionalmente filtrados por categoría"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT p.id, p.codigo_barras, p.nombre, p.descripcion, p.precio_venta, 
                   p.precio_venta_usd, p.precio_compra, p.precio_compra_usd, p.stock_actual, p.tasa_camb,
                   p.vende_al_mayor, p.unidades_por_bulto,
                   c.nombre as categoria
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE 1=1
        """
        params = []
        
        if activos_solo:
            query += " AND p.activo = 1"
        if categoria_id:
            query += " AND p.categoria_id = ?"
            params.append(categoria_id)
        
        query += " ORDER BY p.nombre"
        
        cursor.execute(query, params)
        productos = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], row)) for row in productos]
    
    def buscar_productos(self, termino_busqueda):
        """Busca productos por nombre, código de barras, código QR o descripción"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Limpiar el término de búsqueda
        termino_limpio = termino_busqueda.strip()
        
        if not termino_limpio:
            conn.close()
            return []
        
        # Si el término es exacto (código de barras o QR), buscar coincidencia exacta primero
        query_exacta = """
            SELECT p.id, p.codigo_barras, p.nombre, p.descripcion, p.precio_venta, 
                   p.precio_venta_usd, p.precio_compra, p.precio_compra_usd,
                   p.stock_actual, p.tasa_camb, p.vende_al_mayor, p.unidades_por_bulto,
                   c.nombre as categoria
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = 1 AND (
                p.codigo_barras = ? OR
                p.codigo_barras LIKE ?
            )
            ORDER BY 
                CASE WHEN p.codigo_barras = ? THEN 1 ELSE 2 END,
                p.nombre
        """
        
        cursor.execute(query_exacta, (termino_limpio, f"%{termino_limpio}%", termino_limpio))
        productos_exactos = cursor.fetchall()
        
        # Si encontramos coincidencias exactas, devolverlas
        if productos_exactos:
            conn.close()
            return [dict(zip([col[0] for col in cursor.description], row)) for row in productos_exactos]
        
        # Si no hay coincidencias exactas, buscar por nombre y descripción
        query_general = """
            SELECT p.id, p.codigo_barras, p.nombre, p.descripcion, p.precio_venta, 
                   p.precio_venta_usd, p.precio_compra, p.precio_compra_usd,
                   p.stock_actual, p.tasa_camb, p.vende_al_mayor, p.unidades_por_bulto,
                   c.nombre as categoria
            FROM productos p
            LEFT JOIN categorias c ON p.categoria_id = c.id
            WHERE p.activo = 1 AND (
                p.nombre LIKE ? OR 
                p.descripcion LIKE ? OR
                p.codigo_barras LIKE ?
            )
            ORDER BY 
                CASE 
                    WHEN p.nombre LIKE ? THEN 1
                    WHEN p.descripcion LIKE ? THEN 2
                    ELSE 3
                END,
                p.nombre
        """
        
        termino_like = f"%{termino_limpio}%"
        cursor.execute(query_general, (termino_like, termino_like, termino_like, termino_like, termino_like))
        productos = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], row)) for row in productos]
    
    def agregar_producto(self, codigo_barras, nombre, descripcion, categoria_id, 
                        precio_venta, precio_compra, stock_inicial=0, stock_minimo=0):
        """Agrega un nuevo producto"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO productos (codigo_barras, nombre, descripcion, categoria_id, 
                                     precio_venta, precio_compra, stock_actual, stock_minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (codigo_barras, nombre, descripcion, categoria_id, precio_venta, 
                  precio_compra, stock_inicial, stock_minimo))
            
            producto_id = cursor.lastrowid
            
            # Registrar movimiento de inventario inicial
            if stock_inicial > 0:
                self.registrar_movimiento_inventario(
                    producto_id, 'entrada', stock_inicial, 0, stock_inicial, 
                    'Stock inicial', 'Sistema', cursor
                )
            
            conn.commit()
            return producto_id
        except sqlite3.IntegrityError:
            conn.rollback()
            raise Exception("El código de barras ya existe")
        finally:
            conn.close()
    
    # MÉTODOS PARA CATEGORÍAS
    def get_categorias(self):
        """Obtiene todas las categorías activas"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre FROM categorias WHERE activo = 1 ORDER BY nombre")
        categorias = cursor.fetchall()
        conn.close()
        return [{'id': row[0], 'nombre': row[1]} for row in categorias]
    
    # MÉTODOS PARA CLIENTES
    def get_clientes(self):
        """Obtiene todos los clientes activos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, apellido, rif, telefono, email 
            FROM clientes WHERE activo = 1 ORDER BY nombre
        """)
        clientes = cursor.fetchall()
        conn.close()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in clientes]
    
    def buscar_cliente(self, termino):
        """Busca clientes por nombre o teléfono"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, nombre, apellido, rif, telefono, email 
            FROM clientes 
            WHERE activo = 1 AND (
                nombre LIKE ? OR apellido LIKE ? OR telefono LIKE ?
            )
            ORDER BY nombre
        """
        termino_like = f"%{termino}%"
        cursor.execute(query, (termino_like, termino_like, termino_like))
        clientes = cursor.fetchall()
        conn.close()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in clientes]
    
    def agregar_cliente(self, nombre, apellido="", telefono="", email="", direccion="", rif=None):
        """Agrega un nuevo cliente"""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Asegurar que la columna rif exista (para bases de datos antiguas)
        try:
            cursor.execute("ALTER TABLE clientes ADD COLUMN rif TEXT")
            conn.commit()
        except Exception:
            # Si falla, probablemente la columna ya existe; ignorar
            conn.rollback()

        cursor.execute("""
            INSERT INTO clientes (nombre, apellido, rif, telefono, email, direccion)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (nombre, apellido, rif, telefono, email, direccion))
        
        cliente_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return cliente_id
    
    # MÉTODOS PARA VENTAS
    def crear_venta(self, items_venta, cliente_id=None, metodo_pago='efectivo', 
                   descuento=0.0, impuesto=0.0, notas=""):
        """Crea una nueva venta"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Habilitar transacciones inmediatas para evitar bloqueos
            cursor.execute("BEGIN IMMEDIATE;")
            
            # Calcular totales
            subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in items_venta)
            total = subtotal + impuesto - descuento
            
            # Insertar venta
            cursor.execute("""
                INSERT INTO ventas (cliente_id, subtotal, impuesto, descuento, total, 
                                  metodo_pago, notas)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cliente_id, subtotal, impuesto, descuento, total, metodo_pago, notas))
            
            venta_id = cursor.lastrowid
            
            # Insertar detalles de venta y actualizar inventario
            for item in items_venta:
                # Insertar detalle
                cursor.execute("""
                    INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, 
                                              precio_unitario, subtotal)
                    VALUES (?, ?, ?, ?, ?)
                """, (venta_id, item['producto_id'], item['cantidad'], 
                      item['precio_unitario'], item['cantidad'] * item['precio_unitario']))
                
                # Obtener stock anterior
                cursor.execute("SELECT stock_actual FROM productos WHERE id = ?", (item['producto_id'],))
                stock_anterior = cursor.fetchone()[0]
                stock_nuevo = stock_anterior - item['cantidad']
                
                # Actualizar stock del producto
                cursor.execute("""
                    UPDATE productos 
                    SET stock_actual = ? 
                    WHERE id = ?
                """, (stock_nuevo, item['producto_id']))
                
                # Registrar movimiento de inventario (sin crear nueva conexión)
                cursor.execute("""
                    INSERT INTO movimientos_inventario 
                    (producto_id, tipo_movimiento, cantidad, cantidad_anterior, cantidad_nueva, 
                     motivo, usuario)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (item['producto_id'], 'salida', item['cantidad'], 
                      stock_anterior, stock_nuevo, f'Venta #{venta_id}', 'Sistema'))
            
            conn.commit()
            return venta_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_venta_detalle(self, venta_id):
        """Obtiene el detalle completo de una venta"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Datos de la venta
        cursor.execute("""
            SELECT v.*, c.nombre as cliente_nombre, c.apellido as cliente_apellido
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE v.id = ?
        """, (venta_id,))
        
        venta = cursor.fetchone()
        if not venta:
            return None
        
        venta_dict = dict(zip([col[0] for col in cursor.description], venta))
        
        # Detalles de la venta
        cursor.execute("""
            SELECT dv.*, p.nombre as producto_nombre
            FROM detalle_ventas dv
            JOIN productos p ON dv.producto_id = p.id
            WHERE dv.venta_id = ?
        """, (venta_id,))
        
        detalles = cursor.fetchall()
        venta_dict['detalles'] = [dict(zip([col[0] for col in cursor.description], row)) 
                                 for row in detalles]
        
        conn.close()
        return venta_dict
    
    # MÉTODOS PARA MOVIMIENTOS DE INVENTARIO
    def registrar_movimiento_inventario(self, producto_id, tipo_movimiento, cantidad, 
                                      cantidad_anterior, cantidad_nueva, motivo, usuario, cursor=None):
        """Registra un movimiento de inventario"""
        if cursor:
            # Usar cursor existente (para transacciones)
            cursor.execute("""
                INSERT INTO movimientos_inventario 
                (producto_id, tipo_movimiento, cantidad, cantidad_anterior, cantidad_nueva, 
                 motivo, usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (producto_id, tipo_movimiento, cantidad, cantidad_anterior, 
                  cantidad_nueva, motivo, usuario))
        else:
            # Crear nueva conexión (para operaciones independientes)
            conn = self.get_connection()
            cursor_temp = conn.cursor()
            
            cursor_temp.execute("""
                INSERT INTO movimientos_inventario 
                (producto_id, tipo_movimiento, cantidad, cantidad_anterior, cantidad_nueva, 
                 motivo, usuario)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (producto_id, tipo_movimiento, cantidad, cantidad_anterior, 
                  cantidad_nueva, motivo, usuario))
            
            conn.commit()
            conn.close()
    
    # MÉTODOS PARA OPERACIONES EN ESPERA
    def guardar_operacion_espera(self, nombre_operacion, carrito_data, cliente_id=None, notas=""):
        """Guarda una operación de venta en espera"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        import json
        cursor.execute("""
            INSERT INTO ventas_espera (nombre_operacion, cliente_id, datos_carrito, notas)
            VALUES (?, ?, ?, ?)
        """, (nombre_operacion, cliente_id, json.dumps(carrito_data), notas))
        
        operacion_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return operacion_id
    
    def get_operaciones_espera(self):
        """Obtiene todas las operaciones en espera"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ve.*, c.nombre as cliente_nombre
            FROM ventas_espera ve
            LEFT JOIN clientes c ON ve.cliente_id = c.id
            ORDER BY ve.fecha_creacion DESC
        """)
        
        operaciones = cursor.fetchall()
        conn.close()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in operaciones]
    
    def cargar_operacion_espera(self, operacion_id):
        """Carga una operación en espera"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ventas_espera WHERE id = ?", (operacion_id,))
        operacion = cursor.fetchone()
        
        if operacion:
            import json
            operacion_dict = dict(zip([col[0] for col in cursor.description], operacion))
            operacion_dict['datos_carrito'] = json.loads(operacion_dict['datos_carrito'])
            conn.close()
            return operacion_dict
        
        conn.close()
        return None
    
    def eliminar_operacion_espera(self, operacion_id):
        """Elimina una operación en espera"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ventas_espera WHERE id = ?", (operacion_id,))
        conn.commit()
        conn.close()
    
    # MÉTODOS PARA REPORTES
    def get_ventas_fecha(self, fecha_inicio, fecha_fin=None):
        """Obtiene las ventas entre fechas"""
        if fecha_fin is None:
            fecha_fin = fecha_inicio
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT v.*, c.nombre as cliente_nombre, c.apellido as cliente_apellido
            FROM ventas v
            LEFT JOIN clientes c ON v.cliente_id = c.id
            WHERE DATE(v.fecha_venta) BETWEEN ? AND ?
            ORDER BY v.fecha_venta DESC
        """, (fecha_inicio, fecha_fin))
        
        ventas = cursor.fetchall()
        conn.close()
        return [dict(zip([col[0] for col in cursor.description], row)) for row in ventas]
    
    def get_corte_dia(self, fecha=None):
        """Obtiene el corte del día con información detallada"""
        if fecha is None:
            fecha = date.today().strftime('%Y-%m-%d')
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Total general del día
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_ventas,
                    COALESCE(SUM(total), 0) as total_ingresos,
                    COALESCE(SUM(subtotal), 0) as total_subtotal,
                    COALESCE(SUM(impuesto), 0) as total_impuesto,
                    COALESCE(SUM(descuento), 0) as total_descuento,
                    COALESCE(AVG(total), 0) as ticket_promedio
                FROM ventas 
                WHERE DATE(fecha_venta) = ?
            """, (fecha,))
            
            totales_row = cursor.fetchone()
            totales = {
                'total_ventas': totales_row[0] if totales_row else 0,
                'total_ingresos': totales_row[1] if totales_row else 0.0,
                'total_subtotal': totales_row[2] if totales_row else 0.0,
                'total_impuesto': totales_row[3] if totales_row else 0.0,
                'total_descuento': totales_row[4] if totales_row else 0.0,
                'ticket_promedio': totales_row[5] if totales_row else 0.0
            }
            
            # Resumen por método de pago
            cursor.execute("""
                SELECT 
                    metodo_pago,
                    COUNT(*) as ventas_por_metodo,
                    SUM(total) as total_por_metodo,
                    ROUND(AVG(total), 2) as promedio_por_metodo
                FROM ventas 
                WHERE DATE(fecha_venta) = ?
                GROUP BY metodo_pago
                ORDER BY total_por_metodo DESC
            """, (fecha,))
            
            resumen_pagos = []
            for row in cursor.fetchall():
                resumen_pagos.append({
                    'metodo_pago': row[0],
                    'ventas_por_metodo': row[1],
                    'total_por_metodo': row[2],
                    'promedio_por_metodo': row[3]
                })
            
            # Productos más vendidos del día
            cursor.execute("""
                SELECT 
                    p.nombre,
                    SUM(dv.cantidad) as cantidad_vendida,
                    SUM(dv.subtotal) as total_vendido,
                    dv.precio_unitario
                FROM detalle_ventas dv
                JOIN productos p ON dv.producto_id = p.id
                JOIN ventas v ON dv.venta_id = v.id
                WHERE DATE(v.fecha_venta) = ?
                GROUP BY p.id, p.nombre, dv.precio_unitario
                ORDER BY cantidad_vendida DESC
                LIMIT 10
            """, (fecha,))
            
            productos_vendidos = []
            for row in cursor.fetchall():
                productos_vendidos.append({
                    'nombre': row[0],
                    'cantidad_vendida': row[1],
                    'total_vendido': row[2],
                    'precio_unitario': row[3]
                })
            
            # Ventas por horas (para gráfico de actividad)
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN CAST(strftime('%H', fecha_venta) AS INTEGER) BETWEEN 6 AND 11 THEN 'Mañana (6-11)'
                        WHEN CAST(strftime('%H', fecha_venta) AS INTEGER) BETWEEN 12 AND 17 THEN 'Tarde (12-17)'
                        WHEN CAST(strftime('%H', fecha_venta) AS INTEGER) BETWEEN 18 AND 23 THEN 'Noche (18-23)'
                        ELSE 'Madrugada (0-5)'
                    END as periodo,
                    COUNT(*) as ventas_periodo,
                    SUM(total) as total_periodo
                FROM ventas 
                WHERE DATE(fecha_venta) = ?
                GROUP BY periodo
                ORDER BY ventas_periodo DESC
            """, (fecha,))
            
            actividad_por_periodo = []
            for row in cursor.fetchall():
                actividad_por_periodo.append({
                    'periodo': row[0],
                    'ventas_periodo': row[1],
                    'total_periodo': row[2]
                })
            
            # Estadísticas adicionales
            cursor.execute("""
                SELECT 
                    MIN(total) as venta_minima,
                    MAX(total) as venta_maxima,
                    COUNT(DISTINCT cliente_id) as clientes_unicos
                FROM ventas 
                WHERE DATE(fecha_venta) = ? AND cliente_id IS NOT NULL
            """, (fecha,))
            
            stats_row = cursor.fetchone()
            estadisticas_adicionales = {
                'venta_minima': stats_row[0] if stats_row[0] else 0.0,
                'venta_maxima': stats_row[1] if stats_row[1] else 0.0,
                'clientes_unicos': stats_row[2] if stats_row[2] else 0
            }
            
            return {
                'fecha': fecha,
                'totales': totales,
                'resumen_pagos': resumen_pagos,
                'productos_mas_vendidos': productos_vendidos,
                'actividad_por_periodo': actividad_por_periodo,
                'estadisticas_adicionales': estadisticas_adicionales
            }
            
        except Exception as e:
            print(f"Error en get_corte_dia: {e}")
            return {
                'fecha': fecha,
                'totales': {'total_ventas': 0, 'total_ingresos': 0.0, 'total_subtotal': 0.0, 'total_impuesto': 0.0, 'total_descuento': 0.0, 'ticket_promedio': 0.0},
                'resumen_pagos': [],
                'productos_mas_vendidos': [],
                'actividad_por_periodo': [],
                'estadisticas_adicionales': {'venta_minima': 0.0, 'venta_maxima': 0.0, 'clientes_unicos': 0}
            }
        finally:
            conn.close()
    
    # MÉTODOS PARA AUTENTICACIÓN
    def validar_usuario(self, username, password):
        """Valida las credenciales de un usuario"""
        import hashlib
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Hash de la contraseña proporcionada
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute("""
                SELECT id, username, nombre_completo, rol 
                FROM usuarios 
                WHERE username = ? AND password_hash = ? AND activo = 1
            """, (username, password_hash))
            
            usuario = cursor.fetchone()
            
            if usuario:
                # Actualizar último login
                cursor.execute(
                    "UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP WHERE id = ?",
                    (usuario[0],)
                )
                conn.commit()
                
                return {
                    'id': usuario[0],
                    'username': usuario[1],
                    'nombre_completo': usuario[2],
                    'rol': usuario[3]
                }
            
            return None
            
        except Exception as e:
            print(f"Error en validación: {e}")
            return None
        finally:
            conn.close()
    
    def crear_usuario(self, username, password, nombre_completo, rol='cajero'):
        """Crea un nuevo usuario"""
        import hashlib
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            cursor.execute("""
                INSERT INTO usuarios (username, password_hash, nombre_completo, rol)
                VALUES (?, ?, ?, ?)
            """, (username, password_hash, nombre_completo, rol))
            
            usuario_id = cursor.lastrowid
            conn.commit()
            return usuario_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_usuarios(self):
        """Obtiene todos los usuarios activos"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, username, nombre_completo, rol, fecha_creacion, ultimo_login
            FROM usuarios
            WHERE activo = 1
            ORDER BY nombre_completo
        """)
        
        usuarios = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], row)) for row in usuarios]
    
    # ===========================================
    # MÉTODOS PARA PROVEEDORES
    # ===========================================
    
    def agregar_proveedor(self, nombre, contacto=None, telefono=None, email=None, direccion=None, rif=None, notas=None):
        """Agrega un nuevo proveedor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO proveedores (nombre, contacto, telefono, email, direccion, rif, notas, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (nombre, contacto, telefono, email, direccion, rif, notas))
            
            proveedor_id = cursor.lastrowid
            conn.commit()
            return proveedor_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_proveedores(self, incluir_inactivos=False):
        """Obtiene todos los proveedores"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if incluir_inactivos:
            cursor.execute("""
                SELECT id, nombre, contacto, telefono, email, direccion, rif, notas, 
                       fecha_registro, activo
                FROM proveedores
                ORDER BY nombre
            """)
        else:
            cursor.execute("""
                SELECT id, nombre, contacto, telefono, email, direccion, rif, notas, 
                       fecha_registro, activo
                FROM proveedores
                WHERE activo = 1
                ORDER BY nombre
            """)
        
        proveedores = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], row)) for row in proveedores]
    
    def get_proveedor_by_id(self, proveedor_id):
        """Obtiene un proveedor por su ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, nombre, contacto, telefono, email, direccion, rif, notas, 
                   fecha_registro, activo
            FROM proveedores
            WHERE id = ?
        """, (proveedor_id,))
        
        proveedor = cursor.fetchone()
        conn.close()
        
        if proveedor:
            return dict(zip([col[0] for col in cursor.description], proveedor))
        return None
    
    def actualizar_proveedor(self, proveedor_id, nombre, contacto=None, telefono=None, 
                           email=None, direccion=None, rif=None, notas=None):
        """Actualiza los datos de un proveedor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE proveedores 
                SET nombre = ?, contacto = ?, telefono = ?, email = ?, 
                    direccion = ?, rif = ?, notas = ?
                WHERE id = ?
            """, (nombre, contacto, telefono, email, direccion, rif, notas, proveedor_id))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def eliminar_proveedor(self, proveedor_id):
        """Desactiva un proveedor (eliminación lógica)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE proveedores SET activo = 0 WHERE id = ?", (proveedor_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def buscar_proveedores(self, termino_busqueda):
        """Busca proveedores por nombre, contacto o teléfono"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        termino = f"%{termino_busqueda}%"
        cursor.execute("""
            SELECT id, nombre, contacto, telefono, email, direccion, rif, notas, 
                   fecha_registro, activo
            FROM proveedores
            WHERE activo = 1 AND (
                nombre LIKE ? OR
                contacto LIKE ? OR
                telefono LIKE ? OR
                rif LIKE ?
            )
            ORDER BY nombre
        """, (termino, termino, termino, termino))
        
        proveedores = cursor.fetchall()
        conn.close()
        
        return [dict(zip([col[0] for col in cursor.description], row)) for row in proveedores]
