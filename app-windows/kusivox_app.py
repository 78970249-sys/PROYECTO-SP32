"""
KusiVox para Windows: conecta tu asistente de voz KusiVox con esta computadora.

La ventana guarda tu MCP endpoint (cifrado con la cuenta de Windows), se conecta a
xiaozhi.me y arranca el servidor de herramientas (KusiVoxServidor.exe). Una vez conectada
no se queda desconectada: si la conexion se corta vuelve a conectarse sola, al cerrar la
ventana sigue funcionando minimizada, puede iniciar con Windows y evita que la PC se suspenda.

Modos:
  KusiVox.exe               abre la ventana
  KusiVox.exe --minimizado  abre la ventana minimizada (inicio con Windows)
  KusiVox.exe --autoprueba  prueba interna para la compilacion (cifrado y ventana)
"""

import asyncio
import base64
import json
import os
import queue
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

APP = "KusiVox"
VERSION = "1.3.0"
URL_CONSOLA = "https://xiaozhi.me"
CARPETA_DATOS = Path(os.environ.get("APPDATA") or Path.home()) / APP
ARCHIVO_CONFIG = CARPETA_DATOS / "config.json"
ESPERA_MAXIMA = 15  # segundos entre reintentos, como maximo
CREATE_NO_WINDOW = 0x08000000
LINEAS_MAXIMAS = 400


# ---------------------------------------------------------------- cifrado (DPAPI)
def _dpapi(texto: bytes, cifrar: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(texto, len(texto))
    entrada = BLOB(len(texto), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    salida = BLOB()
    crypt32 = ctypes.windll.crypt32
    if cifrar:
        ok = crypt32.CryptProtectData(ctypes.byref(entrada), "KusiVox", None, None, None, 0, ctypes.byref(salida))
    else:
        ok = crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, 0, ctypes.byref(salida))
    if not ok:
        raise OSError("DPAPI no pudo procesar el dato")
    try:
        return ctypes.string_at(salida.pbData, salida.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(ctypes.cast(salida.pbData, ctypes.c_void_p))


def proteger(texto: str) -> str:
    if sys.platform == "win32":
        return "dpapi:" + base64.b64encode(_dpapi(texto.encode("utf-8"), True)).decode("ascii")
    return "plano:" + texto


def desproteger(valor: str) -> str:
    if valor.startswith("dpapi:"):
        return _dpapi(base64.b64decode(valor[6:]), False).decode("utf-8")
    if valor.startswith("plano:"):
        return valor[6:]
    return ""


# ---------------------------------------------------------------- configuracion
def leer_config() -> dict:
    try:
        datos = json.loads(ARCHIVO_CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    try:
        datos["endpoint"] = desproteger(datos.get("endpoint", ""))
    except OSError:
        datos["endpoint"] = ""
    datos.setdefault("autoconectar", True)
    datos.setdefault("despierta", True)
    return datos


def guardar_config(endpoint: str, autoconectar: bool, despierta: bool = True) -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    datos = {"endpoint": proteger(endpoint) if endpoint else "", "autoconectar": bool(autoconectar),
             "despierta": bool(despierta)}
    ARCHIVO_CONFIG.write_text(json.dumps(datos, indent=1), encoding="utf-8")


def validar_endpoint(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if not url:
        return "Pega tu MCP endpoint (empieza con wss://)."
    if not url.startswith(("wss://", "ws://")):
        return "El MCP endpoint debe empezar con wss://"
    if "token=" not in url:
        return "Al MCP endpoint le falta el token (…?token=…)."
    return ""


# ---------------------------------------------------------------- inicio con Windows
CLAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def inicio_con_windows() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_RUN) as clave:
            winreg.QueryValueEx(clave, APP)
            return True
    except OSError:
        return False


def fijar_inicio_con_windows(activo: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLAVE_RUN, 0, winreg.KEY_SET_VALUE) as clave:
        if activo:
            if getattr(sys, "frozen", False):
                comando = f'"{sys.executable}" --minimizado'
            else:
                comando = f'"{sys.executable}" "{Path(__file__).resolve()}" --minimizado'
            winreg.SetValueEx(clave, APP, 0, winreg.REG_SZ, comando)
        else:
            try:
                winreg.DeleteValue(clave, APP)
            except OSError:
                pass


# ---------------------------------------------------------------- puente WebSocket <-> MCP
def comando_servidor() -> list:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).with_name("KusiVoxServidor.exe"))]
    return [sys.executable, str(Path(__file__).resolve().with_name("kusivox_servidor.py"))]


class Puente(threading.Thread):
    """Mantiene la conexion con el MCP endpoint en un hilo aparte y avisa a la ventana por una cola."""

    def __init__(self, url: str, eventos: "queue.Queue"):
        super().__init__(daemon=True)
        self.url = url
        self.eventos = eventos
        self.loop = None
        self.tarea = None

    def avisar(self, tipo: str, texto: str) -> None:
        self.eventos.put((tipo, texto))

    def run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.tarea = self.loop.create_task(self.principal())
        try:
            self.loop.run_until_complete(self.tarea)
        except asyncio.CancelledError:
            pass
        except Exception as error:  # no deberia pasar: principal() atrapa todo
            self.avisar("log", f"Error inesperado: {error}")
        finally:
            self.avisar("estado", "desconectado")
            self.loop.close()

    def detener(self) -> None:
        if self.loop and self.tarea and not self.tarea.done():
            self.loop.call_soon_threadsafe(self.tarea.cancel)

    async def principal(self) -> None:
        espera = 1
        while True:
            inicio = time.monotonic()
            self.avisar("estado", "conectando")
            try:
                await self.sesion()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self.avisar("log", f"Conexión cortada: {error}")
            if time.monotonic() - inicio > 60:
                espera = 1
            self.avisar("estado", "reintentando")
            self.avisar("log", f"Reintentando en {espera} s…")
            await asyncio.sleep(espera)
            espera = min(espera * 2, ESPERA_MAXIMA)

    async def sesion(self) -> None:
        import websockets
        async with websockets.connect(self.url, ping_interval=15, ping_timeout=15, open_timeout=15, max_size=None) as ws:
            self.avisar("estado", "conectado")
            self.avisar("log", f"Conectado a {urlsplit(self.url).netloc}")
            opciones = {"creationflags": CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            proceso = await asyncio.create_subprocess_exec(
                *comando_servidor(),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                limit=16 * 1024 * 1024, **opciones)

            async def del_agente_al_servidor():
                async for mensaje in ws:
                    if isinstance(mensaje, bytes):
                        mensaje = mensaje.decode("utf-8")
                    proceso.stdin.write((mensaje.rstrip("\r\n") + "\n").encode("utf-8"))
                    await proceso.stdin.drain()
                raise ConnectionError("xiaozhi.me cerró la conexión")

            async def del_servidor_al_agente():
                while True:
                    linea = await proceso.stdout.readline()
                    if not linea:
                        raise RuntimeError("el servidor de herramientas se detuvo")
                    await ws.send(linea.decode("utf-8").rstrip("\r\n"))

            async def mensajes_del_servidor():
                while True:
                    linea = await proceso.stderr.readline()
                    if not linea:
                        return
                    texto = linea.decode("utf-8", errors="replace").strip()
                    if texto:
                        self.avisar("log", texto)

            tareas = [asyncio.create_task(t()) for t in (del_agente_al_servidor, del_servidor_al_agente, mensajes_del_servidor)]
            try:
                hechas, _ = await asyncio.wait(tareas[:2], return_when=asyncio.FIRST_COMPLETED)
                for tarea in hechas:
                    tarea.result()
            finally:
                for tarea in tareas:
                    tarea.cancel()
                if proceso.returncode is None:
                    proceso.kill()
                    await proceso.wait()


# ---------------------------------------------------------------- mantener la PC despierta
def mantener_despierta(activo: bool) -> None:
    """Mientras KusiVox esta conectado, evita que Windows suspenda la PC (la pantalla si puede apagarse)."""
    if sys.platform != "win32":
        return
    import ctypes
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if activo else 0))


def recurso(nombre: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / nombre


# ---------------------------------------------------------------- ventana
COLORES = {"fondo": "#0B1220", "panel": "#141F33", "panel2": "#1B2942", "borde": "#26385A", "texto": "#FFFFFF",
           "suave": "#AEB8C8", "acento": "#1A93CF", "acento2": "#157AAD", "rosa": "#FF6E9C", "verde": "#2FB57A",
           "ambar": "#E0A030", "gris": "#7A8699", "chip": "#20314F"}
ESTADOS = {
    "desconectado": ("Desconectado", "Pega tu MCP endpoint y pulsa «Conectar».", COLORES["gris"], "dormido"),
    "conectando": ("Conectando…", "Un momento, estoy entrando a xiaozhi.me.", COLORES["ambar"], "pensando"),
    "reintentando": ("Reconectando…", "Se cortó la conexión; vuelvo a intentarlo solo.", COLORES["ambar"], "pensando"),
    "conectado": ("Conectado", "Di «KusiVox» y pide lo que necesites.", COLORES["verde"], "feliz"),
}
EJEMPLOS = ("«Abre Word y escribe hola»", "«Pon música de Grupo 5»", "«Más fuerte»", "«Haz clic en Guardar»",
            "«¿Qué hay en la pantalla?»", "«Abre YouTube en Brave»")


class Ventana:
    def __init__(self, minimizado: bool = False):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.eventos = queue.Queue()
        self.puente = None
        self.config = leer_config()
        self.usuario_desconecto = False
        self.estado = "desconectado"
        self.mascotas, self.cuadro, self.animacion = {}, 0, "dormido"
        if sys.platform == "win32":
            try:  # letras nitidas en pantallas con escala de Windows
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

        self.raiz = raiz = tk.Tk()
        raiz.title(f"{APP} {VERSION}")
        escala = max(1.0, raiz.winfo_fpixels("1i") / 96.0)
        raiz.geometry(f"{int(600 * escala)}x{int(780 * escala)}")
        raiz.minsize(int(520 * escala), int(640 * escala))
        raiz.configure(bg=COLORES["fondo"])
        self._icono()

        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        for nombre, fondo in (("TCheckbutton", COLORES["panel"]), ("Fondo.TCheckbutton", COLORES["fondo"])):
            estilo.configure(nombre, background=fondo, foreground=COLORES["texto"], font=("Segoe UI", 10))
            estilo.map(nombre, background=[("active", fondo)])
        estilo.configure("Acento.TButton", background=COLORES["acento"], foreground="#FFFFFF", borderwidth=0,
                         padding=(16, 9), font=("Segoe UI", 10, "bold"))
        estilo.map("Acento.TButton", background=[("active", COLORES["acento2"]), ("disabled", COLORES["chip"])])
        estilo.configure("Suave.TButton", background=COLORES["panel2"], foreground=COLORES["texto"], borderwidth=0,
                         padding=(14, 9), font=("Segoe UI", 10))
        estilo.map("Suave.TButton", background=[("active", COLORES["borde"])], foreground=[("disabled", COLORES["gris"])])

        # --- cabecera: KusiVox animado + nombre
        cab = tk.Frame(raiz, bg=COLORES["fondo"])
        cab.pack(fill="x", padx=22, pady=(20, 10))
        pantalla = tk.Frame(cab, bg="#000000", highlightbackground=COLORES["acento"], highlightthickness=2)
        pantalla.pack(side="left")
        self.lienzo = tk.Label(pantalla, bg="#000000", width=120, height=120)
        self.lienzo.pack(padx=4, pady=4)
        titulos = tk.Frame(cab, bg=COLORES["fondo"])
        titulos.pack(side="left", padx=16, fill="y")
        tk.Label(titulos, text=APP, font=("Segoe UI", 28, "bold"), fg=COLORES["texto"], bg=COLORES["fondo"]).pack(anchor="w")
        tk.Label(titulos, text="Asistente de escritorio por voz", font=("Segoe UI", 12), fg=COLORES["suave"],
                 bg=COLORES["fondo"]).pack(anchor="w")
        tk.Label(titulos, text=f"Versión {VERSION} · para personas con discapacidad y adultos mayores",
                 font=("Segoe UI", 9), fg=COLORES["gris"], bg=COLORES["fondo"]).pack(anchor="w", pady=(4, 0))

        # --- estado
        tarjeta = tk.Frame(raiz, bg=COLORES["panel"], highlightbackground=COLORES["borde"], highlightthickness=1)
        tarjeta.pack(fill="x", padx=22, pady=6)
        fila = tk.Frame(tarjeta, bg=COLORES["panel"])
        fila.pack(fill="x", padx=16, pady=(14, 2))
        self.punto = tk.Canvas(fila, width=18, height=18, bg=COLORES["panel"], highlightthickness=0)
        self.punto.pack(side="left", padx=(0, 10))
        self.circulo = self.punto.create_oval(2, 2, 16, 16, fill=COLORES["gris"], outline="")
        self.texto_estado = tk.Label(fila, text="Desconectado", font=("Segoe UI", 16, "bold"), fg=COLORES["texto"],
                                     bg=COLORES["panel"])
        self.texto_estado.pack(side="left")
        self.texto_ayuda = tk.Label(tarjeta, text="", font=("Segoe UI", 11), fg=COLORES["suave"], bg=COLORES["panel"])
        self.texto_ayuda.pack(anchor="w", padx=44, pady=(0, 14))

        # --- MCP endpoint (se oculta cuando ya esta conectado)
        self.marco_endpoint = tk.Frame(raiz, bg=COLORES["panel"], highlightbackground=COLORES["borde"], highlightthickness=1)
        tk.Label(self.marco_endpoint, text="MCP endpoint de tu agente  (xiaozhi.me → Configurar → Extensiones)",
                 font=("Segoe UI", 10), fg=COLORES["suave"], bg=COLORES["panel"]).pack(anchor="w", padx=16, pady=(12, 4))
        fila = tk.Frame(self.marco_endpoint, bg=COLORES["panel"])
        fila.pack(fill="x", padx=16)
        self.var_endpoint = tk.StringVar(value=self.config.get("endpoint", ""))
        self.entrada = tk.Entry(fila, textvariable=self.var_endpoint, show="•", font=("Segoe UI", 11), relief="flat",
                                bg="#FFFFFF", fg="#0B1220", insertbackground="#0B1220")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(fila, text="Pegar", style="Suave.TButton", command=self.pegar).pack(side="left", padx=(8, 0))
        fila2 = tk.Frame(self.marco_endpoint, bg=COLORES["panel"])
        fila2.pack(fill="x", padx=16, pady=(8, 12))
        self.var_mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila2, text="Mostrar", variable=self.var_mostrar, command=self.mostrar).pack(side="left")
        self.boton_desconectar = ttk.Button(fila2, text="Desconectar", style="Suave.TButton", command=self.desconectar, state="disabled")
        self.boton_desconectar.pack(side="right")
        self.boton_conectar = ttk.Button(fila2, text="Guardar y conectar", style="Acento.TButton", command=self.conectar)
        self.boton_conectar.pack(side="right", padx=8)
        self.enlace_endpoint = tk.Label(raiz, text="Cambiar MCP endpoint", font=("Segoe UI", 10, "underline"),
                                        fg=COLORES["acento"], bg=COLORES["fondo"], cursor="hand2")
        self.enlace_endpoint.bind("<Button-1>", lambda _e: self.mostrar_endpoint(True))
        self.ancla = tk.Frame(raiz, bg=COLORES["fondo"], height=1)
        self.ancla.pack(fill="x")

        # --- ejemplos de ordenes
        ejemplos = tk.Frame(raiz, bg=COLORES["fondo"])
        ejemplos.pack(fill="x", padx=22, pady=(8, 2))
        tk.Label(ejemplos, text="Prueba decir «KusiVox» y luego…", font=("Segoe UI", 10, "bold"), fg=COLORES["suave"],
                 bg=COLORES["fondo"]).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        for n, texto in enumerate(EJEMPLOS):
            tk.Label(ejemplos, text=texto, font=("Segoe UI", 10), fg=COLORES["texto"], bg=COLORES["chip"], padx=10, pady=5,
                     anchor="w").grid(row=1 + n // 2, column=n % 2, sticky="we", padx=(0, 8), pady=3)
        ejemplos.grid_columnconfigure(0, weight=1)
        ejemplos.grid_columnconfigure(1, weight=1)

        # --- opciones
        opciones = tk.Frame(raiz, bg=COLORES["fondo"])
        opciones.pack(fill="x", padx=22, pady=(10, 0))
        self.var_auto = tk.BooleanVar(value=self.config.get("autoconectar", True))
        ttk.Checkbutton(opciones, text="Conectar al abrir KusiVox", style="Fondo.TCheckbutton", variable=self.var_auto,
                        command=self.guardar_opciones).pack(anchor="w")
        self.var_inicio = tk.BooleanVar(value=inicio_con_windows())
        ttk.Checkbutton(opciones, text="Iniciar con Windows (recomendado)", style="Fondo.TCheckbutton", variable=self.var_inicio,
                        command=self.cambiar_inicio).pack(anchor="w")
        self.var_despierta = tk.BooleanVar(value=self.config.get("despierta", True))
        ttk.Checkbutton(opciones, text="No dejar que la PC se suspenda mientras está conectado", style="Fondo.TCheckbutton",
                        variable=self.var_despierta, command=self.cambiar_despierta).pack(anchor="w")

        # --- actividad
        tk.Label(raiz, text="Actividad", font=("Segoe UI", 10, "bold"), fg=COLORES["suave"], bg=COLORES["fondo"]).pack(
            anchor="w", padx=22, pady=(12, 4))
        marco = tk.Frame(raiz, bg=COLORES["panel"], highlightbackground=COLORES["borde"], highlightthickness=1)
        marco.pack(fill="both", expand=True, padx=22)
        self.registro = tk.Text(marco, height=7, font=("Consolas", 9), bg=COLORES["panel"], fg=COLORES["texto"], relief="flat",
                                wrap="word", state="disabled", padx=12, pady=8)
        barra = ttk.Scrollbar(marco, command=self.registro.yview)
        self.registro.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.registro.pack(side="left", fill="both", expand=True)

        # --- pie
        pie = tk.Frame(raiz, bg=COLORES["fondo"])
        pie.pack(fill="x", padx=22, pady=12)
        enlace = tk.Label(pie, text="¿Dónde está mi MCP endpoint?", font=("Segoe UI", 10, "underline"),
                          fg=COLORES["acento"], bg=COLORES["fondo"], cursor="hand2")
        enlace.pack(side="left")
        enlace.bind("<Button-1>", lambda _e: webbrowser.open(URL_CONSOLA))
        ttk.Button(pie, text="Salir de KusiVox", style="Suave.TButton", command=self.salir).pack(side="right")

        self._cargar_mascotas()
        self.poner_estado("desconectado")
        self.mostrar_endpoint(not self.var_endpoint.get().strip())
        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.after(150, self.revisar_eventos)
        raiz.after(200, self.animar)
        self.escribir(f"{APP} {VERSION} listo.")
        if minimizado:
            raiz.iconify()
        if self.config.get("autoconectar", True) and self.var_endpoint.get().strip():
            raiz.after(400, self.conectar)

    def _icono(self):
        try:
            self.raiz.iconbitmap(default=str(recurso("kusivox.ico")))
        except Exception:
            pass

    def _cargar_mascotas(self):
        """Cuadros de las animaciones del shih tzu (feliz, pensando, dormido)."""
        for nombre in ("feliz", "pensando", "dormido"):
            cuadros = []
            for i in range(16):
                try:
                    cuadros.append(self.tk.PhotoImage(file=str(recurso(f"mascota_{nombre}.gif")), format=f"gif -index {i}"))
                except Exception:
                    break
            if cuadros:
                self.mascotas[nombre] = cuadros

    def animar(self):
        cuadros = self.mascotas.get(self.animacion)
        if cuadros:
            self.cuadro = (self.cuadro + 1) % len(cuadros)
            self.lienzo.configure(image=cuadros[self.cuadro], width=120, height=120)
        self.raiz.after(170 if self.animacion != "feliz" else 120, self.animar)

    # --- acciones
    def pegar(self):
        try:
            self.var_endpoint.set(self.raiz.clipboard_get().strip())
        except Exception:
            self.escribir("No hay texto copiado para pegar.")

    def mostrar(self):
        self.entrada.configure(show="" if self.var_mostrar.get() else "•")

    def mostrar_endpoint(self, visible: bool):
        if visible:
            self.enlace_endpoint.pack_forget()
            self.marco_endpoint.pack(fill="x", padx=22, pady=6, after=self.ancla)
        else:
            self.marco_endpoint.pack_forget()
            self.enlace_endpoint.pack(anchor="w", padx=24, pady=(0, 4), after=self.ancla)

    def guardar_opciones(self):
        try:
            guardar_config(self.var_endpoint.get().strip(), self.var_auto.get(), self.var_despierta.get())
        except OSError as error:
            self.escribir(f"No se pudo guardar la configuración: {error}")

    def cambiar_inicio(self):
        try:
            fijar_inicio_con_windows(self.var_inicio.get())
            self.escribir("KusiVox se abrirá al iniciar Windows." if self.var_inicio.get() else "KusiVox ya no se abrirá al iniciar Windows.")
        except OSError as error:
            self.escribir(f"No se pudo cambiar el inicio con Windows: {error}")

    def cambiar_despierta(self):
        self.guardar_opciones()
        mantener_despierta(self.var_despierta.get() and self.estado == "conectado")

    def conectar(self):
        url = self.var_endpoint.get().strip()
        problema = validar_endpoint(url)
        if problema:
            self.escribir(problema)
            self.mostrar_endpoint(True)
            return
        self.guardar_opciones()
        self.usuario_desconecto = False
        if self.puente and self.puente.is_alive():
            return
        self.puente = Puente(url, self.eventos)
        self.puente.start()
        self.boton_conectar.configure(state="disabled")
        self.boton_desconectar.configure(state="normal")

    def desconectar(self):
        self.usuario_desconecto = True
        if self.puente:
            self.puente.detener()
            self.escribir("Desconectado por el usuario.")
        self.boton_conectar.configure(state="normal")
        self.boton_desconectar.configure(state="disabled")

    def cerrar(self):
        """La X no apaga KusiVox: lo deja funcionando minimizado para que no se desconecte."""
        if self.puente and self.puente.is_alive():
            self.raiz.iconify()
            self.escribir("KusiVox sigue conectado en segundo plano. Para cerrarlo usa «Salir de KusiVox».")
            return
        self.salir(preguntar=False)

    def salir(self, preguntar: bool = True):
        from tkinter import messagebox
        if preguntar and self.puente and self.puente.is_alive():
            if not messagebox.askyesno(APP, "Si sales de KusiVox, el control por voz de esta PC se detiene. ¿Salir?"):
                return
        if self.puente:
            self.usuario_desconecto = True
            self.puente.detener()
        mantener_despierta(False)
        self.raiz.destroy()

    # --- eventos del puente
    def poner_estado(self, estado: str):
        self.estado = estado
        titulo, ayuda, color, animacion = ESTADOS.get(estado, (estado, "", COLORES["gris"], "dormido"))
        if estado == "desconectado" and self.var_endpoint.get().strip():
            ayuda = "Pulsa «Guardar y conectar» para volver a conectar."
        self.texto_estado.configure(text=titulo)
        self.texto_ayuda.configure(text=ayuda)
        self.punto.itemconfigure(self.circulo, fill=color)
        self.animacion = animacion
        mantener_despierta(estado == "conectado" and self.var_despierta.get())
        if estado == "conectado":
            self.mostrar_endpoint(False)

    def revisar_eventos(self):
        try:
            while True:
                tipo, texto = self.eventos.get_nowait()
                if tipo == "estado":
                    self.poner_estado(texto)
                    if texto == "desconectado":
                        self.boton_conectar.configure(state="normal")
                        self.boton_desconectar.configure(state="disabled")
                        if not self.usuario_desconecto and self.var_auto.get() and self.var_endpoint.get().strip():
                            self.escribir("La conexión se detuvo; vuelvo a conectar en 3 s.")
                            self.raiz.after(3000, self.conectar)
                else:
                    self.escribir(texto)
        except queue.Empty:
            pass
        self.raiz.after(150, self.revisar_eventos)

    def escribir(self, texto: str):
        self.registro.configure(state="normal")
        self.registro.insert("end", time.strftime("%H:%M:%S  ") + texto + "\n")
        lineas = int(self.registro.index("end-1c").split(".")[0])
        if lineas > LINEAS_MAXIMAS:
            self.registro.delete("1.0", f"{lineas - LINEAS_MAXIMAS}.0")
        self.registro.see("end")
        self.registro.configure(state="disabled")

    def ejecutar(self):
        self.raiz.mainloop()


# ---------------------------------------------------------------- una sola instancia
def ya_esta_abierta() -> bool:
    if sys.platform != "win32":
        return False
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "KusiVoxAppUnica")
    return ctypes.windll.kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def autoprueba() -> int:
    """Prueba usada al compilar: cifrado DPAPI, validacion y creacion de la ventana."""
    lineas = []
    codigo = 0
    try:
        secreto = "wss://api.xiaozhi.me/mcp/?token=prueba123"
        assert desproteger(proteger(secreto)) == secreto
        lineas.append("cifrado: OK")
        assert validar_endpoint(secreto) == ""
        assert validar_endpoint("https://x") != ""
        lineas.append("validacion: OK")
        v = Ventana()
        v.raiz.update()
        v.escribir("autoprueba")
        assert len(v.mascotas) == 3, f"animaciones cargadas: {list(v.mascotas)}"
        lineas.append("animaciones: OK (" + ", ".join(f"{k} {len(c)}" for k, c in v.mascotas.items()) + ")")
        v.poner_estado("conectado")
        v.raiz.update()
        v.raiz.after(800, v.raiz.destroy)
        v.raiz.mainloop()
        lineas.append("ventana: OK")
    except Exception as error:
        lineas.append(f"FALLO: {error!r}")
        codigo = 1
    destino = Path(os.environ.get("TEMP") or "/tmp") / "kusivox_autoprueba.txt"
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return codigo


def main() -> int:
    if "--autoprueba" in sys.argv:
        return autoprueba()
    if ya_esta_abierta():
        import tkinter as tk
        from tkinter import messagebox
        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showinfo(APP, "KusiVox ya está abierto. Búscalo en la barra de tareas.")
        return 0
    Ventana(minimizado="--minimizado" in sys.argv).ejecutar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
