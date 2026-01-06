# Punto de Venta - Versión Web (Flask)

Este proyecto ha sido transformado de una aplicación desktop (tkinter) a una aplicación web usando Flask.

## Características

- ✅ Sistema de autenticación con sesiones
- ✅ Gestión de productos e inventario
- ✅ Gestión de clientes
- ✅ Sistema de ventas con carrito
- ✅ Gestión de compras y proveedores
- ✅ Corte del día y reportes
- ✅ Gestión de usuarios
- ✅ Configuración de empresa
- ✅ Soporte multimoneda (USD/VES)
- ✅ Operaciones en espera

## Instalación

1. Instalar dependencias:
```bash
pip install -r requirements.txt
```

2. La base de datos SQLite (`punto_venta.db`) se mantiene igual que en la versión desktop.

3. Ejecutar la aplicación:
```bash
python app.py
```

4. Abrir en el navegador:
```
http://localhost:5000
```

## Credenciales por defecto

- Usuario: `soporte`
- Contraseña: `soporte123`

## Estructura del Proyecto

```
punto-de-venta-1.2/
├── app.py                 # Aplicación Flask principal
├── database.py            # Gestión de base de datos (sin cambios)
├── requirements.txt        # Dependencias Python
├── templates/             # Templates HTML
│   ├── base.html
│   ├── login.html
│   ├── punto_venta.html
│   ├── inventario.html
│   ├── clientes.html
│   ├── compras.html
│   ├── corte_dia.html
│   ├── usuarios.html
│   └── configuracion.html
└── static/                # Archivos estáticos
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## Diferencias con la versión desktop

1. **Interfaz**: HTML/CSS/JavaScript en lugar de tkinter
2. **Navegación**: URLs y rutas en lugar de ventanas modales
3. **Sesiones**: Sistema de sesiones web en lugar de estado local
4. **API REST**: Endpoints JSON para operaciones dinámicas
5. **Responsive**: Diseño adaptable a diferentes tamaños de pantalla

## Funcionalidades implementadas

### ✅ Completas
- Login y autenticación
- Pantalla principal de punto de venta
- Carrito de compras
- Búsqueda de productos
- Filtrado por categorías
- Gestión básica de clientes
- Creación de ventas
- Vista de inventario
- Vista de compras
- Corte del día
- Gestión de usuarios
- Configuración

### 🔄 Por mejorar/expandir
- Modal completo de procesamiento de pago
- Búsqueda avanzada de clientes
- Formularios completos de edición
- Exportación de reportes a PDF
- Operaciones en espera (UI completa)
- Gestión completa de proveedores

## Notas

- La base de datos se mantiene compatible con la versión desktop
- Los datos existentes se pueden seguir usando
- El sistema de autenticación usa las mismas credenciales
- La lógica de negocio está en `database.py` (sin cambios)

## Desarrollo

Para desarrollo, ejecutar con:
```bash
export FLASK_ENV=development
python app.py
```

Para producción, usar un servidor WSGI como Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```


