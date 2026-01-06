import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import ctypes
import os
import sqlite3
import shutil
from datetime import datetime, timedelta
import threading
import json
from responsive_window import ResponsiveWindow
from colores_modernos import (
    PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR, BACKGROUND_COLOR, 
    CARD_COLOR, TEXT_COLOR, SUBTEXT_COLOR, SUCCESS_COLOR, ERROR_COLOR, 
    BUTTON_COLOR, BUTTON_TEXT_COLOR, BORDER_RADIUS, FONT_FAMILY, 
    TITLE_FONT_SIZE, SUBTITLE_FONT_SIZE, TEXT_FONT_SIZE, BUTTON_FONT_SIZE
)

class BackupWindow(ResponsiveWindow):
    def __init__(self, parent, database_manager):
        self.db = database_manager
        self.config_file = "backup_config.json"
        self.is_backup_running = False
        
        # Inicializar ventana responsiva
        super().__init__(parent, "Sistema de Respaldos", min_width=320, min_height=520)
        try:
            self.window.overrideredirect(True)
            try:
                self.window.lift()
                self.window.attributes('-topmost', True)
                self.window.focus_force()
            except Exception:
                pass
        except Exception:
            pass
        # Topbar personalizada
        try:
            self.topbar = ctk.CTkFrame(self.window, height=36, fg_color=BACKGROUND_COLOR, corner_radius=0)
            self.topbar.place(x=0, y=0, relwidth=1.0)
            self.topbar_title = ctk.CTkLabel(self.topbar, text="Sistema de Respaldos", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_COLOR, fg_color=BACKGROUND_COLOR)
            self.topbar_title.place(x=10, y=6)
            close_btn = ctk.CTkButton(self.topbar, text="✖", width=30, height=30, fg_color=BACKGROUND_COLOR, hover_color="#f2f2f2", text_color=TEXT_COLOR, corner_radius=8, command=self.window.destroy)
            close_btn.place(relx=1.0, x=-10, y=3, anchor='ne')
            try:
                self.topbar.bind('<ButtonPress-1>', self._start_move)
                self.topbar.bind('<B1-Motion>', self._on_move)
                self.topbar.bind('<ButtonRelease-1>', self._stop_move)
                self.topbar_title.bind('<ButtonPress-1>', self._start_move)
                self.topbar_title.bind('<B1-Motion>', self._on_move)
                self.topbar_title.bind('<ButtonRelease-1>', self._stop_move)
            except Exception:
                pass
            try:
                self.window.update_idletasks()
                self.set_round_corners(14)
                self.window.bind('<Configure>', lambda e: self.set_round_corners(14))
            except Exception:
                pass
            # Spacer para dejar sitio al topbar
            spacer = ctk.CTkFrame(self.window, fg_color=BACKGROUND_COLOR, height=12, corner_radius=0)
            spacer.place(x=0, y=36, relwidth=1.0)
        except Exception:
            pass
        
        # For this window we want a fixed initial geometry of 700x800 (centered)
        try:
            desired_w, desired_h = 700, 800
            sw = getattr(self, 'screen_width', parent.winfo_screenwidth())
            sh = getattr(self, 'screen_height', parent.winfo_screenheight())
            x = (sw - desired_w) // 2
            y = (sh - desired_h) // 2
            self.window.geometry(f"{desired_w}x{desired_h}+{x}+{y}")
            # Ensure the window minimums reflect this geometry so layout doesn't collapse
            try:
                self.window.minsize(desired_w, desired_h)
            except Exception:
                pass
            # Update responsive tracking values
            try:
                self._last_width = desired_w
                self._last_height = desired_h
            except Exception:
                pass
        except Exception:
            pass

        self.load_config()
        self.show()
        
    def load_config(self):
        """Carga la configuración de respaldos"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # Configuración por defecto
                self.config = {
                    'backup_path': os.path.join(os.path.expanduser("~"), "Documents", "Respaldos_PuntoVenta"),
                    'auto_backup_enabled': True,
                    'backup_frequency_hours': 24,
                    'max_backups': 10,
                    'last_backup': None
                }
                self.save_config()
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            self.config = {
                'backup_path': os.path.join(os.path.expanduser("~"), "Documents", "Respaldos_PuntoVenta"),
                'auto_backup_enabled': True,
                'backup_frequency_hours': 24,
                'max_backups': 10,
                'last_backup': None
            }

    def save_config(self):
        """Guarda la configuración de respaldos"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando configuración: {e}")

    def setup_ui(self):
        """Configura la interfaz de usuario (responsiva)"""
        # Obtener padding responsivo
        padding = self.get_responsive_padding(10)
        
        # Frame principal
        main_frame = ctk.CTkScrollableFrame(self.window, fg_color=BACKGROUND_COLOR)
        if hasattr(self, 'topbar'):
            top_padding = 46
            main_frame.pack(fill="both", expand=True, padx=2, pady=(top_padding, 2))
        else:
            main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Título responsivo
        title_label = self.create_responsive_label(
            main_frame,
            text="🗄️ Sistema de Respaldos de Base de Datos",
            category='title',
            text_color=PRIMARY_COLOR
        )
        title_label.pack(pady=(0, self.get_responsive_margin(20)))
        
        # Sección de respaldo manual
        self.setup_manual_backup_section(main_frame)
        
        # Sección de configuración
        self.setup_configuration_section(main_frame)
        
        # Sección de historial
        self.setup_history_section(main_frame)
        
        # Botones de acción
        self.setup_action_buttons(main_frame)

    def setup_manual_backup_section(self, parent):
        """Configura la sección de respaldo manual"""
        manual_frame = ctk.CTkFrame(parent, fg_color=CARD_COLOR)
        manual_frame.pack(fill="x", pady=(0, 8), padx=1)
        
        ctk.CTkLabel(
            manual_frame,
            text="📋 Respaldo Manual",
            font=ctk.CTkFont(size=SUBTITLE_FONT_SIZE-2, weight="bold")
        ).pack(pady=(10, 8))
        
        info_frame = ctk.CTkFrame(manual_frame, fg_color="transparent")
        info_frame.pack(fill="x", padx=6, pady=(0, 8))
        
        # Obtener información de la BD
        db_info = self.get_database_info()
        
        ctk.CTkLabel(
            info_frame,
            text=f"Base de datos: {db_info['name']}",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2)
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"Tamaño: {db_info['size']}",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2)
        ).pack(anchor="w")
        
        ctk.CTkLabel(
            info_frame,
            text=f"Último respaldo: {self.config.get('last_backup', 'Nunca')}",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2)
        ).pack(anchor="w")
        
        self.btn_manual_backup = ctk.CTkButton(
            manual_frame,
            text="🔄 Crear Respaldo Ahora",
            font=ctk.CTkFont(size=BUTTON_FONT_SIZE-4, weight="bold"),
            fg_color=SUCCESS_COLOR,
            hover_color="#2d8f2d",
            command=self.create_manual_backup,
            height=28,
            width=90
        )
        self.btn_manual_backup.pack(pady=(0, 6))

    def setup_configuration_section(self, parent):
        """Configura la sección de configuración"""
        config_frame = ctk.CTkFrame(parent, fg_color=CARD_COLOR)
        config_frame.pack(fill="x", pady=(0, 8), padx=1)
        
        ctk.CTkLabel(
            config_frame,
            text="⚙️ Configuración de Respaldos",
            font=ctk.CTkFont(size=SUBTITLE_FONT_SIZE-2, weight="bold")
        ).pack(pady=(10, 8))
        
        # Ruta de respaldos
        path_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        path_frame.pack(fill="x", padx=6, pady=4)
        
        ctk.CTkLabel(
            path_frame,
            text="📁 Ruta de respaldos:",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2, weight="bold")
        ).pack(anchor="w")
        
        path_input_frame = ctk.CTkFrame(path_frame, fg_color="transparent")
        path_input_frame.pack(fill="x", pady=4)
        
        self.entry_backup_path = ctk.CTkEntry(
            path_input_frame,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-4),
            height=24,
            width=120
        )
        self.entry_backup_path.pack(side="left", fill="x", expand=True)
        self.entry_backup_path.insert(0, self.config['backup_path'])
        
        btn_browse = ctk.CTkButton(
            path_input_frame,
            text="📂 Examinar",
            width=40,
            command=self.browse_backup_path,
            fg_color=BUTTON_COLOR,
            hover_color=SECONDARY_COLOR
        )
        btn_browse.pack(side="right", padx=(3, 0))
        
        # Respaldos automáticos
        auto_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        auto_frame.pack(fill="x", padx=6, pady=8)
        
        self.var_auto_backup = ctk.BooleanVar(value=self.config['auto_backup_enabled'])
        self.chk_auto_backup = ctk.CTkCheckBox(
            auto_frame,
            text="Habilitar respaldos automáticos",
            variable=self.var_auto_backup,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2, weight="bold"),
            command=self.toggle_auto_backup
        )
        self.chk_auto_backup.pack(anchor="w", pady=4)
        
        # Frecuencia
        freq_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        freq_frame.pack(fill="x", pady=4)
        
        ctk.CTkLabel(
            freq_frame,
            text="Frecuencia (horas):",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2)
        ).pack(side="left")
        
        self.entry_frequency = ctk.CTkEntry(
            freq_frame,
            width=40,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-4)
        )
        self.entry_frequency.pack(side="left", padx=(3, 0))
        self.entry_frequency.insert(0, str(self.config['backup_frequency_hours']))
        
        # Máximo de respaldos
        max_frame = ctk.CTkFrame(auto_frame, fg_color="transparent")
        max_frame.pack(fill="x", pady=4)
        
        ctk.CTkLabel(
            max_frame,
            text="Máximo de respaldos a mantener:",
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2)
        ).pack(side="left")
        
        self.entry_max_backups = ctk.CTkEntry(
            max_frame,
            width=40,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-4)
        )
        self.entry_max_backups.pack(side="left", padx=(3, 0))
        self.entry_max_backups.insert(0, str(self.config['max_backups']))
        
        # Botón guardar configuración
        btn_save_config = ctk.CTkButton(
            config_frame,
            text="💾 Guardar Configuración",
            command=self.save_configuration,
            fg_color=ACCENT_COLOR,
            hover_color=PRIMARY_COLOR,
            width=80
        )
        btn_save_config.pack(pady=6)

    def setup_history_section(self, parent):
        """Configura la sección de historial"""
        history_frame = ctk.CTkFrame(parent, fg_color=CARD_COLOR)
        history_frame.pack(fill="both", expand=True, pady=(0, 8), padx=1)
        
        ctk.CTkLabel(
            history_frame,
            text="📜 Historial de Respaldos",
            font=ctk.CTkFont(size=SUBTITLE_FONT_SIZE-2, weight="bold")
        ).pack(pady=(10, 8))
        
        # Frame para la lista de respaldos
        list_frame = ctk.CTkFrame(history_frame, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=6, pady=(0, 10))
        
        # Scrollable frame para la lista
        self.history_scroll = ctk.CTkScrollableFrame(
            list_frame,
            height=120,
            fg_color=BACKGROUND_COLOR
        )
        self.history_scroll.pack(fill="both", expand=True)

    def setup_action_buttons(self, parent):
        """Configura los botones de acción"""
        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", pady=3)
        
        # Botón para restaurar respaldo
        btn_restore = ctk.CTkButton(
            button_frame,
            text="🔄 Restaurar",
            command=self.restore_backup,
            fg_color=BUTTON_COLOR,
            hover_color=SECONDARY_COLOR,
            width=60
        )
        btn_restore.pack(side="left", padx=1)
        
        # Botón para limpiar respaldos antiguos
        btn_clean = ctk.CTkButton(
            button_frame,
            text="🗑️ Limpiar",
            command=self.clean_old_backups,
            fg_color=ERROR_COLOR,
            hover_color="#cc0000",
            width=60
        )
        btn_clean.pack(side="left", padx=1)
        
        # Botón cerrar
        btn_close = ctk.CTkButton(
            button_frame,
            text="❌ Cerrar",
            command=self.window.destroy,
            fg_color=SECONDARY_COLOR,
            hover_color=PRIMARY_COLOR,
            width=40
        )
        btn_close.pack(side="right", padx=1)

    def get_database_info(self):
        """Obtiene información de la base de datos"""
        try:
            db_path = self.db.db_name
            if os.path.exists(db_path):
                size = os.path.getsize(db_path)
                size_mb = size / (1024 * 1024)
                return {
                    'name': os.path.basename(db_path),
                    'size': f"{size_mb:.2f} MB",
                    'path': db_path
                }
            else:
                return {
                    'name': "No encontrada",
                    'size': "0 MB",
                    'path': ""
                }
        except Exception as e:
            print(f"Error obteniendo info de BD: {e}")
            return {
                'name': "Error",
                'size': "0 MB",
                'path': ""
            }

    def browse_backup_path(self):
        """Permite seleccionar la ruta de respaldos"""
        folder = filedialog.askdirectory(
            title="Seleccionar carpeta para respaldos",
            initialdir=self.config['backup_path']
        )
        if folder:
            self.entry_backup_path.delete(0, 'end')
            self.entry_backup_path.insert(0, folder)

    def toggle_auto_backup(self):
        """Activa/desactiva los respaldos automáticos"""
        enabled = self.var_auto_backup.get()
        # Aquí puedes agregar lógica para iniciar/detener el servicio de respaldo automático
        print(f"Respaldos automáticos: {'Habilitados' if enabled else 'Deshabilitados'}")

    def create_manual_backup(self):
        """Crea un respaldo manual"""
        if self.is_backup_running:
            messagebox.showwarning("Advertencia", "Ya hay un respaldo en proceso")
            return
            
        def backup_thread():
            try:
                self.is_backup_running = True
                self.btn_manual_backup.configure(text="⏳ Creando respaldo...", state="disabled")
                
                backup_path = self.entry_backup_path.get()
                if not backup_path:
                    raise ValueError("Debe especificar una ruta de respaldo")
                
                # Crear directorio si no existe
                os.makedirs(backup_path, exist_ok=True)
                
                # Nombre del archivo de respaldo
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_filename = f"respaldo_punto_venta_{timestamp}.db"
                backup_full_path = os.path.join(backup_path, backup_filename)
                
                # Crear el respaldo
                db_info = self.get_database_info()
                if os.path.exists(db_info['path']):
                    shutil.copy2(db_info['path'], backup_full_path)
                    
                    # Actualizar configuración
                    self.config['last_backup'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.save_config()
                    
                    # Actualizar UI en el hilo principal
                    self.window.after(0, lambda: self.backup_completed_successfully(backup_filename))
                else:
                    self.window.after(0, lambda: messagebox.showerror("Error", "No se encontró la base de datos"))
                    
            except Exception as e:
                self.window.after(0, lambda: messagebox.showerror("Error", f"Error creando respaldo: {e}"))
            finally:
                self.is_backup_running = False
                self.window.after(0, lambda: self.btn_manual_backup.configure(
                    text="🔄 Crear Respaldo Ahora", 
                    state="normal"
                ))
        
        # Ejecutar en hilo separado
        thread = threading.Thread(target=backup_thread)
        thread.daemon = True
        thread.start()

    def backup_completed_successfully(self, filename):
        """Callback cuando el respaldo se completa exitosamente"""
        messagebox.showinfo("Éxito", f"Respaldo creado exitosamente: {filename}")
        self.load_backup_history()

    # Drag and rounding helpers
    def _start_move(self, event):
        try:
            self._drag_x = event.x
            self._drag_y = event.y
        except Exception:
            self._drag_x = 0
            self._drag_y = 0

    def _on_move(self, event):
        try:
            x = self.window.winfo_x() + (event.x - getattr(self, '_drag_x', 0))
            y = self.window.winfo_y() + (event.y - getattr(self, '_drag_y', 0))
            self.window.geometry(f"+{x}+{y}")
            try:
                self.set_round_corners(14)
            except Exception:
                pass
        except Exception:
            pass

    def _stop_move(self, event):
        return

    def set_round_corners(self, radius=14):
        try:
            w = self.window.winfo_width()
            h = self.window.winfo_height()
            if w <= 1 or h <= 1:
                self.window.after(20, lambda: self.set_round_corners(radius))
                return
            hwnd = self.window.winfo_id()
            hrgn = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w, h, radius, radius)
            ctypes.windll.user32.SetWindowRgn(hwnd, hrgn, True)
        except Exception:
            pass

    def save_configuration(self):
        """Guarda la configuración actual"""
        try:
            self.config['backup_path'] = self.entry_backup_path.get()
            self.config['auto_backup_enabled'] = self.var_auto_backup.get()
            self.config['backup_frequency_hours'] = int(self.entry_frequency.get())
            self.config['max_backups'] = int(self.entry_max_backups.get())
            
            self.save_config()
            messagebox.showinfo("Éxito", "Configuración guardada correctamente")
            
        except ValueError as e:
            messagebox.showerror("Error", "Valores numéricos inválidos")
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando configuración: {e}")

    def load_backup_history(self):
        """Carga el historial de respaldos"""
        # Limpiar historial actual
        for widget in self.history_scroll.winfo_children():
            widget.destroy()
            
        try:
            backup_path = self.config['backup_path']
            if not os.path.exists(backup_path):
                ctk.CTkLabel(
                    self.history_scroll,
                    text="No se encontraron respaldos",
                    font=ctk.CTkFont(size=TEXT_FONT_SIZE),
                    text_color=SUBTEXT_COLOR
                ).pack(pady=20)
                return
                
            # Buscar archivos de respaldo
            backup_files = []
            for filename in os.listdir(backup_path):
                if filename.startswith("respaldo_punto_venta_") and filename.endswith(".db"):
                    filepath = os.path.join(backup_path, filename)
                    stat = os.stat(filepath)
                    backup_files.append({
                        'filename': filename,
                        'path': filepath,
                        'size': stat.st_size,
                        'date': datetime.fromtimestamp(stat.st_mtime)
                    })
            
            # Ordenar por fecha (más reciente primero)
            backup_files.sort(key=lambda x: x['date'], reverse=True)
            
            if not backup_files:
                ctk.CTkLabel(
                    self.history_scroll,
                    text="No se encontraron respaldos",
                    font=ctk.CTkFont(size=TEXT_FONT_SIZE),
                    text_color=SUBTEXT_COLOR
                ).pack(pady=20)
                return
            
            # Crear elementos de la lista
            for backup in backup_files:
                self.create_backup_item(backup)
                
        except Exception as e:
            print(f"Error cargando historial: {e}")
            ctk.CTkLabel(
                self.history_scroll,
                text="Error cargando historial de respaldos",
                font=ctk.CTkFont(size=TEXT_FONT_SIZE),
                text_color=ERROR_COLOR
            ).pack(pady=20)

    def create_backup_item(self, backup):
        """Crea un elemento del historial de respaldo"""
        item_frame = ctk.CTkFrame(self.history_scroll, fg_color=CARD_COLOR)
        item_frame.pack(fill="x", pady=2, padx=5)
        
        # Información del respaldo
        info_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True, padx=10, pady=8)
        
        # Nombre y fecha
        name_label = ctk.CTkLabel(
            info_frame,
            text=backup['filename'],
            font=ctk.CTkFont(size=TEXT_FONT_SIZE, weight="bold"),
            anchor="w"
        )
        name_label.pack(anchor="w")
        
        date_size_text = f"📅 {backup['date'].strftime('%Y-%m-%d %H:%M:%S')} | 💾 {backup['size'] / (1024*1024):.2f} MB"
        date_label = ctk.CTkLabel(
            info_frame,
            text=date_size_text,
            font=ctk.CTkFont(size=TEXT_FONT_SIZE-2),
            text_color=SUBTEXT_COLOR,
            anchor="w"
        )
        date_label.pack(anchor="w")
        
        # Botones de acción
        action_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
        action_frame.pack(side="right", padx=10, pady=8)
        
        btn_restore = ctk.CTkButton(
            action_frame,
            text="🔄",
            width=30,
            height=30,
            command=lambda: self.restore_specific_backup(backup['path']),
            fg_color=SUCCESS_COLOR,
            hover_color="#2d8f2d"
        )
        btn_restore.pack(side="right", padx=2)
        
        btn_delete = ctk.CTkButton(
            action_frame,
            text="🗑️",
            width=30,
            height=30,
            command=lambda: self.delete_backup(backup['path']),
            fg_color=ERROR_COLOR,
            hover_color="#cc0000"
        )
        btn_delete.pack(side="right", padx=2)

    def restore_specific_backup(self, backup_path):
        """Restaura un respaldo específico"""
        if messagebox.askyesno(
            "Confirmar Restauración",
            "¿Está seguro de que desea restaurar este respaldo?\n\n"
            "⚠️ ADVERTENCIA: Esta acción sobrescribirá la base de datos actual y no se puede deshacer."
        ):
            try:
                db_info = self.get_database_info()
                
                # Crear respaldo de seguridad antes de restaurar
                safety_backup = f"{db_info['path']}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                shutil.copy2(db_info['path'], safety_backup)
                
                # Restaurar el respaldo
                shutil.copy2(backup_path, db_info['path'])
                
                messagebox.showinfo(
                    "Éxito", 
                    f"Respaldo restaurado exitosamente.\n\n"
                    f"Se creó un respaldo de seguridad en:\n{safety_backup}\n\n"
                    f"Reinicie la aplicación para ver los cambios."
                )
                
            except Exception as e:
                messagebox.showerror("Error", f"Error restaurando respaldo: {e}")

    def delete_backup(self, backup_path):
        """Elimina un respaldo específico"""
        if messagebox.askyesno("Confirmar", "¿Está seguro de eliminar este respaldo?"):
            try:
                os.remove(backup_path)
                messagebox.showinfo("Éxito", "Respaldo eliminado")
                self.load_backup_history()
            except Exception as e:
                messagebox.showerror("Error", f"Error eliminando respaldo: {e}")

    def restore_backup(self):
        """Restaura un respaldo seleccionado desde un archivo"""
        backup_file = filedialog.askopenfilename(
            title="Seleccionar respaldo a restaurar",
            filetypes=[("Base de datos SQLite", "*.db"), ("Todos los archivos", "*.*")],
            initialdir=self.config['backup_path']
        )
        
        if backup_file:
            self.restore_specific_backup(backup_file)

    def clean_old_backups(self):
        """Limpia respaldos antiguos según la configuración"""
        try:
            backup_path = self.config['backup_path']
            max_backups = self.config['max_backups']
            
            if not os.path.exists(backup_path):
                messagebox.showinfo("Información", "No hay respaldos para limpiar")
                return
                
            # Obtener lista de respaldos
            backup_files = []
            for filename in os.listdir(backup_path):
                if filename.startswith("respaldo_punto_venta_") and filename.endswith(".db"):
                    filepath = os.path.join(backup_path, filename)
                    stat = os.stat(filepath)
                    backup_files.append({
                        'path': filepath,
                        'date': datetime.fromtimestamp(stat.st_mtime)
                    })
            
            # Ordenar por fecha y mantener solo los más recientes
            backup_files.sort(key=lambda x: x['date'], reverse=True)
            
            if len(backup_files) <= max_backups:
                messagebox.showinfo("Información", "No hay respaldos antiguos que limpiar")
                return
            
            # Eliminar respaldos antiguos
            deleted_count = 0
            for backup in backup_files[max_backups:]:
                os.remove(backup['path'])
                deleted_count += 1
            
            messagebox.showinfo("Éxito", f"Se eliminaron {deleted_count} respaldos antiguos")
            self.load_backup_history()
            
        except Exception as e:
            messagebox.showerror("Error", f"Error limpiando respaldos: {e}")