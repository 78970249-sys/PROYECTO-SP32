"""
Control del sistema Windows por voz: energia (apagar, reiniciar, suspender, bloquear...),
volumen y brillo exactos, cerrar aplicaciones, configuracion de Windows, capturas y
estado del equipo. Solo usa la libreria estandar de Python.

Seguridad: apagar, reiniciar y cerrar sesion necesitan confirmacion y esperan al menos
10 segundos ("cancela el apagado" lo detiene). No hay ejecucion de comandos libres.
"""

import ctypes
import datetime
import logging
import os
import shutil
import subprocess
import time

import control_windows as cw

log = logging.getLogger("escritorio")

ES_WINDOWS = cw.ES_WINDOWS
SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0
HWND = ctypes.c_void_p

if ES_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.PostMessageW.argtypes = (HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
    user32.PostMessageW.restype = ctypes.c_bool
else:
    user32 = kernel32 = None

AVISO = "Pedido a KusiVox. Di 'KusiVox, cancela el apagado' para detenerlo."

ENERGIA = {
    "apagar": "apagar", "apaga": "apagar", "apagar computadora": "apagar", "apaga la computadora": "apagar",
    "apagar la computadora": "apagar", "apagar pc": "apagar", "apaga la pc": "apagar", "shutdown": "apagar",
    "reiniciar": "reiniciar", "reinicia": "reiniciar", "reinicia la computadora": "reiniciar", "restart": "reiniciar",
    "cancelar": "cancelar", "cancela": "cancelar", "cancelar apagado": "cancelar", "cancela el apagado": "cancelar",
    "cancelar reinicio": "cancelar", "cancela el reinicio": "cancelar",
    "suspender": "suspender", "suspende": "suspender", "suspension": "suspender", "dormir": "suspender",
    "modo suspension": "suspender", "sleep": "suspender",
    "hibernar": "hibernar", "hiberna": "hibernar",
    "bloquear": "bloquear", "bloquea": "bloquear", "bloquear pantalla": "bloquear", "bloquea la pc": "bloquear",
    "cerrar sesion": "cerrar sesion", "cierra sesion": "cerrar sesion", "cierra la sesion": "cerrar sesion",
    "apagar pantalla": "apagar pantalla", "apaga la pantalla": "apagar pantalla", "apagar monitor": "apagar pantalla",
    "apaga el monitor": "apagar pantalla",
}
NECESITAN_CONFIRMAR = {"apagar", "reiniciar", "cerrar sesion"}

CONFIGURACION = {
    "wifi": "ms-settings:network-wifi", "wi fi": "ms-settings:network-wifi", "red": "ms-settings:network",
    "redes": "ms-settings:network", "internet": "ms-settings:network",
    "bluetooth": "ms-settings:bluetooth", "dispositivos": "ms-settings:bluetooth",
    "pantalla": "ms-settings:display", "brillo": "ms-settings:display", "resolucion": "ms-settings:display",
    "sonido": "ms-settings:sound", "audio": "ms-settings:sound",
    "actualizaciones": "ms-settings:windowsupdate", "windows update": "ms-settings:windowsupdate",
    "bateria": "ms-settings:batterysaver", "energia": "ms-settings:powersleep", "inicio y apagado": "ms-settings:powersleep",
    "aplicaciones": "ms-settings:appsfeatures", "programas": "ms-settings:appsfeatures",
    "fondo": "ms-settings:personalization-background", "fondo de pantalla": "ms-settings:personalization-background",
    "colores": "ms-settings:personalization-colors", "tema": "ms-settings:themes",
    "hora": "ms-settings:dateandtime", "fecha y hora": "ms-settings:dateandtime",
    "idioma": "ms-settings:regionlanguage", "almacenamiento": "ms-settings:storagesense",
    "privacidad": "ms-settings:privacy", "mouse": "ms-settings:mousetouchpad", "raton": "ms-settings:mousetouchpad",
    "notificaciones": "ms-settings:notifications", "impresoras": "ms-settings:printers",
    "configuracion": "ms-settings:", "ajustes": "ms-settings:",
}


def _lanzar(args):
    subprocess.Popen(args, creationflags=SIN_VENTANA)


def _apagar_monitor():
    # HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2 = apagar
    user32.PostMessageW(HWND(0xFFFF), 0x0112, 0xF170, 2)


# ------------------------------------------------------------ energia

def energia(accion: str, segundos: int = 30, confirmado: bool = False, lanzar=None, apagar_monitor=None) -> dict:
    lanzar = lanzar or _lanzar
    apagar_monitor = apagar_monitor or _apagar_monitor
    clave = cw.normalizar(accion)
    accion_n = ENERGIA.get(clave)
    if accion_n is None:
        # la frase mas larga primero: "apaga la pantalla" no debe leerse como "apaga" (apagar la PC)
        for palabra in sorted(ENERGIA, key=len, reverse=True):
            if palabra in clave:
                accion_n = ENERGIA[palabra]
                break
    if accion_n is None:
        return {"exito": False, "mensaje": "Accion no valida. Usa: apagar, reiniciar, cancelar, suspender, "
                                           "hibernar, bloquear, cerrar sesion o apagar pantalla."}
    if accion_n in NECESITAN_CONFIRMAR and not confirmado:
        return {"exito": False, "requiere_confirmacion": True,
                "mensaje": f"Antes de {accion_n}, pregunta al usuario si esta seguro (se cerraran los programas "
                           "y se puede perder lo no guardado). Si dice que si, vuelve a llamar con confirmado=true."}
    segundos = max(10, min(int(segundos or 30), 3600))
    if accion_n == "apagar":
        lanzar(["shutdown", "/s", "/t", str(segundos), "/c", "Apagado " + AVISO])
    elif accion_n == "reiniciar":
        lanzar(["shutdown", "/r", "/t", str(segundos), "/c", "Reinicio " + AVISO])
    elif accion_n == "cancelar":
        lanzar(["shutdown", "/a"])
    elif accion_n == "cerrar sesion":
        lanzar(["shutdown", "/l"])
    elif accion_n == "hibernar":
        lanzar(["shutdown", "/h"])
    elif accion_n == "suspender":
        lanzar(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
    elif accion_n == "bloquear":
        lanzar(["rundll32.exe", "user32.dll,LockWorkStation"])
    elif accion_n == "apagar pantalla":
        apagar_monitor()
    log.info("Energia: %s", accion_n)
    respuesta = {"exito": True, "accion": accion_n}
    if accion_n in ("apagar", "reiniciar"):
        respuesta["en_segundos"] = segundos
        respuesta["nota"] = "Se puede cancelar diciendo 'cancela el apagado'."
    return respuesta


# ------------------------------------------------------------ volumen y brillo

def fijar_volumen(nivel: int, enviar=None) -> dict:
    """Pone el volumen en un nivel exacto (0-100): lo baja a 0 y lo sube de 2 en 2."""
    enviar = enviar or cw._enviar
    n = max(0, min(100, int(nivel)))
    def pulsar(vk):
        enviar([cw._evento(vk, 0, cw.KEYEVENTF_EXTENDEDKEY),
                cw._evento(vk, 0, cw.KEYEVENTF_EXTENDEDKEY | cw.KEYEVENTF_KEYUP)])
        time.sleep(0.01)
    for _ in range(50):
        pulsar(0xAE)
    for _ in range(round(n / 2)):
        pulsar(0xAF)
    log.info("Volumen: %s %%", n)
    return {"exito": True, "volumen": n}


def _powershell(orden: str, timeout: int = 20) -> str:
    salida = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
                            capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
    if salida.returncode != 0:
        raise RuntimeError(salida.stderr.decode("utf-8", "replace").strip()[:200] or "error de PowerShell")
    return salida.stdout.decode("utf-8", "replace").strip()


def fijar_brillo(nivel: int, powershell=None) -> dict:
    powershell = powershell or _powershell
    n = max(0, min(100, int(nivel)))
    try:
        powershell("Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
                   f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={n}}} | Out-Null")
    except Exception as error:
        return {"exito": False, "mensaje": "No se pudo cambiar el brillo. Solo funciona en laptops con "
                                           f"pantalla integrada. Detalle: {error}"}
    log.info("Brillo: %s %%", n)
    return {"exito": True, "brillo": n}


# ------------------------------------------------------------ aplicaciones y ventanas

def cerrar_aplicacion(nombre: str, ventanas=None, cerrar=None) -> dict:
    """Cierra (con WM_CLOSE, como pulsar la X) las ventanas cuyo titulo contiene el nombre."""
    if ventanas is None:
        ventanas = cw.listar_ventanas()
    if cerrar is None:
        cerrar = lambda h: user32.PostMessageW(h, 0x0010, 0, 0)
    buscado = cw.normalizar(nombre)
    for relleno in ("la aplicacion ", "el programa ", "la ", "el "):
        if buscado.startswith(relleno):
            buscado = buscado[len(relleno):]
    cerradas, protegidas = [], []
    for hwnd, titulo in ventanas:
        if buscado and buscado in cw.normalizar(titulo):
            if cw.es_ventana_prohibida(titulo, ""):
                protegidas.append(titulo)
                continue
            cerrar(hwnd)
            cerradas.append(titulo)
    if not cerradas:
        mensaje = f"No hay ninguna ventana abierta de '{nombre}'."
        if protegidas:
            mensaje = "Por seguridad no cierro terminales ni VS Code (ahi corre este programa)."
        return {"exito": False, "mensaje": mensaje}
    log.info("Cerrando: %s", ", ".join(cerradas))
    return {"exito": True, "cerradas": cerradas,
            "nota": "Si habia cambios sin guardar, la aplicacion preguntara antes de cerrarse."}


def abrir_configuracion(seccion: str, abrir=None) -> dict:
    abrir = abrir or os.startfile
    clave = cw.normalizar(seccion)
    for quitar in ("la configuracion de ", "configuracion de ", "ajustes de ", "el ", "la ", "los ", "las "):
        if clave.startswith(quitar):
            clave = clave[len(quitar):]
    destino = CONFIGURACION.get(clave)
    if destino is None:
        return {"exito": False, "mensaje": "Seccion no reconocida. Puedo abrir: "
                                           + ", ".join(sorted({k for k in CONFIGURACION if len(k) > 3}))}
    abrir(destino)
    log.info("Configuracion: %s", destino)
    return {"exito": True, "seccion": clave}


def tomar_captura(enviar=None) -> dict:
    """Win + Impr Pant: Windows guarda la captura en Imagenes > Capturas de pantalla."""
    enviar = enviar or cw._enviar
    enviar(cw.eventos_combinacion([0x5B, 0x2C]))
    log.info("Captura de pantalla")
    return {"exito": True, "guardada_en": "Imagenes > Capturas de pantalla"}


# ------------------------------------------------------------ estado del equipo

class _ESTADO_ENERGIA(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_uint8), ("BatteryFlag", ctypes.c_uint8),
                ("BatteryLifePercent", ctypes.c_uint8), ("SystemStatusFlag", ctypes.c_uint8),
                ("BatteryLifeTime", ctypes.c_uint32), ("BatteryFullLifeTime", ctypes.c_uint32)]


class _MEMORIA(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_uint32), ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64), ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64), ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64), ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64)]


def estado_del_sistema() -> dict:
    ahora = datetime.datetime.now()
    estado = {"fecha": ahora.strftime("%d/%m/%Y"), "hora": ahora.strftime("%H:%M")}
    if not ES_WINDOWS:
        return estado
    e = _ESTADO_ENERGIA()
    if kernel32.GetSystemPowerStatus(ctypes.byref(e)):
        if e.BatteryFlag != 128 and e.BatteryLifePercent != 255:
            estado["bateria_porcentaje"] = e.BatteryLifePercent
            estado["cargando"] = e.ACLineStatus == 1
        else:
            estado["bateria"] = "sin bateria (PC de escritorio)"
    m = _MEMORIA(dwLength=ctypes.sizeof(_MEMORIA))
    if kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        estado["ram_usada_porcentaje"] = m.dwMemoryLoad
        estado["ram_total_gb"] = round(m.ullTotalPhys / 2 ** 30, 1)
    try:
        disco = shutil.disk_usage("C:\\")
        estado["disco_c_libre_gb"] = round(disco.free / 2 ** 30, 1)
        estado["disco_c_total_gb"] = round(disco.total / 2 ** 30, 1)
    except OSError:
        pass
    try:
        cpu = _powershell("(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage "
                          "-Average).Average", timeout=15)
        estado["cpu_porcentaje"] = round(float(cpu.replace(",", ".")))
    except Exception:
        pass
    return estado
