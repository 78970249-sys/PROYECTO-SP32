"""
KusiVox para Windows: conecta tu asistente de voz KusiVox con esta computadora.

La ventana guarda tu MCP endpoint (cifrado con la cuenta de Windows), se conecta a
xiaozhi.me y arranca el servidor de herramientas (KusiVoxServidor.exe). Si la conexion
se corta, vuelve a conectarse sola.

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
VERSION = "1.0.0"
URL_CONSOLA = "https://xiaozhi.me"
URL_APP_CELULAR = "https://78970249-sys.github.io/PROYECTO-SP32/"
CARPETA_DATOS = Path(os.environ.get("APPDATA") or Path.home()) / APP
ARCHIVO_CONFIG = CARPETA_DATOS / "config.json"
ESPERA_MAXIMA = 60
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
    return datos


def guardar_config(endpoint: str, autoconectar: bool) -> None:
    CARPETA_DATOS.mkdir(parents=True, exist_ok=True)
    datos = {"endpoint": proteger(endpoint) if endpoint else "", "autoconectar": bool(autoconectar)}
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
        async with websockets.connect(self.url, ping_interval=20, ping_timeout=30, max_size=None) as ws:
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


# ---------------------------------------------------------------- ventana
COLORES = {"fondo": "#0E1726", "panel": "#16223A", "texto": "#FFFFFF", "suave": "#AEB8C8",
           "acento": "#1A93CF", "rosa": "#FF6E9C", "verde": "#2A9D6B", "ambar": "#D98A1C", "gris": "#7A8699"}
ESTADOS = {
    "desconectado": ("Desconectado", COLORES["gris"]),
    "conectando": ("Conectando…", COLORES["ambar"]),
    "reintentando": ("Reconectando…", COLORES["ambar"]),
    "conectado": ("Conectado: KusiVox puede controlar esta PC", COLORES["verde"]),
}


class Ventana:
    def __init__(self, minimizado: bool = False):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.eventos = queue.Queue()
        self.puente = None
        self.config = leer_config()

        self.raiz = raiz = tk.Tk()
        raiz.title(f"{APP} {VERSION}")
        raiz.geometry("560x600")
        raiz.minsize(480, 520)
        raiz.configure(bg=COLORES["fondo"])
        self._icono()

        estilo = ttk.Style(raiz)
        estilo.theme_use("clam")
        estilo.configure("TCheckbutton", background=COLORES["fondo"], foreground=COLORES["texto"])
        estilo.map("TCheckbutton", background=[("active", COLORES["fondo"])])
        estilo.configure("Acento.TButton", background=COLORES["acento"], foreground="#FFFFFF", borderwidth=0, padding=(14, 8))
        estilo.map("Acento.TButton", background=[("active", "#157AAD")])
        estilo.configure("Suave.TButton", background=COLORES["panel"], foreground=COLORES["texto"], borderwidth=0, padding=(14, 8))
        estilo.map("Suave.TButton", background=[("active", "#22324F")])

        cab = tk.Frame(raiz, bg=COLORES["fondo"])
        cab.pack(fill="x", padx=20, pady=(18, 6))
        tk.Label(cab, text=APP, font=("Segoe UI", 22, "bold"), fg=COLORES["texto"], bg=COLORES["fondo"]).pack(anchor="w")
        tk.Label(cab, text="Control de tu computadora por voz", font=("Segoe UI", 11), fg=COLORES["suave"], bg=COLORES["fondo"]).pack(anchor="w")

        est = tk.Frame(raiz, bg=COLORES["panel"])
        est.pack(fill="x", padx=20, pady=8)
        self.punto = tk.Canvas(est, width=14, height=14, bg=COLORES["panel"], highlightthickness=0)
        self.punto.pack(side="left", padx=(14, 8), pady=12)
        self.circulo = self.punto.create_oval(2, 2, 12, 12, fill=COLORES["gris"], outline="")
        self.texto_estado = tk.Label(est, text="Desconectado", font=("Segoe UI", 11, "bold"), fg=COLORES["texto"], bg=COLORES["panel"])
        self.texto_estado.pack(side="left", pady=12)

        caja = tk.Frame(raiz, bg=COLORES["fondo"])
        caja.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(caja, text="MCP endpoint de tu agente (xiaozhi.me → Configurar → Extensiones)", font=("Segoe UI", 10),
                 fg=COLORES["suave"], bg=COLORES["fondo"]).pack(anchor="w")
        fila = tk.Frame(caja, bg=COLORES["fondo"])
        fila.pack(fill="x", pady=(4, 0))
        self.var_endpoint = tk.StringVar(value=self.config.get("endpoint", ""))
        self.entrada = tk.Entry(fila, textvariable=self.var_endpoint, show="•", font=("Segoe UI", 11), relief="flat",
                                bg="#FFFFFF", fg="#0E1726", insertbackground="#0E1726")
        self.entrada.pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(fila, text="Pegar", style="Suave.TButton", command=self.pegar).pack(side="left", padx=(8, 0))
        self.var_mostrar = tk.BooleanVar(value=False)
        ttk.Checkbutton(caja, text="Mostrar", variable=self.var_mostrar, command=self.mostrar).pack(anchor="w", pady=(4, 0))

        botones = tk.Frame(raiz, bg=COLORES["fondo"])
        botones.pack(fill="x", padx=20, pady=10)
        self.boton_conectar = ttk.Button(botones, text="Guardar y conectar", style="Acento.TButton", command=self.conectar)
        self.boton_conectar.pack(side="left")
        self.boton_desconectar = ttk.Button(botones, text="Desconectar", style="Suave.TButton", command=self.desconectar, state="disabled")
        self.boton_desconectar.pack(side="left", padx=8)

        opciones = tk.Frame(raiz, bg=COLORES["fondo"])
        opciones.pack(fill="x", padx=20)
        self.var_auto = tk.BooleanVar(value=self.config.get("autoconectar", True))
        ttk.Checkbutton(opciones, text="Conectar al abrir KusiVox", variable=self.var_auto, command=self.guardar_opciones).pack(anchor="w")
        self.var_inicio = tk.BooleanVar(value=inicio_con_windows())
        ttk.Checkbutton(opciones, text="Iniciar con Windows", variable=self.var_inicio, command=self.cambiar_inicio).pack(anchor="w")

        tk.Label(raiz, text="Actividad", font=("Segoe UI", 10, "bold"), fg=COLORES["suave"], bg=COLORES["fondo"]).pack(anchor="w", padx=20, pady=(12, 2))
        marco = tk.Frame(raiz, bg=COLORES["panel"])
        marco.pack(fill="both", expand=True, padx=20)
        self.registro = tk.Text(marco, height=10, font=("Consolas", 9), bg=COLORES["panel"], fg=COLORES["texto"], relief="flat",
                                wrap="word", state="disabled", padx=10, pady=8)
        barra = ttk.Scrollbar(marco, command=self.registro.yview)
        self.registro.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.registro.pack(side="left", fill="both", expand=True)

        pie = tk.Frame(raiz, bg=COLORES["fondo"])
        pie.pack(fill="x", padx=20, pady=12)
        for texto, url in (("¿Dónde está mi MCP endpoint?", URL_CONSOLA), ("App para el celular", URL_APP_CELULAR)):
            enlace = tk.Label(pie, text=texto, font=("Segoe UI", 10, "underline"), fg=COLORES["acento"], bg=COLORES["fondo"], cursor="hand2")
            enlace.pack(side="left", padx=(0, 16))
            enlace.bind("<Button-1>", lambda _e, u=url: webbrowser.open(u))

        raiz.protocol("WM_DELETE_WINDOW", self.cerrar)
        raiz.after(150, self.revisar_eventos)
        self.escribir(f"{APP} {VERSION} listo.")
        if minimizado:
            raiz.iconify()
        if self.config.get("autoconectar", True) and self.var_endpoint.get().strip():
            raiz.after(400, self.conectar)

    def _icono(self):
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        try:
            self.raiz.iconbitmap(default=str(base / "kusivox.ico"))
        except Exception:
            pass

    # --- acciones
    def pegar(self):
        try:
            self.var_endpoint.set(self.raiz.clipboard_get().strip())
        except Exception:
            self.escribir("No hay texto copiado para pegar.")

    def mostrar(self):
        self.entrada.configure(show="" if self.var_mostrar.get() else "•")

    def guardar_opciones(self):
        try:
            guardar_config(self.var_endpoint.get().strip(), self.var_auto.get())
        except OSError as error:
            self.escribir(f"No se pudo guardar la configuración: {error}")

    def cambiar_inicio(self):
        try:
            fijar_inicio_con_windows(self.var_inicio.get())
            self.escribir("KusiVox se abrirá al iniciar Windows." if self.var_inicio.get() else "KusiVox ya no se abrirá al iniciar Windows.")
        except OSError as error:
            self.escribir(f"No se pudo cambiar el inicio con Windows: {error}")

    def conectar(self):
        url = self.var_endpoint.get().strip()
        problema = validar_endpoint(url)
        if problema:
            self.escribir(problema)
            return
        self.guardar_opciones()
        if self.puente and self.puente.is_alive():
            return
        self.puente = Puente(url, self.eventos)
        self.puente.start()
        self.boton_conectar.configure(state="disabled")
        self.boton_desconectar.configure(state="normal")

    def desconectar(self):
        if self.puente:
            self.puente.detener()
            self.escribir("Desconectado por el usuario.")
        self.boton_conectar.configure(state="normal")
        self.boton_desconectar.configure(state="disabled")

    def cerrar(self):
        from tkinter import messagebox
        if self.puente and self.puente.is_alive():
            if not messagebox.askyesno(APP, "Si cierras KusiVox, el control por voz de esta PC se detiene. ¿Cerrar?"):
                return
            self.puente.detener()
        self.raiz.destroy()

    # --- eventos del puente
    def revisar_eventos(self):
        try:
            while True:
                tipo, texto = self.eventos.get_nowait()
                if tipo == "estado":
                    etiqueta, color = ESTADOS.get(texto, (texto, COLORES["gris"]))
                    self.texto_estado.configure(text=etiqueta)
                    self.punto.itemconfigure(self.circulo, fill=color)
                    if texto == "desconectado":
                        self.boton_conectar.configure(state="normal")
                        self.boton_desconectar.configure(state="disabled")
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
