"""
Control de Windows sin raton: teclas multimedia y volumen, atajos de teclado,
escribir texto, ver y cambiar ventanas, y reproducir videos de YouTube.

Usa solo la libreria estandar de Python (ctypes) para hablar con Windows.
Por seguridad no escribe en terminales, PowerShell, la ventana Ejecutar ni VS Code,
y bloquea los atajos Win+R y Win+X.
"""

import ctypes
import logging
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

from apps_windows import abrir_en_navegador

log = logging.getLogger("escritorio")

ES_WINDOWS = sys.platform == "win32"

# ------------------------------------------------------------ estructuras SendInput
# Tamanos fijos (no wintypes) para que la estructura mida lo mismo en cualquier sistema.
DWORD, WORD, LONG = ctypes.c_uint32, ctypes.c_uint16, ctypes.c_int32
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", LONG), ("dy", LONG), ("mouseData", DWORD), ("dwFlags", DWORD),
                ("time", DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", WORD), ("wScan", WORD), ("dwFlags", DWORD), ("time", DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", DWORD), ("wParamL", WORD), ("wParamH", WORD)]


class _UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", DWORD), ("u", _UNION)]


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

HWND = ctypes.c_void_p
ENUM_VENTANAS = (ctypes.WINFUNCTYPE if ES_WINDOWS else ctypes.CFUNCTYPE)(ctypes.c_bool, HWND, ctypes.c_void_p)

if ES_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    dwmapi = ctypes.WinDLL("dwmapi")
    user32.SendInput.argtypes = (ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = ctypes.c_uint
    user32.GetForegroundWindow.restype = HWND
    user32.GetWindowTextLengthW.argtypes = (HWND,)
    user32.GetWindowTextW.argtypes = (HWND, ctypes.c_wchar_p, ctypes.c_int)
    user32.GetClassNameW.argtypes = (HWND, ctypes.c_wchar_p, ctypes.c_int)
    user32.IsWindowVisible.argtypes = (HWND,)
    user32.IsIconic.argtypes = (HWND,)
    user32.GetWindow.argtypes = (HWND, ctypes.c_uint)
    user32.GetWindow.restype = HWND
    user32.ShowWindow.argtypes = (HWND, ctypes.c_int)
    user32.SetForegroundWindow.argtypes = (HWND,)
    user32.EnumWindows.argtypes = (ENUM_VENTANAS, ctypes.c_void_p)
    dwmapi.DwmGetWindowAttribute.argtypes = (HWND, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32)
else:
    user32 = dwmapi = None

# ------------------------------------------------------------ nombres de teclas
VK = {
    "ctrl": 0x11, "control": 0x11, "shift": 0x10, "mayus": 0x10, "mayusculas": 0x10,
    "alt": 0x12, "win": 0x5B, "windows": 0x5B, "tecla windows": 0x5B,
    "enter": 0x0D, "intro": 0x0D, "entrar": 0x0D, "esc": 0x1B, "escape": 0x1B,
    "tab": 0x09, "tabulador": 0x09, "espacio": 0x20, "space": 0x20, "barra espaciadora": 0x20,
    "retroceso": 0x08, "backspace": 0x08, "borrar": 0x08,
    "suprimir": 0x2E, "supr": 0x2E, "delete": 0x2E, "insert": 0x2D, "insertar": 0x2D,
    "arriba": 0x26, "flecha arriba": 0x26, "up": 0x26,
    "abajo": 0x28, "flecha abajo": 0x28, "down": 0x28,
    "izquierda": 0x25, "flecha izquierda": 0x25, "left": 0x25,
    "derecha": 0x27, "flecha derecha": 0x27, "right": 0x27,
    "home": 0x24, "inicio de linea": 0x24, "fin": 0x23, "end": 0x23,
    "repag": 0x21, "pageup": 0x21, "pagina arriba": 0x21, "re pag": 0x21,
    "avpag": 0x22, "pagedown": 0x22, "pagina abajo": 0x22, "av pag": 0x22,
    "imprimir pantalla": 0x2C, "printscreen": 0x2C, "impr pant": 0x2C,
    "menos": 0xBD, "-": 0xBD, "mas": 0xBB, "=": 0xBB, "coma": 0xBC, ",": 0xBC,
    "punto": 0xBE, ".": 0xBE,
}
VK.update({f"f{n}": 0x6F + n for n in range(1, 13)})
# Las letras usan el codigo de la MAYUSCULA (VK 'A' = 0x41); la minuscula seria otra tecla.
VK.update({chr(c): c - 32 for c in range(ord("a"), ord("z") + 1)})
VK.update({chr(c): c for c in range(ord("0"), ord("9") + 1)})
VK["enie"] = 0xC0  # tecla Ñ del teclado en espanol (VK_OEM_3)

EXTENDIDAS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}
MODIFICADORES = {0x11, 0x10, 0x12, 0x5B}
BLOQUEADAS = {frozenset({0x5B, ord("R")}): "Win+R (ventana Ejecutar)",
              frozenset({0x5B, ord("X")}): "Win+X (menu de sistema)"}

MULTIMEDIA = {
    "reproducir": 0xB3, "pausar": 0xB3, "pausa": 0xB3, "play": 0xB3, "continuar": 0xB3,
    "reproducir pausar": 0xB3, "play pause": 0xB3,
    "siguiente": 0xB0, "siguiente cancion": 0xB0, "next": 0xB0,
    "anterior": 0xB1, "cancion anterior": 0xB1, "previous": 0xB1,
    "detener": 0xB2, "stop": 0xB2,
    "subir volumen": 0xAF, "subir": 0xAF, "volumen arriba": 0xAF, "mas volumen": 0xAF,
    "bajar volumen": 0xAE, "bajar": 0xAE, "volumen abajo": 0xAE, "menos volumen": 0xAE,
    "silenciar": 0xAD, "mute": 0xAD, "quitar silencio": 0xAD, "activar sonido": 0xAD,
}

# Ventanas donde no se escribe texto: ahi el texto podria ejecutarse como comando.
CLASES_PROHIBIDAS = {"ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS", "PseudoConsoleWindow"}
TITULOS_PROHIBIDOS = ("powershell", "simbolo del sistema", "command prompt", "cmd.exe",
                      "terminal", "visual studio code", "ejecutar", "run")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    return " ".join(texto.replace("_", " ").split())


# ------------------------------------------------------------ envio de teclas

def _evento(vk=0, scan=0, flags=0) -> INPUT:
    entrada = INPUT(type=INPUT_KEYBOARD)
    entrada.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return entrada


def _enviar(eventos: list) -> None:
    if not ES_WINDOWS:
        raise RuntimeError("solo funciona en Windows")
    arreglo = (INPUT * len(eventos))(*eventos)
    enviados = user32.SendInput(len(eventos), arreglo, ctypes.sizeof(INPUT))
    if enviados != len(eventos):
        raise ctypes.WinError(ctypes.get_last_error())


def eventos_combinacion(codigos: list) -> list:
    """Presiona las teclas en orden y las suelta al reves (ej. Ctrl+Shift+T)."""
    def bandera(vk, soltar):
        return (KEYEVENTF_EXTENDEDKEY if vk in EXTENDIDAS else 0) | (KEYEVENTF_KEYUP if soltar else 0)
    return ([_evento(vk, 0, bandera(vk, False)) for vk in codigos]
            + [_evento(vk, 0, bandera(vk, True)) for vk in reversed(codigos)])


def interpretar_combinacion(teclas: str) -> list:
    """'Ctrl + Shift + T' -> [0x11, 0x10, 0x54]. Lanza ValueError si no se entiende."""
    texto = normalizar((teclas or "").lower().replace("ñ", "enie")).replace("control izquierdo", "ctrl")
    partes = [p.strip() for p in re.split(r"\s*\+\s*", texto) if p.strip()]
    if not partes:
        raise ValueError("no se indico ninguna tecla")
    codigos = []
    for parte in partes:
        if parte not in VK:
            raise ValueError(f"no conozco la tecla '{parte}'")
        codigos.append(VK[parte])
    if not any(c not in MODIFICADORES for c in codigos) and len(codigos) > 1:
        raise ValueError("la combinacion solo tiene teclas como Ctrl/Alt/Shift")
    bloqueo = BLOQUEADAS.get(frozenset(codigos))
    if bloqueo:
        raise PermissionError(f"por seguridad no se permite {bloqueo}")
    return codigos


def presionar_teclas(teclas: str, veces: int = 1, enviar=None) -> dict:
    enviar = enviar or _enviar
    try:
        codigos = interpretar_combinacion(teclas)
    except (ValueError, PermissionError) as error:
        return {"exito": False, "mensaje": str(error)}
    veces = max(1, min(int(veces or 1), 50))
    for i in range(veces):
        enviar(eventos_combinacion(codigos))
        if veces > 1:
            time.sleep(0.05)
    log.info("Teclas: %s x%s", teclas, veces)
    return {"exito": True, "teclas": teclas, "veces": veces}


def controlar_multimedia(accion: str, veces: int = 0, enviar=None) -> dict:
    enviar = enviar or _enviar
    clave = normalizar(accion)
    vk = MULTIMEDIA.get(clave)
    if vk is None:
        return {"exito": False,
                "mensaje": "Accion no valida. Usa: reproducir/pausar, siguiente, anterior, detener, "
                           "subir volumen, bajar volumen o silenciar."}
    if not veces:
        veces = 5 if vk in (0xAF, 0xAE) else 1  # cada pulsacion de volumen es ~2 %
    veces = max(1, min(int(veces), 50))
    for _ in range(veces):
        enviar([_evento(vk, 0, KEYEVENTF_EXTENDEDKEY),
                _evento(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP)])
        time.sleep(0.02)
    log.info("Multimedia: %s x%s", clave, veces)
    return {"exito": True, "accion": clave, "veces": veces}


# ------------------------------------------------------------ ventanas

def _titulo(hwnd) -> str:
    largo = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(largo + 1)
    user32.GetWindowTextW(hwnd, buf, largo + 1)
    return buf.value


def _clase(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def ventana_activa() -> dict:
    if not ES_WINDOWS:
        return {"titulo": "", "clase": ""}
    hwnd = user32.GetForegroundWindow()
    return {"titulo": _titulo(hwnd), "clase": _clase(hwnd)}


def es_ventana_prohibida(titulo: str, clase: str) -> bool:
    if clase in CLASES_PROHIBIDAS:
        return True
    t = normalizar(titulo)
    if clase == "#32770" and t in ("ejecutar", "run"):
        return True
    return any(p in t for p in TITULOS_PROHIBIDOS if p not in ("ejecutar", "run"))


def _oculta(hwnd) -> bool:
    """Ventanas 'fantasma' de apps de Windows que estan cargadas pero no se ven (DWMWA_CLOAKED)."""
    valor = ctypes.c_int(0)
    dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(valor), ctypes.sizeof(valor))
    return valor.value != 0


def listar_ventanas() -> list:
    if not ES_WINDOWS:
        return []
    ventanas = []

    def visitar(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4) and not _oculta(hwnd):
            titulo = _titulo(hwnd)
            if titulo and titulo != "Program Manager":
                ventanas.append((hwnd, titulo))
        return True

    user32.EnumWindows(ENUM_VENTANAS(visitar), None)
    return ventanas


def ver_ventanas() -> dict:
    activa = ventana_activa()
    return {"ventana_activa": activa["titulo"],
            "ventanas_abiertas": [t for _, t in listar_ventanas()][:30]}


def cambiar_a_ventana(nombre: str) -> dict:
    if not ES_WINDOWS:
        return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
    buscado = normalizar(nombre)
    candidatas = [(h, t) for h, t in listar_ventanas() if buscado and buscado in normalizar(t)]
    if not candidatas:
        return {"exito": False, "mensaje": f"No hay ninguna ventana abierta con '{nombre}'.",
                "ventanas_abiertas": [t for _, t in listar_ventanas()][:20]}
    hwnd, titulo = candidatas[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # Pulsar Alt permite a Windows pasar el foco a otra ventana.
    _enviar([_evento(0x12, 0, 0), _evento(0x12, 0, KEYEVENTF_KEYUP)])
    if not user32.SetForegroundWindow(hwnd):
        return {"exito": False, "mensaje": f"Windows no dejo pasar al frente '{titulo}'."}
    log.info("Ventana al frente: %s", titulo)
    return {"exito": True, "ventana": titulo}


def cerrar_ventana_activa() -> dict:
    activa = ventana_activa()
    if es_ventana_prohibida(activa["titulo"], activa["clase"]):
        return {"exito": False, "mensaje": "Por seguridad no cierro terminales ni VS Code."}
    _enviar(eventos_combinacion([0x12, 0x73]))  # Alt+F4
    log.info("Cerrando: %s", activa["titulo"])
    return {"exito": True, "cerrada": activa["titulo"]}


# ------------------------------------------------------------ escribir texto

def eventos_texto(texto: str) -> list:
    eventos = []
    for caracter in texto.replace("\r\n", "\n"):
        if caracter == "\n":
            eventos += [_evento(0x0D, 0, 0), _evento(0x0D, 0, KEYEVENTF_KEYUP)]
            continue
        datos = caracter.encode("utf-16-le")
        for i in range(0, len(datos), 2):
            unidad = int.from_bytes(datos[i:i + 2], "little")
            eventos += [_evento(0, unidad, KEYEVENTF_UNICODE),
                        _evento(0, unidad, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return eventos


def escribir_texto(texto: str, presionar_enter: bool = False, enviar=None, activa=None) -> dict:
    enviar = enviar or _enviar
    activa = activa or ventana_activa()
    if es_ventana_prohibida(activa["titulo"], activa["clase"]):
        return {"exito": False,
                "mensaje": "Por seguridad no escribo en terminales, PowerShell, la ventana Ejecutar "
                           "ni VS Code. Abre o cambia a otra aplicacion primero."}
    texto = (texto or "")[:2000]
    eventos = eventos_texto(texto)
    for i in range(0, len(eventos), 100):  # por partes, para no saturar la ventana
        enviar(eventos[i:i + 100])
        time.sleep(0.01)
    if presionar_enter:
        enviar([_evento(0x0D, 0, 0), _evento(0x0D, 0, KEYEVENTF_KEYUP)])
    log.info("Texto escrito en '%s' (%s caracteres)", activa["titulo"], len(texto))
    return {"exito": True, "ventana": activa["titulo"], "caracteres": len(texto)}


# ------------------------------------------------------------ YouTube

AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")


def id_primer_video(html: str):
    """Saca el id del primer video normal (no anuncio ni short) de una pagina de resultados."""
    m = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html)
    if not m:
        m = re.search(r'/watch\?v=([\w-]{11})', html)
    return m.group(1) if m else None


def reproducir_en_youtube(consulta: str, abrir=None, descargar=None) -> dict:
    abrir = abrir or abrir_en_navegador
    consulta = (consulta or "").strip()
    if not consulta:
        return {"exito": False, "mensaje": "No se indico que reproducir."}
    resultados = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(consulta)
    try:
        if descargar is None:
            pedido = urllib.request.Request(resultados, headers={
                "User-Agent": AGENTE, "Accept-Language": "es-419,es;q=0.9"})
            html = urllib.request.urlopen(pedido, timeout=10).read().decode("utf-8", "replace")
        else:
            html = descargar(resultados)
        video = id_primer_video(html)
    except Exception as error:
        log.warning("No se pudo buscar en YouTube: %s", error)
        video = None
    if not video:
        abrir(resultados)
        return {"exito": True, "url": resultados,
                "nota": "No pude elegir un video; abri los resultados de busqueda."}
    url = f"https://www.youtube.com/watch?v={video}"
    abrir(url)
    log.info("Reproduciendo en YouTube: %s -> %s", consulta, url)
    return {"exito": True, "reproduciendo": consulta, "url": url}
