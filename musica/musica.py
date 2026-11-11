"""
musica.py - Servidor MCP de musica para el asistente XiaoZhi ("Asistente UC").

El asistente de voz (ESP32-S3 + xiaozhi.me + DeepSeek) puede pedirle a este
programa que reproduzca CUALQUIER cancion, artista, album, genero o estilo en
YouTube, en la computadora, y que pause, pase a la siguiente o cambie el volumen.

Como funciona:
    voz -> ESP32-S3 -> xiaozhi.me (DeepSeek decide usar una herramienta)
        -> punto de acceso MCP (WebSocket) -> mcp_pipe.py -> este programa
        -> abre YouTube en la PC / envia teclas multimedia de Windows

Uso (Windows, dentro de la carpeta del proyecto mcp-calculator de XiaoZhi):
    pip install -r requirements.txt
    $env:MCP_ENDPOINT = "wss://...tu punto de acceso MCP..."
    python mcp_pipe.py musica.py
"""
import json
import logging
import re
import sys
import urllib.parse
import urllib.request
import webbrowser

from fastmcp import FastMCP

# Consola de Windows en UTF-8 (tildes y enes)
if sys.platform == "win32":
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("Musica")
mcp = FastMCP("Musica")

# Estado de la ultima reproduccion
_estado = {"titulo": None, "url": None, "sonando": False}

# ---------------------------------------------------------------------------
# Busqueda en YouTube (solo biblioteca estandar de Python)
# ---------------------------------------------------------------------------
_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
    "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
    "Cookie": "SOCS=CAI; CONSENT=YES+cb",   # evita la pagina de consentimiento de cookies
}


def extraer_videos(html: str, max_resultados: int = 5) -> list:
    """Devuelve [(video_id, titulo), ...] en el orden en que aparecen en la busqueda."""
    resultados = []
    for m in re.finditer(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html):
        video_id = m.group(1)
        if any(v == video_id for v, _ in resultados):
            continue
        tramo = html[m.end(): m.end() + 3000]
        t = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"', tramo)
        titulo = json.loads('"' + t.group(1) + '"') if t else video_id
        resultados.append((video_id, titulo))
        if len(resultados) >= max_resultados:
            break
    if not resultados:  # respaldo si YouTube cambia el formato de la pagina
        for video_id in re.findall(r'"videoId":"([\w-]{11})"', html):
            if video_id not in [v for v, _ in resultados]:
                resultados.append((video_id, video_id))
            if len(resultados) >= max_resultados:
                break
    return resultados


def buscar_en_youtube(busqueda: str) -> list:
    url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(busqueda)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    return extraer_videos(html)


# ---------------------------------------------------------------------------
# Teclas multimedia de Windows (pausa, siguiente, volumen)
# ---------------------------------------------------------------------------
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3


def pulsar_tecla(vk: int, veces: int = 1) -> None:
    if sys.platform != "win32":
        raise RuntimeError("El control multimedia de este programa solo funciona en Windows")
    import ctypes
    KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP = 0x1, 0x2
    for _ in range(veces):
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY, 0)
        ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)


# ---------------------------------------------------------------------------
# Herramientas MCP que puede usar el asistente
# ---------------------------------------------------------------------------
@mcp.tool()
def reproducir_musica(busqueda: str) -> dict:
    """Reproduce en la computadora cualquier canción, artista, álbum, género, estilo o
    ambiente musical, buscándolo en YouTube. Ejemplos de 'busqueda': 'Bohemian Rhapsody Queen',
    'Shakira', 'salsa clásica mix', 'cumbia peruana', 'música para estudiar lo-fi',
    'rock de los 80 playlist'. Para un género o un ánimo, agrega 'mix' o 'playlist'."""
    busqueda = busqueda.strip()
    if not busqueda:
        return {"success": False, "error": "Falta indicar qué música reproducir"}
    try:
        videos = buscar_en_youtube(busqueda)
    except Exception as e:  # sin internet, YouTube no responde, etc.
        logger.error(f"Error buscando '{busqueda}': {e}")
        return {"success": False, "error": f"No se pudo buscar en YouTube: {e}"}
    if not videos:
        return {"success": False, "error": f"No encontré resultados para '{busqueda}'"}

    if _estado["sonando"]:
        try:
            pulsar_tecla(VK_MEDIA_STOP)   # detiene la canción anterior para que no se mezclen
        except RuntimeError:
            pass
    video_id, titulo = videos[0]
    url = f"https://www.youtube.com/watch?v={video_id}"
    webbrowser.open(url, new=2)
    _estado.update(titulo=titulo, url=url, sonando=True)
    logger.info(f"Reproduciendo: {titulo} ({url})")
    return {"success": True, "reproduciendo": titulo,
            "nota": "Suena en la computadora, en YouTube."}


@mcp.tool()
def pausar_o_reanudar_musica() -> dict:
    """Pausa la música si está sonando, o la reanuda si está en pausa."""
    try:
        pulsar_tecla(VK_MEDIA_PLAY_PAUSE)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    _estado["sonando"] = not _estado["sonando"]
    return {"success": True, "sonando": _estado["sonando"]}


@mcp.tool()
def siguiente_cancion() -> dict:
    """Pasa a la siguiente canción (la siguiente recomendada por YouTube)."""
    try:
        pulsar_tecla(VK_MEDIA_NEXT_TRACK)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    _estado["sonando"] = True
    return {"success": True}


@mcp.tool()
def detener_musica() -> dict:
    """Detiene la música que suena en la computadora."""
    try:
        pulsar_tecla(VK_MEDIA_STOP)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    _estado["sonando"] = False
    return {"success": True}


@mcp.tool()
def volumen_computadora(accion: str, pasos: int = 5) -> dict:
    """Cambia el volumen de la computadora. 'accion' debe ser 'subir', 'bajar' o 'silenciar'.
    'pasos' (1 a 25) indica cuánto subir o bajar; cada paso equivale a 2 %."""
    accion = accion.strip().lower()
    pasos = max(1, min(int(pasos), 25))
    teclas = {"subir": VK_VOLUME_UP, "bajar": VK_VOLUME_DOWN, "silenciar": VK_VOLUME_MUTE}
    if accion not in teclas:
        return {"success": False, "error": "La acción debe ser subir, bajar o silenciar"}
    try:
        pulsar_tecla(teclas[accion], 1 if accion == "silenciar" else pasos)
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    return {"success": True, "accion": accion, "pasos": pasos}


@mcp.tool()
def musica_actual() -> dict:
    """Dice qué canción se pidió por última vez y si está sonando."""
    return {"success": True, "titulo": _estado["titulo"], "sonando": _estado["sonando"]}


if __name__ == "__main__":
    mcp.run(transport="stdio")
