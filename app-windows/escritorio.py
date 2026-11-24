"""
Servidor MCP "KusiVox PC" para el asistente de voz KusiVox (ESP32-S3).

Le da al asistente herramientas para manejar esta computadora sin raton:
abrir aplicaciones, paginas y carpetas, reproducir en YouTube, controlar la musica
y el volumen, usar atajos de teclado, dictar texto y cambiar de ventana.
Lo arranca la app KusiVox (o puente.py); no hace falta ejecutarlo a mano.
"""

import logging
import sys
import time

from mcp.server import MCPServer

import apps_windows as aw
import control_windows as cw
import sistema_windows as sw

if sys.platform == "win32":
    sys.stderr.reconfigure(encoding="utf-8")

# Los mensajes van a stderr: stdout lo usa el protocolo MCP.
logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")

servidor = MCPServer(
    "KusiVox PC",
    instructions=(
        "Controlas la computadora Windows del usuario con estas herramientas, sin que use el raton. "
        "Cuando el usuario pida hacer algo en su PC, usa SIEMPRE la herramienta adecuada en lugar de "
        "decir que no puedes. Puedes encadenar varias: por ejemplo abrir_aplicacion y luego "
        "escribir_texto, o reproducir_en_youtube y luego controlar_multimedia. "
        "Para poner musica o videos usa reproducir_en_youtube. Para apagar, reiniciar, suspender o bloquear "
        "usa energia; antes de apagar, reiniciar o cerrar sesion pregunta si esta seguro. "
        "Responde en espanol con una frase corta."
    ),
)


# ------------------------------------------------------------ abrir cosas

@servidor.tool()
def abrir_aplicacion(nombre: str) -> dict:
    """Abre una aplicacion instalada en la computadora Windows del usuario.
    Ejemplos: 'abre Word', 'abre la calculadora', 'abre Visual Studio Code', 'abre el navegador'.
    nombre: el nombre de la aplicacion tal como lo dijo."""
    resultado = aw.abrir_aplicacion(nombre)
    if resultado.get("exito"):
        time.sleep(1.5)  # da tiempo a que la ventana aparezca antes de la siguiente orden
    return resultado


@servidor.tool()
def listar_aplicaciones(filtro: str = "") -> dict:
    """Lista las aplicaciones instaladas. Usala si abrir_aplicacion no encontro una aplicacion,
    o si el usuario pregunta que programas tiene. filtro: texto para filtrar (opcional)."""
    return aw.listar_aplicaciones(filtro)


@servidor.tool()
def abrir_pagina_web(direccion: str) -> dict:
    """Abre una pagina web en el navegador. direccion: una URL, un dominio (github.com)
    o el nombre de un sitio conocido (YouTube, Gmail, Google Drive, WhatsApp, Netflix, etc.)."""
    return aw.abrir_pagina_web(direccion)


@servidor.tool()
def buscar_en_internet(consulta: str) -> dict:
    """Busca algo en Google y abre los resultados en el navegador."""
    return aw.buscar_en_internet(consulta)


@servidor.tool()
def reproducir_en_youtube(consulta: str) -> dict:
    """Busca en YouTube y REPRODUCE directamente el primer video encontrado.
    Usala para 'pon musica de Grupo 5', 'reproduce la cancion ...', 'pon un video de ...'.
    consulta: artista, cancion o tema, por ejemplo 'Grupo 5 mix'."""
    return cw.reproducir_en_youtube(consulta)


@servidor.tool()
def buscar_en_youtube(consulta: str) -> dict:
    """Muestra la lista de resultados de YouTube sin reproducir nada.
    Usala solo si el usuario quiere ver opciones; para poner musica usa reproducir_en_youtube."""
    return aw.buscar_en_youtube(consulta)


@servidor.tool()
def abrir_carpeta(nombre: str) -> dict:
    """Abre una carpeta en el Explorador de archivos.
    nombre: escritorio, documentos, descargas, imagenes, musica, videos, este equipo o papelera."""
    return aw.abrir_carpeta(nombre)


# ------------------------------------------------------------ musica y volumen

@servidor.tool()
def controlar_multimedia(accion: str, veces: int = 0) -> dict:
    """Controla la musica o el video que esta sonando y el volumen de la computadora.
    accion: 'pausar' o 'reproducir' (es la misma tecla), 'siguiente', 'anterior', 'detener',
    'subir volumen', 'bajar volumen' o 'silenciar'.
    veces: cuantas pulsaciones (opcional). Cada pulsacion de volumen cambia ~2 %;
    si no se indica, el volumen cambia ~10 %."""
    return cw.controlar_multimedia(accion, veces)


# ------------------------------------------------------------ teclado

@servidor.tool()
def presionar_teclas(teclas: str, veces: int = 1) -> dict:
    """Presiona una tecla o un atajo de teclado en la ventana que esta al frente.
    teclas: una tecla o combinacion con '+'. Ejemplos:
    'ctrl+t' (nueva pestana), 'ctrl+w' (cerrar pestana), 'ctrl+tab' (siguiente pestana),
    'alt+tab' (cambiar de ventana), 'win+d' (mostrar escritorio), 'f' (pantalla completa en YouTube),
    'espacio' (pausar en YouTube), 'abajo' o 'avpag' (bajar), 'arriba' o 'repag' (subir),
    'ctrl+c', 'ctrl+v', 'ctrl+z', 'ctrl+s', 'enter', 'esc', 'f5' (recargar), 'win' (menu Inicio).
    veces: cuantas veces repetirla (por ejemplo 5 para bajar varias lineas)."""
    return cw.presionar_teclas(teclas, veces)


@servidor.tool()
def escribir_texto(texto: str, presionar_enter: bool = False) -> dict:
    """Escribe texto en la ventana que esta al frente, como si se tecleara (dictado).
    Sirve para escribir en Word, el Bloc de notas, un chat o el buscador de una pagina.
    presionar_enter: true para pulsar Enter al final (por ejemplo para enviar o buscar).
    Por seguridad no escribe en terminales ni en VS Code."""
    return cw.escribir_texto(texto, presionar_enter)


# ------------------------------------------------------------ ventanas

@servidor.tool()
def ver_ventanas() -> dict:
    """Dice cual es la ventana que esta al frente y que otras ventanas estan abiertas."""
    return cw.ver_ventanas()


@servidor.tool()
def cambiar_a_ventana(nombre: str) -> dict:
    """Trae al frente una ventana abierta cuyo titulo contenga 'nombre' (por ejemplo 'YouTube',
    'Word', 'Chrome', 'Bloc de notas')."""
    return cw.cambiar_a_ventana(nombre)


@servidor.tool()
def cerrar_ventana_activa() -> dict:
    """Cierra la ventana que esta al frente (como Alt+F4). Si hay cambios sin guardar,
    la aplicacion preguntara antes de cerrarse."""
    return cw.cerrar_ventana_activa()


# ------------------------------------------------------------ sistema

@servidor.tool()
def energia(accion: str, segundos: int = 30, confirmado: bool = False) -> dict:
    """Apaga, reinicia, suspende, hiberna o bloquea la computadora, cierra la sesion, apaga la pantalla
    o cancela un apagado pendiente.
    accion: 'apagar', 'reiniciar', 'cancelar' (cancela un apagado o reinicio), 'suspender', 'hibernar',
    'bloquear', 'cerrar sesion' o 'apagar pantalla'.
    segundos: espera antes de apagar o reiniciar (minimo 10, por defecto 30), para poder cancelar.
    confirmado: para apagar, reiniciar o cerrar sesion, PRIMERO pregunta al usuario si esta seguro
    (se cierran los programas y se puede perder lo no guardado) y solo si dice que si usa confirmado=true."""
    return sw.energia(accion, segundos, confirmado)


@servidor.tool()
def fijar_volumen(nivel: int) -> dict:
    """Pone el volumen de la computadora en un porcentaje exacto, de 0 a 100 (ej. 'volumen al 40')."""
    return sw.fijar_volumen(nivel)


@servidor.tool()
def fijar_brillo(nivel: int) -> dict:
    """Pone el brillo de la pantalla de la laptop en un porcentaje exacto, de 0 a 100."""
    return sw.fijar_brillo(nivel)


@servidor.tool()
def cerrar_aplicacion(nombre: str) -> dict:
    """Cierra todas las ventanas de una aplicacion por su nombre (ej. 'cierra Chrome', 'cierra Word'),
    como pulsar la X. Si hay cambios sin guardar, la aplicacion pregunta antes de cerrarse."""
    return sw.cerrar_aplicacion(nombre)


@servidor.tool()
def abrir_configuracion(seccion: str) -> dict:
    """Abre una seccion de la Configuracion de Windows: wifi, bluetooth, pantalla, sonido,
    actualizaciones, bateria, energia, aplicaciones, fondo de pantalla, tema, fecha y hora, idioma,
    almacenamiento, mouse, notificaciones, impresoras o configuracion (inicio)."""
    return sw.abrir_configuracion(seccion)


@servidor.tool()
def tomar_captura() -> dict:
    """Toma una captura de toda la pantalla; Windows la guarda en Imagenes > Capturas de pantalla."""
    return sw.tomar_captura()


@servidor.tool()
def estado_del_sistema() -> dict:
    """Dice la fecha y hora, la bateria (y si esta cargando), el uso de RAM y de CPU,
    y el espacio libre en el disco C."""
    return sw.estado_del_sistema()


if __name__ == "__main__":
    servidor.run(transport="stdio")
