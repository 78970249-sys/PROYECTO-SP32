"""
Funciones para abrir aplicaciones, paginas web y carpetas en Windows.

Este archivo no depende de MCP, para poder probarlo por separado.
Solo abre cosas: no cierra programas, no borra archivos y no ejecuta comandos libres.
"""

import difflib
import json
import logging
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import webbrowser

log = logging.getLogger("escritorio")

ES_WINDOWS = sys.platform == "win32"
SIN_VENTANA = 0x08000000 if ES_WINDOWS else 0  # CREATE_NO_WINDOW

# Cuantos segundos se guarda la lista de aplicaciones antes de volver a leerla.
TIEMPO_CACHE = 300

# Nombres que la gente dice -> nombre (o parte del nombre) en el menu Inicio.
ALIAS = {
    "navegador": ["google chrome", "chrome", "microsoft edge", "firefox"],
    "internet": ["google chrome", "chrome", "microsoft edge", "firefox"],
    "chrome": ["google chrome"],
    "edge": ["microsoft edge"],
    "vs code": ["visual studio code"],
    "vscode": ["visual studio code"],
    "visual studio code": ["visual studio code"],
    "code": ["visual studio code"],
    "word": ["word"],
    "excel": ["excel"],
    "power point": ["powerpoint"],
    "powerpoint": ["powerpoint"],
    "notas": ["bloc de notas", "notepad"],
    "bloc de notas": ["bloc de notas", "notepad"],
    "explorador": ["explorador de archivos", "file explorer"],
    "archivos": ["explorador de archivos", "file explorer"],
    "configuracion": ["configuracion", "settings"],
    "ajustes": ["configuracion", "settings"],
    "terminal": ["terminal", "windows terminal"],
    "consola": ["simbolo del sistema", "command prompt", "terminal"],
    "arduino": ["arduino ide", "arduino"],
    "whatsapp": ["whatsapp"],
    "spotify": ["spotify"],
    "teams": ["microsoft teams", "teams"],
    "camara": ["camara", "camera"],
    "reloj": ["reloj", "clock"],
    "fotos": ["fotos", "photos"],
    # formas coloquiales y errores comunes del reconocimiento de voz
    "calcu": ["calculadora", "calculator"],
    "calculadora": ["calculadora", "calculator"],
    "block de notas": ["bloc de notas", "notepad"],
    "block": ["bloc de notas", "notepad"],
    "bloc": ["bloc de notas", "notepad"],
    "notepad": ["bloc de notas", "notepad"],
    "guord": ["word"], "uord": ["word"], "documento": ["word"], "procesador de texto": ["word"],
    "hoja de calculo": ["excel"], "hojas de calculo": ["excel"], "ecsel": ["excel"],
    "presentacion": ["powerpoint"], "presentaciones": ["powerpoint"], "diapositivas": ["powerpoint"],
    "google": ["google chrome", "chrome", "microsoft edge"],
    "google chrome": ["google chrome"], "crom": ["google chrome"], "cromo": ["google chrome"],
    "wasap": ["whatsapp"], "guasap": ["whatsapp"], "whatsap": ["whatsapp"], "wsp": ["whatsapp"],
    "mensajes": ["whatsapp"],
    "espotifai": ["spotify"], "spotifai": ["spotify"],
    "correo": ["outlook", "correo", "mail"],
    "recortes": ["recortes", "snipping tool"], "herramienta de recortes": ["recortes", "snipping tool"],
    "tienda": ["microsoft store"], "store": ["microsoft store"],
    "mapas": ["mapas", "maps"],
    "grabadora": ["grabadora de sonido", "grabadora", "sound recorder"],
    "grabadora de voz": ["grabadora de sonido", "grabadora", "sound recorder"],
    "reproductor": ["reproductor multimedia", "media player", "windows media player"],
    "pain": ["paint"], "peint": ["paint"],
    "administrador de tareas": ["administrador de tareas", "task manager"],
    # herramientas de accesibilidad de Windows
    "lupa": ["lupa", "magnifier"],
    "narrador": ["narrador", "narrator"],
    "teclado en pantalla": ["teclado en pantalla", "on screen keyboard"],
    "teclado virtual": ["teclado en pantalla", "on screen keyboard"],
}

# Si no aparece en el menu Inicio, se intenta abrir directamente.
DIRECTOS = {
    "bloc de notas": "notepad.exe",
    "notepad": "notepad.exe",
    "notas": "notepad.exe",
    "calculadora": "calc.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorador": "explorer.exe",
    "explorador de archivos": "explorer.exe",
    "archivos": "explorer.exe",
    "simbolo del sistema": "cmd.exe",
    "cmd": "cmd.exe",
    "consola": "cmd.exe",
    "administrador de tareas": "taskmgr.exe",
    "configuracion": "ms-settings:",
    "ajustes": "ms-settings:",
    "calcu": "calc.exe",
    "block de notas": "notepad.exe",
    "block": "notepad.exe",
    "bloc": "notepad.exe",
    "pain": "mspaint.exe",
    # accesibilidad: lupa, narrador y teclado en pantalla vienen con Windows
    "lupa": "magnify.exe",
    "narrador": "narrator.exe",
    "teclado en pantalla": "osk.exe",
    "teclado virtual": "osk.exe",
}

# Entradas del menu Inicio que casi nunca son lo que la persona quiere abrir.
RUIDO = ("desinstalar", "uninstall", "readme", "leame", "release notes", "documentation",
         "documentacion", "website", "sitio web", "help", "ayuda")

SITIOS = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "correo": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "google drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "google maps": "https://maps.google.com",
    "mapas": "https://maps.google.com",
    "traductor": "https://translate.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
    "xiaozhi": "https://xiaozhi.me",
    "wikipedia": "https://es.wikipedia.org",
    "outlook": "https://outlook.live.com",
    "hotmail": "https://outlook.live.com",
    "yutub": "https://www.youtube.com", "youtub": "https://www.youtube.com", "you tube": "https://www.youtube.com",
    "face": "https://www.facebook.com", "feisbuk": "https://www.facebook.com",
    "insta": "https://www.instagram.com", "tik tok": "https://www.tiktok.com",
    "wasap": "https://web.whatsapp.com", "guasap": "https://web.whatsapp.com", "whatsap": "https://web.whatsapp.com",
    "correo de google": "https://mail.google.com", "traductor de google": "https://translate.google.com",
}

CARPETAS = {
    "escritorio": "shell:Desktop",
    "documentos": "shell:Personal",
    "mis documentos": "shell:Personal",
    "descargas": "shell:Downloads",
    "imagenes": "shell:My Pictures",
    "fotos": "shell:My Pictures",
    "musica": "shell:My Music",
    "videos": "shell:My Video",
    "este equipo": "shell:MyComputerFolder",
    "mi pc": "shell:MyComputerFolder",
    "papelera": "shell:RecycleBinFolder",
    "papelera de reciclaje": "shell:RecycleBinFolder",
    "reciclaje": "shell:RecycleBinFolder",
    "mis descargas": "shell:Downloads", "downloads": "shell:Downloads", "desktop": "shell:Desktop",
    "documents": "shell:Personal", "mis imagenes": "shell:My Pictures", "mis fotos": "shell:My Pictures",
    "mi musica": "shell:My Music", "mis videos": "shell:My Video",
    "capturas": "shell:Screenshots", "capturas de pantalla": "shell:Screenshots",
    "mi computadora": "shell:MyComputerFolder", "computadora": "shell:MyComputerFolder",
}

_cache = {"hora": 0.0, "apps": []}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes y sin signos: 'Configuración!' -> 'configuracion'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9+#]+", " ", texto.lower())
    return " ".join(texto.split())


RELLENO = {
    "abre", "abrir", "abreme", "abrime", "abri", "ejecuta", "ejecutar", "inicia", "iniciar", "lanza",
    "pon", "ponme", "quiero", "necesito", "activa", "activar", "enciende", "prende", "usar",
    "el", "la", "los", "las", "un", "una", "de", "del", "app", "aplicacion", "aplicativo", "programa",
    "por", "favor", "porfa", "porfavor", "mi", "ahora", "rapido", "ahi"}

# Verbos con que suele empezar una orden: 'ejecuta el excel', 'puedes abrir word', 'entra a youtube'.
VERBOS = (r"^(?:por favor |porfa )?(?:puedes |podrias |me |quiero |necesito )?"
          r"(?:abre|abrir|abreme|abrime|abri|abres|ejecuta|ejecutar|inicia|iniciar|lanza|lanzar|"
          r"pon|ponme|entra a|entra en|entrar a|ir a|ve a|activa|activar|enciende|prende|usar)\s+")


def _quitar_relleno(consulta: str) -> str:
    """Quita palabras que suelen venir en la orden: 'la aplicacion de word' -> 'word'."""
    palabras = [p for p in consulta.split() if p not in RELLENO]
    return " ".join(palabras) or consulta


def _variantes(nombre: str) -> list:
    """Formas de buscar lo que dijo la persona: tal cual y sin palabras de relleno.
    'Bloc de notas' -> ['bloc de notas', 'bloc notas']."""
    tal_cual = re.sub(VERBOS, "", normalizar(nombre))
    tal_cual = re.sub(r"\s+(por favor|porfa|porfavor)$", "", tal_cual)
    limpio = _quitar_relleno(tal_cual)
    sin_articulo = re.sub(r"^(el|la|los|las|mi|mis)\s+", "", tal_cual)
    return [v for v in dict.fromkeys([tal_cual, sin_articulo, limpio]) if v]


# ---------------------------------------------------------------- aplicaciones

def leer_apps_inicio(forzar: bool = False) -> list:
    """Lista de aplicaciones del menu Inicio: [{'Name': ..., 'AppID': ...}, ...]."""
    if not ES_WINDOWS:
        return []
    ahora = time.time()
    if not forzar and _cache["apps"] and ahora - _cache["hora"] < TIEMPO_CACHE:
        return _cache["apps"]
    orden = ("[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
             "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress")
    try:
        salida = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", orden],
            capture_output=True, timeout=40, creationflags=SIN_VENTANA,
        )
        texto = salida.stdout.decode("utf-8", errors="replace").strip()
        datos = json.loads(texto) if texto else []
        if isinstance(datos, dict):
            datos = [datos]
        apps = [a for a in datos if a.get("Name") and a.get("AppID")]
    except Exception as error:  # PowerShell no disponible, tiempo agotado, etc.
        log.warning("No se pudo leer el menu Inicio: %s", error)
        apps = _cache["apps"]
    _cache.update(hora=ahora, apps=apps)
    return apps


def buscar_apps(nombre: str, apps: list) -> list:
    """Devuelve las apps que mejor coinciden con lo que dijo la persona, la mejor primero."""
    variantes = _variantes(nombre)
    if not variantes:
        return []
    consulta = variantes[-1]
    objetivos = list(dict.fromkeys(
        objetivo for v in variantes for objetivo in ALIAS.get(v, []) + [v]))

    pide_ruido = any(r in consulta for r in RUIDO)
    candidatas = []
    for app in apps:
        nombre_app = normalizar(app["Name"])
        if not pide_ruido and any(r in nombre_app for r in RUIDO):
            continue
        candidatas.append((nombre_app, app))

    for objetivo in objetivos:
        exactas = [a for n, a in candidatas if n == objetivo]
        if exactas:
            return exactas
        empiezan = [(n, a) for n, a in candidatas if n.startswith(objetivo + " ")]
        contienen = [(n, a) for n, a in candidatas
                     if re.search(r"\b" + re.escape(objetivo) + r"\b", n) and (n, a) not in empiezan]
        if empiezan or contienen:
            ordenadas = sorted(empiezan, key=lambda x: len(x[0])) + sorted(contienen, key=lambda x: len(x[0]))
            return [a for _, a in ordenadas]

    palabras = consulta.split()
    if len(palabras) > 1:
        todas = [(n, a) for n, a in candidatas if all(p in n.split() for p in palabras)]
        if todas:
            return [a for _, a in sorted(todas, key=lambda x: len(x[0]))]

    nombres = [n for n, _ in candidatas]
    parecidas = []
    for v in variantes:
        parecidas = difflib.get_close_matches(v, nombres, n=5, cutoff=0.72)
        if parecidas:
            break
    return [a for p in parecidas for n, a in candidatas if n == p][:5]


def _lanzar_appid(appid: str) -> None:
    subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + appid], creationflags=SIN_VENTANA)


def _lanzar_directo(objetivo: str) -> None:
    os.startfile(objetivo)  # solo existe en Windows


def abrir_aplicacion(nombre: str, apps=None, lanzar_appid=_lanzar_appid,
                     lanzar_directo=_lanzar_directo) -> dict:
    variantes = _variantes(nombre)
    if not variantes:
        return {"exito": False, "mensaje": "No entendi que aplicacion abrir."}
    desde_menu_inicio = apps is None
    if desde_menu_inicio:
        if not ES_WINDOWS:
            return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
        apps = leer_apps_inicio()

    coincidencias = buscar_apps(nombre, apps)
    if not coincidencias and desde_menu_inicio:
        # Quizas se instalo algo nuevo: se vuelve a leer el menu Inicio.
        coincidencias = buscar_apps(nombre, leer_apps_inicio(forzar=True))

    if coincidencias:
        elegida = coincidencias[0]
        try:
            lanzar_appid(elegida["AppID"])
        except Exception as error:
            return {"exito": False, "mensaje": f"No se pudo abrir {elegida['Name']}: {error}"}
        otras = [a["Name"] for a in coincidencias[1:4]]
        respuesta = {"exito": True, "abierta": elegida["Name"]}
        if otras:
            respuesta["otras_coincidencias"] = otras
        log.info("Abriendo %s", elegida["Name"])
        return respuesta

    for v in variantes:
        directo = DIRECTOS.get(v)
        if directo:
            try:
                lanzar_directo(directo)
                log.info("Abriendo %s", directo)
                return {"exito": True, "abierta": v}
            except Exception as error:
                return {"exito": False, "mensaje": f"No se pudo abrir {v}: {error}"}

    return {"exito": False,
            "mensaje": f"No encontre ninguna aplicacion llamada '{nombre}'. "
                       "Puedes usar listar_aplicaciones para ver los nombres exactos."}


def listar_aplicaciones(filtro: str = "", apps=None, limite: int = 40) -> dict:
    if apps is None:
        apps = leer_apps_inicio(forzar=True)
    filtro_n = normalizar(filtro)
    nombres = sorted({a["Name"] for a in apps
                      if not filtro_n or filtro_n in normalizar(a["Name"])},
                     key=str.casefold)
    return {"total": len(nombres), "aplicaciones": nombres[:limite]}


# ---------------------------------------------------------------- web y carpetas

# Navegadores que KusiVox sabe abrir: ruta del .exe dentro de Archivos de programa o AppData.
NAVEGADORES = {
    "brave": (r"BraveSoftware\Brave-Browser\Application\brave.exe",),
    "chrome": (r"Google\Chrome\Application\chrome.exe",),
    "edge": (r"Microsoft\Edge\Application\msedge.exe",),
    "firefox": (r"Mozilla Firefox\firefox.exe",),
    "opera": (r"Programs\Opera\opera.exe", r"Opera\opera.exe"),
}
NOMBRES_NAVEGADOR = {
    "brave": "brave", "brave browser": "brave", "breiv": "brave", "breif": "brave",
    "chrome": "chrome", "google chrome": "chrome", "crom": "chrome", "google": "chrome",
    "edge": "edge", "microsoft edge": "edge", "ech": "edge",
    "firefox": "firefox", "mozilla": "firefox", "mozilla firefox": "firefox", "opera": "opera",
    "predeterminado": "", "el predeterminado": "", "el de windows": "",
}
# ProgId del navegador predeterminado de Windows -> navegador
PROGID_NAVEGADOR = {"bravehtml": "brave", "chromehtml": "chrome", "msedgehtm": "edge",
                    "firefoxurl": "firefox", "operastable": "opera"}
ARCHIVO_NAVEGADOR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "KusiVox", "navegador.txt")


def ruta_navegador(nombre: str):
    """Ruta del .exe del navegador si esta instalado; si no, None."""
    if not ES_WINDOWS or nombre not in NAVEGADORES:
        return None
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        for relativa in NAVEGADORES[nombre]:
            if base and os.path.isfile(os.path.join(base, relativa)):
                return os.path.join(base, relativa)
    return None


def ruta_chrome():
    """Ruta de chrome.exe si Google Chrome esta instalado; si no, None."""
    return ruta_navegador("chrome")


def navegador_predeterminado():
    """Navegador que Windows usa para abrir enlaces (Brave, Chrome, Edge, Firefox u Opera)."""
    if not ES_WINDOWS:
        return None
    try:
        import winreg
        clave = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            progid = winreg.QueryValueEx(k, "ProgId")[0].lower()
    except OSError:
        return None
    return next((n for p, n in PROGID_NAVEGADOR.items() if progid.startswith(p)), None)


def nombre_navegador(texto: str):
    """'Brave', 'google chrome', 'el predeterminado' -> 'brave', 'chrome', ''. None si no es un navegador."""
    clave = re.sub(r"^(?:el|la|en|con)\s+|\s+(?:browser|navegador)$", "", normalizar(texto))
    return NOMBRES_NAVEGADOR.get(clave)


def navegador_elegido():
    """El navegador que la persona eligio por voz ('usa Brave'), si sigue instalado."""
    try:
        with open(ARCHIVO_NAVEGADOR, encoding="utf-8") as f:
            nombre = f.read().strip()
    except OSError:
        return None
    return nombre if nombre in NAVEGADORES else None


def elegir_navegador(texto: str, ruta=None) -> dict:
    """Guarda el navegador con el que KusiVox abrira las paginas: 'Brave', 'Chrome', 'Edge'..."""
    ruta = ruta or ruta_navegador
    nombre = nombre_navegador(texto)
    if nombre is None:
        return {"exito": False, "mensaje": "Puedo usar Brave, Chrome, Edge, Firefox u Opera."}
    if nombre and not ruta(nombre):
        return {"exito": False, "mensaje": f"No encontre {nombre} instalado en esta computadora."}
    os.makedirs(os.path.dirname(ARCHIVO_NAVEGADOR), exist_ok=True)
    with open(ARCHIVO_NAVEGADOR, "w", encoding="utf-8") as f:
        f.write(nombre)
    elegido = nombre.capitalize() if nombre else "el navegador predeterminado de Windows"
    log.info("Navegador elegido: %s", elegido)
    return {"exito": True, "navegador": nombre or "predeterminado",
            "decir": f"Listo, desde ahora abro las paginas en {elegido}."}


def abrir_en_navegador(url: str, navegador: str = "") -> None:
    """Abre la URL en el navegador pedido, el elegido por voz, el predeterminado de Windows o Chrome."""
    pedido = nombre_navegador(navegador) if navegador else None
    predeterminado = navegador_predeterminado()
    # Edge suele ser el predeterminado de fabrica: si hay Chrome o Brave instalado, se prefieren.
    orden = (pedido, navegador_elegido(), predeterminado if predeterminado != "edge" else None,
             "chrome", "brave", "firefox", predeterminado, "edge")
    for candidato in orden:
        ruta = ruta_navegador(candidato) if candidato else None
        if ruta:
            subprocess.Popen([ruta, url], creationflags=SIN_VENTANA)
            return
    webbrowser.open(url)


def url_para(direccion: str) -> str:
    """Convierte 'youtube', 'github.com' o 'https://...' en una URL segura (solo http/https)."""
    texto = (direccion or "").strip()
    if re.match(r"^https?://", texto, re.IGNORECASE):
        return texto
    clave = normalizar(texto)
    for intento in (clave, re.sub(r"^(?:la |el )?(?:pagina |sitio |web |pagina web )?(?:de |del )?", "", re.sub(VERBOS, "", clave))):
        if intento in SITIOS:
            return SITIOS[intento]
    if re.fullmatch(r"[\w-]+(\.[\w-]+)+(/\S*)?", texto):
        return "https://" + texto
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(texto)


def abrir_pagina_web(direccion: str, abrir=None, navegador: str = "") -> dict:
    abrir = abrir or (lambda url: abrir_en_navegador(url, navegador))
    if not (direccion or "").strip():
        return {"exito": False, "mensaje": "No se indico que pagina abrir."}
    url = url_para(direccion)
    abrir(url)
    log.info("Abriendo %s", url)
    return {"exito": True, "url": url}


def buscar_en_internet(consulta: str, abrir=None) -> dict:
    abrir = abrir or abrir_en_navegador
    url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(consulta or "")
    abrir(url)
    log.info("Buscando en Google: %s", consulta)
    return {"exito": True, "url": url}


def buscar_en_youtube(consulta: str, abrir=None) -> dict:
    abrir = abrir or abrir_en_navegador
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(consulta or "")
    abrir(url)
    log.info("Buscando en YouTube: %s", consulta)
    return {"exito": True, "url": url}


def abrir_carpeta(nombre: str, lanzar=None) -> dict:
    destino = clave = None
    for v in _variantes(nombre):
        v = re.sub(r"^(la |mi |mis )?carpeta (de |del )?", "", v)
        if v in CARPETAS:
            destino, clave = CARPETAS[v], v
            break
    if not destino:
        # 'abre la carpeta de descargas por favor' -> 'descargas' (la frase mas larga primero)
        frase = normalizar(nombre)
        for k in sorted(CARPETAS, key=len, reverse=True):
            if re.search(r"\b" + re.escape(k) + r"\b", frase):
                destino, clave = CARPETAS[k], k
                break
    if not destino:
        return {"exito": False,
                "mensaje": f"No conozco la carpeta '{nombre}'. Puedo abrir: "
                           + ", ".join(sorted(set(CARPETAS)))}
    if lanzar is None:
        if not ES_WINDOWS:
            return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
        lanzar = lambda d: subprocess.Popen(["explorer.exe", d], creationflags=SIN_VENTANA)
    lanzar(destino)
    log.info("Abriendo carpeta %s", destino)
    return {"exito": True, "carpeta": clave}
