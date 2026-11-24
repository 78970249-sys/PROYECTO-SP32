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
}

_cache = {"hora": 0.0, "apps": []}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes y sin signos: 'Configuración!' -> 'configuracion'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^a-z0-9+#]+", " ", texto.lower())
    return " ".join(texto.split())


def _quitar_relleno(consulta: str) -> str:
    """Quita palabras que suelen venir en la orden: 'la aplicacion de word' -> 'word'."""
    palabras = [p for p in consulta.split() if p not in (
        "abre", "abrir", "abreme", "el", "la", "los", "las", "un", "una", "de", "del",
        "app", "aplicacion", "programa", "por", "favor", "porfa", "mi")]
    return " ".join(palabras) or consulta


def _variantes(nombre: str) -> list:
    """Formas de buscar lo que dijo la persona: tal cual y sin palabras de relleno.
    'Bloc de notas' -> ['bloc de notas', 'bloc notas']."""
    tal_cual = re.sub(r"^(abre|abrir|abreme)\s+", "", normalizar(nombre))
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

def ruta_chrome():
    """Ruta de chrome.exe si Google Chrome esta instalado; si no, None."""
    if not ES_WINDOWS:
        return None
    for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            ruta = os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")
            if os.path.isfile(ruta):
                return ruta
    return None


def abrir_en_navegador(url: str) -> None:
    """Abre la URL en Google Chrome; si no esta instalado, en el navegador predeterminado."""
    chrome = ruta_chrome()
    if chrome:
        subprocess.Popen([chrome, url], creationflags=SIN_VENTANA)
    else:
        webbrowser.open(url)


def url_para(direccion: str) -> str:
    """Convierte 'youtube', 'github.com' o 'https://...' en una URL segura (solo http/https)."""
    texto = (direccion or "").strip()
    if re.match(r"^https?://", texto, re.IGNORECASE):
        return texto
    clave = normalizar(texto)
    if clave in SITIOS:
        return SITIOS[clave]
    if re.fullmatch(r"[\w-]+(\.[\w-]+)+(/\S*)?", texto):
        return "https://" + texto
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(texto)


def abrir_pagina_web(direccion: str, abrir=None) -> dict:
    abrir = abrir or abrir_en_navegador
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
