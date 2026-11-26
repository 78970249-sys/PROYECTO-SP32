"""
Servidor MCP "KusiVox PC" para el asistente de voz KusiVox (ESP32-S3).

Le da al asistente herramientas para manejar esta computadora solo con la voz:
entender ordenes libres, abrir aplicaciones, paginas y carpetas, reproducir en YouTube
(en la misma pestana), controlar la musica y el volumen, usar atajos por su nombre,
dictar texto en una aplicacion, hacer clic por nombre, usar el mouse y leer la pantalla.
Lo arranca la app KusiVox (o puente.py); no hace falta ejecutarlo a mano.
"""

import logging
import sys
import threading
import time

from mcp.server import MCPServer

import acciones_windows as ac
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
        "Eres un asistente profesional que maneja la computadora Windows del usuario solo con la voz; "
        "muchos usuarios tienen discapacidad visual o motriz o son adultos mayores. "
        "Para cualquier orden sobre la PC, la forma mas rapida es ejecutar_orden con la frase completa tal "
        "como la dijo (sirve aunque solo diga 'Word', 'pon cumbia' o 'abre Word y escribe hola'). "
        "Usa las demas herramientas solo si necesitas algo mas preciso. Nunca digas que no puedes si hay una herramienta. "
        "Si una herramienta devuelve 'decir', usa ese texto como respuesta. "
        "Para poner musica o videos usa reproducir_en_youtube. Para apagar, reiniciar, suspender o bloquear "
        "usa energia; antes de apagar, reiniciar o cerrar sesion pregunta si esta seguro. "
        "Acepta cualquier forma de pedir: sinonimos, errores de pronunciacion y ordenes indirectas "
        "('no escucho nada' = subir volumen, 'no veo bien las letras' = abrir la lupa). "
        "Pasa a la herramienta las palabras del usuario: la app entiende 'mas fuerte', 'la calcu' o 'block de notas'. "
        "No pidas que usen el raton ni que miren la pantalla; si no ven bien, usa leer_pantalla y diles que hay. "
        "Responde en espanol con una frase corta."
    ),
)


# ------------------------------------------------------------ abrir cosas

@servidor.tool()
def abrir_aplicacion(nombre: str) -> dict:
    """Abre una aplicacion instalada en la computadora Windows del usuario.
    Ejemplos: 'abre Word', 'la calcu', 'ejecuta Excel', 'el navegador', 'block de notas'.
    Accesibilidad: 'lupa' (agranda la pantalla), 'narrador' (lee la pantalla), 'teclado en pantalla'.
    nombre: el nombre de la aplicacion tal como lo dijo."""
    resultado = aw.abrir_aplicacion(nombre)
    if resultado.get("exito"):
        time.sleep(0.5)  # da tiempo a que la ventana aparezca antes de la siguiente orden
        resultado["decir"] = f"Listo, abri {resultado.get('abierta', nombre)}."
    return resultado


@servidor.tool()
def listar_aplicaciones(filtro: str = "") -> dict:
    """Lista las aplicaciones instaladas. Usala si abrir_aplicacion no encontro una aplicacion,
    o si el usuario pregunta que programas tiene. filtro: texto para filtrar (opcional)."""
    return aw.listar_aplicaciones(filtro)


@servidor.tool()
def abrir_pagina_web(direccion: str, navegador: str = "") -> dict:
    """Abre una pagina web. direccion: una URL, un dominio (github.com) o un sitio conocido
    (YouTube, Gmail, Google Drive, WhatsApp, Netflix...). navegador: 'Brave', 'Chrome', 'Edge' o
    'Firefox' si lo pidio; vacio = el que eligio el usuario o el predeterminado de Windows."""
    return aw.abrir_pagina_web(direccion, navegador=navegador)


@servidor.tool()
def buscar_en_internet(consulta: str) -> dict:
    """Busca algo en Google y abre los resultados en el navegador."""
    return aw.buscar_en_internet(consulta)


@servidor.tool()
def reproducir_en_youtube(consulta: str) -> dict:
    """Busca en YouTube y REPRODUCE directamente el primer video encontrado.
    Usala para 'pon musica de Grupo 5', 'reproduce la cancion ...', 'pon un video de ...'.
    Si YouTube ya esta abierto, cambia de video en la MISMA pestana (no abre otra).
    consulta: artista, cancion o tema, por ejemplo 'Grupo 5 mix'."""
    resultado = cw.reproducir_en_youtube(consulta, abrir=ac.abrir_reutilizando)
    if resultado.get("reproduciendo"):
        resultado["decir"] = f"Listo, puse {consulta}."
    return resultado


@servidor.tool()
def buscar_en_youtube(consulta: str) -> dict:
    """Muestra la lista de resultados de YouTube sin reproducir nada.
    Usala solo si el usuario quiere ver opciones; para poner musica usa reproducir_en_youtube."""
    return aw.buscar_en_youtube(consulta, abrir=ac.abrir_reutilizando)


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
    'subir volumen', 'bajar volumen' o 'silenciar'. Tambien entiende 'mas fuerte', 'bajale',
    'esta muy alto', 'pasa a la otra', 'quita el sonido'.
    veces: cuantas pulsaciones (opcional). Cada pulsacion de volumen cambia ~2 %;
    si no se indica, el volumen cambia ~10 %."""
    resultado = cw.controlar_multimedia(accion, veces)
    if resultado.get("exito"):
        resultado["decir"] = "Listo."
    return resultado


# ------------------------------------------------------------ teclado

@servidor.tool()
def presionar_teclas(teclas: str, veces: int = 1) -> dict:
    """Presiona una tecla o un atajo de teclado en la ventana que esta al frente.
    teclas: una tecla o combinacion con '+'. Ejemplos:
    'ctrl+t' (nueva pestana), 'ctrl+w' (cerrar pestana), 'ctrl+tab' (siguiente pestana),
    'alt+tab' (cambiar de ventana), 'win+d' (mostrar escritorio), 'f' (pantalla completa en YouTube),
    'espacio' (pausar en YouTube), 'abajo' o 'avpag' (bajar), 'arriba' o 'repag' (subir),
    'ctrl+c', 'ctrl+v', 'ctrl+z', 'ctrl+s', 'enter', 'esc', 'f5' (recargar), 'win' (menu Inicio).
    Tambien acepta el NOMBRE de la accion, sin saber el atajo: 'copiar', 'pegar', 'guardar',
    'seleccionar todo', 'negrita', 'nueva pestana', 'cerrar pestana', 'atras', 'acercar', 'minimizar'.
    veces: cuantas veces repetirla (por ejemplo 5 para bajar varias lineas)."""
    return ac.presionar_por_nombre(teclas, veces)


@servidor.tool()
def escribir_texto(texto: str, presionar_enter: bool = False, aplicacion: str = "") -> dict:
    """Escribe texto como si se tecleara (dictado).
    aplicacion: donde escribir, por ejemplo 'Word' o 'Bloc de notas'; si no esta abierta la abre
    (Word con un documento en blanco) y espera a que este lista. Vacio = la ventana al frente.
    presionar_enter: true para pulsar Enter al final (por ejemplo para enviar o buscar).
    Por seguridad no escribe en terminales ni en VS Code."""
    return ac.escribir_en(texto, aplicacion, presionar_enter)


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
    almacenamiento, mouse, notificaciones, impresoras, configuracion (inicio) y accesibilidad:
    lupa, narrador, texto grande, alto contraste o puntero del mouse."""
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


# ------------------------------------------------------------ orden libre, mouse y pantalla

@servidor.tool()
def ejecutar_orden(frase: str) -> dict:
    """La forma mas rapida de cumplir cualquier orden sobre la PC: pasa la frase COMPLETA del usuario
    tal como la dijo y la app la entiende y la ejecuta. Sirve con una sola palabra ('Word', 'YouTube'),
    con ordenes compuestas ('abre Word y escribe hola') y con cualquier forma de decirlo:
    'pon Despacito', 'otra cancion', 'mas fuerte', 'guardalo', 'haz clic en Aceptar', 'baja la pagina',
    'busca el clima en Cusco', 'pon las letras grandes', 'cierra Word'.
    Para apagar o reiniciar devuelve que hay que confirmar con la herramienta energia."""
    return ac.ejecutar_orden(frase)


@servidor.tool()
def hacer_clic_en(nombre: str, tipo_clic: str = "normal") -> dict:
    """Hace clic en un boton, menu, pestana, enlace u opcion de la ventana al frente, buscandolo por
    el nombre que se ve en pantalla (por ejemplo 'Guardar', 'Archivo', 'Documento en blanco', 'Aceptar').
    tipo_clic: 'normal', 'doble' o 'derecho'. Si no lo encuentra, devuelve las opciones visibles."""
    return ac.hacer_clic_en(nombre, tipo_clic)


@servidor.tool()
def usar_mouse(accion: str, direccion: str = "", cantidad: int = 0) -> dict:
    """Usa el mouse como lo haria la persona: 'clic', 'doble clic', 'clic derecho' donde esta el puntero,
    'mover' el puntero (direccion arriba, abajo, izquierda o derecha; cantidad en pixeles),
    'desplazar' con la rueda (cantidad = pasos) o llevar el puntero al 'centro' de la ventana."""
    return ac.usar_mouse(accion, direccion, cantidad)


@servidor.tool()
def leer_pantalla() -> dict:
    """Dice que ventana esta al frente, el texto donde esta el cursor y los botones u opciones que
    se ven, para contarselos en voz alta a una persona que no ve bien la pantalla."""
    return ac.leer_pantalla()


if __name__ == "__main__":
    # Lee el menu Inicio en segundo plano para que la primera orden 'abre ...' sea rapida.
    threading.Thread(target=aw.leer_apps_inicio, daemon=True).start()
    servidor.run(transport="stdio")
