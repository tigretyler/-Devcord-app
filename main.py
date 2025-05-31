import socket
import threading
import json
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox, ttk, simpledialog
from datetime import datetime
import base64
import os
import time
import hashlib
import queue
from tkinter import font
import mimetypes
import platform
import webbrowser
import re

class DiscordClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Devcord Client")
        self.root.geometry("1000x700")
        self.root.configure(bg="#36393f")
        
        # Configuración de conexión
        self.SERVER_IP = '87.106.52.7'  # Usar localhost para pruebas
        self.SERVER_PORT = 6237
        
        # Variables de estado
        self.connected = False
        self.username = ""
        self.current_channel = ""
        self.channels = []
        self.users = {}
        self.pending_file_transfers = {}
        self.gui_queue = queue.Queue()
        self.last_message_time = 0
        self.typing_users = set()
        self.typing_indicator_id = None
        
        # Configurar interfaz
        self.setup_ui()
        
        # Manejar cierre de ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Verificar actualizaciones periódicamente
        self.root.after(100, self.process_gui_events)
        
        # Conectar al servidor
        self.connect_to_server()

    def setup_ui(self):
        # Fuentes personalizadas
        self.title_font = font.Font(family="Arial", size=16, weight="bold")
        self.channel_font = font.Font(family="Arial", size=12)
        self.message_font = font.Font(family="Arial", size=11)
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg="#36393f")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo (canales y usuarios)
        left_panel = tk.Frame(main_frame, bg="#2f3136", width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        # Botón para crear nuevo canal
        new_channel_btn = tk.Button(
            left_panel, 
            text="+ Crear Canal", 
            command=self.create_channel,
            bg="#7289da",
            fg="#ffffff",
            bd=0,
            highlightthickness=0,
            activebackground="#677bc4",
            font=self.channel_font
        )
        new_channel_btn.pack(fill=tk.X, padx=5, pady=5)
        
        # Lista de canales
        tk.Label(left_panel, text="CANALES", bg="#2f3136", fg="#8e9297", 
                font=self.title_font, anchor="w").pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.channel_listbox = tk.Listbox(
            left_panel,
            bg="#2f3136",
            fg="#ffffff",
            selectbackground="#3b3d44",
            selectforeground="#ffffff",
            bd=0,
            highlightthickness=0,
            font=self.channel_font,
            height=10
        )
        self.channel_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.channel_listbox.bind("<<ListboxSelect>>", self.switch_channel)
        
        # Lista de usuarios
        tk.Label(left_panel, text="USUARIOS CONECTADOS", bg="#2f3136", fg="#8e9297", 
                font=self.title_font, anchor="w").pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.user_listbox = tk.Listbox(
            left_panel,
            bg="#2f3136",
            fg="#ffffff",
            bd=0,
            highlightthickness=0,
            font=self.channel_font
        )
        self.user_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel principal (chat)
        right_panel = tk.Frame(main_frame, bg="#36393f")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Barra de canal actual
        channel_bar = tk.Frame(right_panel, bg="#36393f", height=40)
        channel_bar.pack(fill=tk.X, padx=10, pady=5)
        
        self.channel_label = tk.Label(
            channel_bar, 
            text="#general", 
            bg="#36393f", 
            fg="#ffffff",
            font=self.title_font,
            anchor="w"
        )
        self.channel_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Indicador de usuarios escribiendo
        self.typing_label = tk.Label(
            channel_bar,
            text="",
            bg="#36393f",
            fg="#b9bbbe",
            font=self.message_font,
            anchor="w"
        )
        self.typing_label.pack(side=tk.LEFT, fill=tk.X, padx=10)
        
        # Historial de chat
        chat_container = tk.Frame(right_panel, bg="#36393f")
        chat_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.chat_history = scrolledtext.ScrolledText(
            chat_container, 
            wrap=tk.WORD, 
            state='disabled', 
            bg="#36393f",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=self.message_font,
            padx=10,
            pady=10,
            bd=0,
            highlightthickness=0
        )
        self.chat_history.pack(fill=tk.BOTH, expand=True)
        
        # Configurar tags para diferentes tipos de mensajes
        self.chat_history.tag_config('system', foreground='#b9bbbe')
        self.chat_history.tag_config('user', foreground='#ffffff')
        self.chat_history.tag_config('self', foreground='#43b581')
        self.chat_history.tag_config('file', foreground='#7289da')
        self.chat_history.tag_config('error', foreground='#f04747')
        self.chat_history.tag_config('link', foreground='#00aaff', underline=1)
        
        # Enlace de hipervínculo
        self.chat_history.tag_bind("link", "<Button-1>", self.open_link)
        self.chat_history.tag_bind("link", "<Enter>", lambda e: self.chat_history.config(cursor="hand2"))
        self.chat_history.tag_bind("link", "<Leave>", lambda e: self.chat_history.config(cursor=""))
        
        # Entrada de mensaje
        input_frame = tk.Frame(right_panel, bg="#40444b", height=50)
        input_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.message_entry = tk.Entry(
            input_frame, 
            bg="#40444b",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=self.message_font,
            bd=0,
            highlightthickness=0,
            relief=tk.FLAT
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.message_entry.bind("<Return>", self.send_message)
        self.message_entry.bind("<Key>", self.typing_indicator)
        
        # Botones
        button_frame = tk.Frame(input_frame, bg="#40444b")
        button_frame.pack(side=tk.RIGHT, padx=5)
        
        self.file_button = tk.Button(
            button_frame, 
            text="📎", 
            command=self.send_file,
            bg="#40444b",
            fg="#ffffff",
            bd=0,
            highlightthickness=0,
            activebackground="#4f535c",
            font=self.title_font
        )
        self.file_button.pack(side=tk.LEFT, padx=2)
        
        self.send_button = tk.Button(
            button_frame, 
            text="➤", 
            command=lambda: self.send_message(),
            bg="#40444b",
            fg="#ffffff",
            bd=0,
            highlightthickness=0,
            activebackground="#4f535c",
            font=self.title_font
        )
        self.send_button.pack(side=tk.LEFT, padx=2)
        
        # Panel de registro
        self.register_frame = tk.Frame(self.root, bg="#36393f")
        self.register_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            self.register_frame, 
            text="Discord-Like Chat", 
            bg="#36393f", 
            fg="#ffffff",
            font=self.title_font
        ).pack(pady=10)
        
        tk.Label(
            self.register_frame, 
            text="Ingresa tu nombre de usuario", 
            bg="#36393f", 
            fg="#b9bbbe"
        ).pack(pady=5)
        
        self.username_entry = tk.Entry(
            self.register_frame, 
            bg="#40444b",
            fg="#ffffff",
            insertbackground="#ffffff",
            font=self.message_font,
            width=30
        )
        self.username_entry.pack(pady=10, padx=20)
        self.username_entry.focus()
        self.username_entry.bind("<Return>", self.register_user)
        
        self.register_button = tk.Button(
            self.register_frame, 
            text="Entrar", 
            command=self.register_user,
            bg="#7289da",
            fg="#ffffff",
            bd=0,
            highlightthickness=0,
            activebackground="#677bc4",
            font=self.message_font,
            width=10
        )
        self.register_button.pack(pady=10)
        
        self.status_label = tk.Label(
            self.register_frame, 
            text="", 
            bg="#36393f", 
            fg="#f04747"
        )
        self.status_label.pack(pady=5)
        
        # Barra de estado
        self.status_bar = tk.Label(
            self.root, 
            text="Desconectado", 
            bg="#2f3136", 
            fg="#b9bbbe",
            anchor="w",
            padx=10
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def connect_to_server(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((self.SERVER_IP, self.SERVER_PORT))
            self.client_socket.settimeout(0.5)
            
            self.connected = True
            self.status_bar.config(text=f"Conectado a {self.SERVER_IP}:{self.SERVER_PORT}", fg="#43b581")
            self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            self.receive_thread.start()
            
        except socket.timeout:
            self.gui_queue.put(('error', "Tiempo de espera agotado. Servidor no disponible."))
        except ConnectionRefusedError:
            self.gui_queue.put(('error', "Servidor no disponible o rechazó la conexión."))
        except Exception as e:
            self.gui_queue.put(('error', f"Error de conexión: {str(e)}"))

    def receive_messages(self):
        while self.connected:
            try:
                message = self.client_socket.recv(65536)
                if not message:
                    break
                    
                try:
                    msg_data = json.loads(message.decode('utf-8'))
                    self.gui_queue.put(('process', msg_data))
                except json.JSONDecodeError:
                    try:
                        while True:
                            more_data = self.client_socket.recv(65536)
                            if not more_data:
                                break
                            message += more_data
                        msg_data = json.loads(message.decode('utf-8'))
                        self.gui_queue.put(('process', msg_data))
                    except:
                        self.gui_queue.put(('warning', "Mensaje no válido recibido"))
                except Exception as e:
                    self.gui_queue.put(('error', f"Error procesando mensaje: {str(e)}"))
                    
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                self.gui_queue.put(('disconnect', "Se perdió la conexión con el servidor"))
                break
            except Exception as e:
                if self.connected:
                    self.gui_queue.put(('error', f"Error de recepción: {str(e)}"))
                break
                
        if self.connected:
            self.gui_queue.put(('disconnect', "Se perdió la conexión con el servidor"))

    def process_gui_events(self):
        try:
            while True:
                event_type, data = self.gui_queue.get_nowait()
                
                if event_type == 'process':
                    self.process_message(data)
                elif event_type == 'error':
                    self.display_error(data)
                elif event_type == 'warning':
                    self.display_warning(data)
                elif event_type == 'disconnect':
                    self.disconnect(data)
                    
        except queue.Empty:
            pass
        
        # Actualizar indicador de escritura
        self.update_typing_indicator()
        
        self.root.after(100, self.process_gui_events)

    def process_message(self, msg_data):
        msg_type = msg_data.get('type')
        
        if msg_type == 'server_info':
            self.handle_server_info(msg_data)
        elif msg_type == 'channel_info':
            self.handle_channel_info(msg_data)
        elif msg_type == 'message':
            self.display_message(msg_data)
        elif msg_type == 'file':
            self.display_file(msg_data)
        elif msg_type == 'user_joined':
            self.user_joined(msg_data)
        elif msg_type == 'user_left':
            self.user_left(msg_data)
        elif msg_type == 'user_disconnected':
            self.user_disconnected(msg_data)
        elif msg_type == 'file_transfer':
            self.handle_file_transfer(msg_data)
        elif msg_type == 'ping':
            self.handle_ping()
        elif msg_type == 'server_shutdown':
            self.disconnect("El servidor se está apagando")
        elif msg_type == 'error':
            self.display_error(msg_data.get('message', 'Error desconocido'))
        elif msg_type == 'typing_indicator':
            self.handle_typing_indicator(msg_data)
        elif msg_type == 'channel_created':
            self.handle_channel_created(msg_data)
        else:
            self.display_warning(f"Mensaje de tipo desconocido: {msg_type}")

    def handle_server_info(self, msg_data):
        self.channels = msg_data.get('channels', [])
        self.current_channel = msg_data.get('current_channel', '')
        
        # Actualizar lista de canales
        self.channel_listbox.delete(0, tk.END)
        for channel in self.channels:
            self.channel_listbox.insert(tk.END, f"# {channel}")
        
        # Seleccionar canal actual
        if self.current_channel:
            self.channel_label.config(text=f"#{self.current_channel}")
            
            # Buscar índice del canal actual
            for i, channel in enumerate(self.channels):
                if channel == self.current_channel:
                    self.channel_listbox.selection_set(i)
                    self.channel_listbox.see(i)
                    break
        
        # Mostrar historial
        history = msg_data.get('channel_history', [])
        for msg in history:
            if msg['type'] == 'message':
                self.display_message(msg)
            elif msg['type'] == 'file':
                self.display_file(msg)
        
        # Ocultar panel de registro
        self.register_frame.place_forget()

    def handle_channel_info(self, msg_data):
        channel = msg_data.get('channel', '')
        if channel != self.current_channel:
            return
            
        # Actualizar lista de usuarios
        users = msg_data.get('users', [])
        self.user_listbox.delete(0, tk.END)
        for user in users:
            self.user_listbox.insert(tk.END, user)
        
        # Limpiar historial y mostrar mensajes del canal
        self.chat_history.config(state='normal')
        self.chat_history.delete(1.0, tk.END)
        
        history = msg_data.get('history', [])
        for msg in history:
            if msg['type'] == 'message':
                self.display_message(msg, history=True)
            elif msg['type'] == 'file':
                self.display_file(msg, history=True)
        
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)

    def display_message(self, msg_data, history=False):
        user = msg_data.get('user', 'Unknown')
        message = msg_data.get('message', '')
        channel = msg_data.get('channel', '')
        timestamp = datetime.fromisoformat(msg_data['timestamp']).strftime("%H:%M")
        
        if channel != self.current_channel:
            return
            
        self.chat_history.config(state='normal')
        
        if user == self.username:
            self.chat_history.insert(tk.END, f"[{timestamp}] Tú: ", 'self')
        else:
            self.chat_history.insert(tk.END, f"[{timestamp}] {user}: ", 'user')
        
        # Detectar y formatear enlaces
        formatted_message = self.format_message_links(message)
        self.chat_history.insert(tk.END, formatted_message + "\n")
        
        self.chat_history.config(state='disabled')
        if not history:
            self.chat_history.see(tk.END)

    def format_message_links(self, message):
        # Detectar URLs
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        urls = re.findall(url_pattern, message)
        
        if not urls:
            return message
        
        # Reemplazar URLs con etiquetas de hipervínculo
        for url in urls:
            display_url = url if len(url) < 50 else url[:47] + "..."
            message = message.replace(url, f"[{display_url}]")
            start_idx = message.index(f"[{display_url}]")
            end_idx = start_idx + len(display_url) + 2
            self.chat_history.insert(tk.END, message[:start_idx])
            self.chat_history.insert(tk.END, display_url, 'link')
            message = message[end_idx:]
        
        return message

    def display_file(self, msg_data, history=False):
        user = msg_data.get('user', 'Unknown')
        file_name = msg_data.get('file_name', 'file')
        file_id = msg_data.get('file_id', '')
        file_size = msg_data.get('size', 0)
        channel = msg_data.get('channel', '')
        timestamp = datetime.fromisoformat(msg_data['timestamp']).strftime("%H:%M")
        
        if channel != self.current_channel:
            return
            
        self.chat_history.config(state='normal')
        
        if user == self.username:
            prefix = f"[{timestamp}] Tú enviaste un archivo: "
        else:
            prefix = f"[{timestamp}] {user} envió un archivo: "
        
        self.chat_history.insert(tk.END, prefix, 'self' if user == self.username else 'user')
        
        # Obtener icono según tipo de archivo
        file_icon = self.get_file_icon(file_name)
        
        file_button = tk.Button(
            self.chat_history, 
            text=f"{file_icon} {file_name} ({self.format_size(file_size)})", 
            command=lambda fid=file_id, fname=file_name: self.download_file(fid, fname),
            relief=tk.FLAT,
            fg="#7289da",
            cursor="hand2",
            bg="#36393f",
            activebackground="#40444b",
            font=self.message_font,
            bd=0,
            highlightthickness=0,
            compound=tk.LEFT
        )
        self.chat_history.window_create(tk.END, window=file_button)
        self.chat_history.insert(tk.END, "\n")
        
        self.chat_history.config(state='disabled')
        if not history:
            self.chat_history.see(tk.END)

    def get_file_icon(self, filename):
        """Devuelve un emoji según el tipo de archivo"""
        ext = os.path.splitext(filename)[1].lower()
        
        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return "🖼️"
        elif ext in ['.mp3', '.wav', '.ogg', '.flac']:
            return "🎵"
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            return "🎬"
        elif ext in ['.pdf']:
            return "📄"
        elif ext in ['.doc', '.docx']:
            return "📝"
        elif ext in ['.xls', '.xlsx']:
            return "📊"
        elif ext in ['.zip', '.rar', '.7z']:
            return "📦"
        else:
            return "📁"

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} GB"

    def download_file(self, file_id, file_name):
        transfer_id = hashlib.md5(f"{file_id}{time.time()}".encode()).hexdigest()[:8]
        self.pending_file_transfers[transfer_id] = file_name
        
        save_path = filedialog.asksaveasfilename(
            initialfile=file_name,
            title="Guardar archivo",
            filetypes=[("Todos los archivos", "*.*")]
        )
        
        if save_path:
            try:
                request = {
                    'type': 'file_request',
                    'file_id': file_id,
                    'transfer_id': transfer_id
                }
                self.client_socket.send(json.dumps(request).encode('utf-8'))
            except:
                self.display_error("Error al solicitar el archivo")
                if transfer_id in self.pending_file_transfers:
                    del self.pending_file_transfers[transfer_id]

    def handle_file_transfer(self, file_data):
        file_id = file_data.get('file_id')
        file_name = file_data.get('file_name')
        content = file_data.get('content')
        transfer_id = file_data.get('transfer_id')
        
        if transfer_id in self.pending_file_transfers:
            suggested_name = self.pending_file_transfers[transfer_id]
            del self.pending_file_transfers[transfer_id]
        else:
            suggested_name = file_name
        
        if not content:
            self.display_error("Archivo vacío recibido")
            return
            
        try:
            file_bytes = base64.b64decode(content.encode('latin1'))
            
            save_path = filedialog.asksaveasfilename(
                initialfile=suggested_name,
                title="Guardar archivo",
                filetypes=[("Todos los archivos", "*.*")]
            )
            
            if save_path:
                with open(save_path, 'wb') as f:
                    f.write(file_bytes)
                
                self.display_system_message(f"Archivo {suggested_name} guardado correctamente")
        except Exception as e:
            self.display_error(f"Error al guardar archivo: {str(e)}")

    def user_joined(self, msg_data):
        user = msg_data.get('user', 'Usuario')
        channel = msg_data.get('channel', '')
        timestamp = datetime.fromisoformat(msg_data['timestamp']).strftime("%H:%M")
        
        if channel == self.current_channel:
            self.chat_history.config(state='normal')
            self.chat_history.insert(tk.END, f"[{timestamp}] {user} se ha unido al chat\n", 'system')
            self.chat_history.config(state='disabled')
            self.chat_history.see(tk.END)

    def user_left(self, msg_data):
        user = msg_data.get('user', 'Usuario')
        channel = msg_data.get('channel', '')
        timestamp = datetime.fromisoformat(msg_data['timestamp']).strftime("%H:%M")
        
        if channel == self.current_channel:
            self.chat_history.config(state='normal')
            self.chat_history.insert(tk.END, f"[{timestamp}] {user} ha abandonado el chat\n", 'system')
            self.chat_history.config(state='disabled')
            self.chat_history.see(tk.END)

    def user_disconnected(self, msg_data):
        user = msg_data.get('user', 'Usuario')
        channel = msg_data.get('channel', '')
        timestamp = datetime.fromisoformat(msg_data['timestamp']).strftime("%H:%M")
        
        if channel == self.current_channel:
            self.chat_history.config(state='normal')
            self.chat_history.insert(tk.END, f"[{timestamp}] {user} se ha desconectado\n", 'system')
            self.chat_history.config(state='disabled')
            self.chat_history.see(tk.END)

    def switch_channel(self, event):
        if not self.connected:
            return
            
        selection = self.channel_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        new_channel = self.channels[index]
        
        if new_channel == self.current_channel:
            return
            
        # Enviar solicitud para cambiar de canal
        join_msg = {
            'type': 'join_channel',
            'channel': new_channel
        }
        
        try:
            self.client_socket.send(json.dumps(join_msg).encode('utf-8'))
        except:
            self.disconnect("Error al cambiar de canal")

    def register_user(self, event=None):
        username = self.username_entry.get().strip()
        if not username:
            self.status_label.config(text="Debes ingresar un nombre de usuario")
            return
            
        # Enviar registro al servidor
        register_msg = {
            'type': 'register',
            'username': username
        }
        
        try:
            self.client_socket.send(json.dumps(register_msg).encode('utf-8'))
            self.username = username
        except:
            self.status_label.config(text="Error al registrar usuario")

    def send_message(self, event=None):
        if not self.connected or not self.current_channel:
            return
            
        message = self.message_entry.get().strip()
        if not message:
            return
            
        msg_data = {
            'type': 'message',
            'message': message,
            'channel': self.current_channel,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            self.client_socket.send(json.dumps(msg_data).encode('utf-8'))
            self.message_entry.delete(0, tk.END)
            self.last_message_time = time.time()
        except:
            self.disconnect("Error al enviar mensaje")

    def send_file(self):
        if not self.connected or not self.current_channel:
            return
            
        file_path = filedialog.askopenfilename(
            title="Seleccionar archivo para enviar",
            filetypes=[("Todos los archivos", "*.*")]
        )
        if not file_path:
            return
            
        try:
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB límite
                messagebox.showwarning("Archivo grande", "El archivo es demasiado grande (máximo 10MB)")
                return
                
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            encoded_content = base64.b64encode(file_content).decode('latin1')
            file_name = os.path.basename(file_path)
            
            file_data = {
                'type': 'file',
                'file_name': file_name,
                'content': encoded_content,
                'channel': self.current_channel,
                'timestamp': datetime.now().isoformat()
            }
            
            self.client_socket.send(json.dumps(file_data).encode('utf-8'))
        except Exception as e:
            self.display_error(f"No se pudo enviar el archivo: {str(e)}")

    def handle_ping(self):
        try:
            self.client_socket.send(json.dumps({'type': 'pong'}).encode('utf-8'))
        except:
            self.disconnect("Error al responder ping")

    def display_error(self, message):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, f"ERROR: {message}\n", 'error')
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)

    def display_warning(self, message):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, f"ADVERTENCIA: {message}\n", 'warning')
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)
        
    def display_system_message(self, message):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, f"SYSTEM: {message}\n", 'system')
        self.chat_history.config(state='disabled')
        self.chat_history.see(tk.END)

    def disconnect(self, message="Desconectado"):
        if self.connected:
            self.connected = False
            try:
                self.client_socket.close()
            except:
                pass
            
            # Mostrar mensaje de desconexión
            self.register_frame.place(relx=0.5, rely=0.5, anchor="center")
            self.status_label.config(text=message, fg="#f04747")
            self.status_bar.config(text=message, fg="#f04747")
            
            # Limpiar datos
            self.channels = []
            self.current_channel = ""
            self.users = {}
            self.channel_listbox.delete(0, tk.END)
            self.user_listbox.delete(0, tk.END)
            self.chat_history.config(state='normal')
            self.chat_history.delete(1.0, tk.END)
            self.chat_history.config(state='disabled')
            self.channel_label.config(text="#general")
            self.typing_label.config(text="")

    def on_closing(self):
        if self.connected:
            self.disconnect("Conexión cerrada por el usuario")
        self.root.destroy()
        
    def create_channel(self):
        if not self.connected:
            return
            
        channel_name = simpledialog.askstring("Crear Canal", "Nombre del nuevo canal:")
        if not channel_name:
            return
            
        create_msg = {
            'type': 'create_channel',
            'channel': channel_name
        }
        
        try:
            self.client_socket.send(json.dumps(create_msg).encode('utf-8'))
        except:
            self.display_error("Error al crear canal")

    def handle_channel_created(self, msg_data):
        channel = msg_data.get('channel', '')
        if channel:
            self.channels.append(channel)
            self.channel_listbox.insert(tk.END, f"# {channel}")
            self.display_system_message(f"Nuevo canal creado: #{channel}")

    def typing_indicator(self, event):
        if not self.connected or not self.username or not self.current_channel:
            return
            
        # Enviar indicador de escritura solo si han pasado más de 3 segundos desde el último mensaje
        current_time = time.time()
        if current_time - self.last_message_time > 3:
            typing_msg = {
                'type': 'typing_indicator',
                'user': self.username,
                'channel': self.current_channel
            }
            
            try:
                self.client_socket.send(json.dumps(typing_msg).encode('utf-8'))
                self.last_message_time = current_time
            except:
                pass

    def handle_typing_indicator(self, msg_data):
        user = msg_data.get('user', '')
        channel = msg_data.get('channel', '')
        
        if channel != self.current_channel or user == self.username:
            return
            
        # Agregar usuario a la lista de escribiendo
        self.typing_users.add(user)
        
        # Programar limpieza después de 5 segundos
        if self.typing_indicator_id:
            self.root.after_cancel(self.typing_indicator_id)
        self.typing_indicator_id = self.root.after(5000, self.clear_typing_indicator)

    def update_typing_indicator(self):
        if not self.typing_users:
            self.typing_label.config(text="")
            return
            
        users = list(self.typing_users)
        if len(users) == 1:
            text = f"{users[0]} está escribiendo..."
        elif len(users) == 2:
            text = f"{users[0]} y {users[1]} están escribiendo..."
        else:
            text = f"{users[0]}, {users[1]} y otros están escribiendo..."
            
        self.typing_label.config(text=text)

    def clear_typing_indicator(self):
        self.typing_users.clear()
        self.typing_label.config(text="")
        self.typing_indicator_id = None

    def open_link(self, event):
        # Encuentra la posición del clic
        index = self.chat_history.index(f"@{event.x},{event.y}")
        
        # Busca todos los enlaces en el área
        for tag in self.chat_history.tag_names(index):
            if tag.startswith("link_"):
                url = tag[5:]
                webbrowser.open(url)
                break

if __name__ == "__main__":
    root = tk.Tk()
    client = DiscordClient(root)
    root.mainloop()