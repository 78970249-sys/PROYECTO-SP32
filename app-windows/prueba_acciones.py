"""Pruebas de la orden libre, el mouse, los atajos por nombre y el clic por nombre (sin Windows)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acciones_windows as ac  # noqa: E402

fallos = total = 0


def revisar(ok, texto):
    global fallos, total
    total += 1
    fallos += not ok
    print(("OK  " if ok else "MAL ") + texto)


def ruta(frase):
    return [(h, a) for h, a in ac.interpretar_orden(frase)]


# --------------------------------------------- orden libre: (frase, herramienta, argumento clave)
CASOS = [
    # una sola palabra o un nombre
    ("Word", "abrir", {"nombre": "word"}),
    ("YouTube", "abrir", {"nombre": "youtube"}),
    ("la calculadora", "abrir", {"nombre": "calculadora"}),
    ("KusiVox, Excel por favor", "abrir", {"nombre": "excel"}),
    ("abre el navegador", "abrir", {"nombre": "navegador"}),
    ("quiero usar Paint", "abrir", {"nombre": "paint"}),
    ("dame la lupa", "abrir", {"nombre": "lupa"}),
    ("facebook", "abrir", {"nombre": "facebook"}),
    # musica y videos
    ("pon Despacito", "reproducir_en_youtube", {"consulta": "despacito"}),
    ("ponme música de Grupo 5", "reproducir_en_youtube", {"consulta": "musica de grupo 5"}),
    ("quiero escuchar cumbia", "reproducir_en_youtube", {"consulta": "cumbia"}),
    ("reproduce videos de gatos en YouTube", "reproducir_en_youtube", {"consulta": "videos de gatos"}),
    ("toca algo de salsa", "reproducir_en_youtube", {"consulta": "salsa"}),
    ("abre YouTube y pon a Shakira", "reproducir_en_youtube", {"consulta": "a shakira"}),
    # controlar lo que suena
    ("pausa", "controlar_multimedia", None),
    ("ponle pausa", "controlar_multimedia", None),
    ("pon la siguiente", "controlar_multimedia", None),
    ("otra canción", "controlar_multimedia", None),
    ("más fuerte", "controlar_multimedia", None),
    ("súbele el volumen a la música", "controlar_multimedia", None),
    ("está muy alto", "controlar_multimedia", None),
    ("no escucho nada", "controlar_multimedia", None),
    ("silencio", "controlar_multimedia", None),
    # escribir
    ("abre Word y escribe hola mundo", "escribir_en", {"texto": "hola mundo", "aplicacion": "word"}),
    ("escribe buenos días en el bloc de notas", "escribir_en", {"texto": "buenos dias", "aplicacion": "bloc de notas"}),
    ("dicta querida mamá te quiero", "escribir_en", {"texto": "querida mama te quiero", "aplicacion": ""}),
    ("abre Word y pon mi nombre es Ana", "escribir_en", {"texto": "mi nombre es ana", "aplicacion": "word"}),
    ("escribe hola en Word", "escribir_en", {"texto": "hola", "aplicacion": "word"}),
    # clic y mouse
    ("haz clic en Guardar", "hacer_clic_en", {"nombre": "guardar", "tipo_clic": "normal"}),
    ("dale clic al botón aceptar", "hacer_clic_en", None),
    ("doble clic en la carpeta fotos", "hacer_clic_en", {"tipo_clic": "doble"}),
    ("clic derecho en el escritorio", "hacer_clic_en", {"tipo_clic": "derecho"}),
    ("presiona el botón Imprimir", "hacer_clic_en", {"nombre": "imprimir"}),
    ("selecciona la opción negrita", "presionar_teclas", {"teclas": "negrita"}),
    ("pulsa Aceptar", "presionar_teclas", {"teclas": "aceptar"}),
    ("elige Documento en blanco", "hacer_clic_en", {"nombre": "documento en blanco"}),
    ("haz clic", "usar_mouse", None),
    ("mueve el mouse a la derecha", "usar_mouse", None),
    ("desplázate hacia abajo", "usar_mouse", None),
    # atajos por nombre
    ("guárdalo", "presionar_teclas", {"teclas": "guardar"}),
    ("copia esto", "presionar_teclas", {"teclas": "copiar"}),
    ("pega", "presionar_teclas", {"teclas": "pegar"}),
    ("selecciona todo", "presionar_teclas", {"teclas": "seleccionar todo"}),
    ("presiona enter", "presionar_teclas", {"teclas": "aceptar"}),
    ("abre una pestaña nueva", "presionar_teclas", {"teclas": "nueva pestana"}),
    ("cierra la pestaña", "presionar_teclas", {"teclas": "cerrar pestana"}),
    ("deshaz", "presionar_teclas", {"teclas": "deshacer"}),
    ("ponlo en negrita", "presionar_teclas", {"teclas": "negrita"}),
    ("agranda la página", "presionar_teclas", {"teclas": "acercar"}),
    ("regresa a la página anterior", "presionar_teclas", {"teclas": "atras"}),
    # buscar
    ("busca el clima en Cusco", "buscar_en_internet", {"consulta": "el clima en cusco"}),
    ("busca recetas de cuy en YouTube", "buscar_en_youtube", {"consulta": "recetas de cuy"}),
    # sistema y ventanas
    ("bloquea la computadora", "energia", {"accion": "bloquear"}),
    ("a dormir", "energia", {"accion": "suspender"}),
    ("cancela el apagado", "energia", {"accion": "cancelar"}),
    ("apágate", "energia", {"accion": "apagar"}),
    ("pon las letras grandes", "abrir_configuracion", None),
    ("cambia a Chrome", "cambiar_a_ventana", {"nombre": "chrome"}),
    ("cierra Word", "cerrar_aplicacion", {"nombre": "word"}),
    ("cierra esto", "cerrar_ventana_activa", {}),
    ("abre mis descargas", "abrir_carpeta", {"nombre": "mis descargas"}),
    ("abre la carpeta de documentos", "abrir_carpeta", None),
    # navegadores
    ("usa Brave como navegador", "elegir_navegador", {"texto": "brave"}),
    ("cambia el navegador a Chrome", "elegir_navegador", {"texto": "chrome"}),
    ("abre YouTube en Brave", "abrir", {"nombre": "youtube", "navegador": "brave"}),
    ("busca el clima en Cusco con Edge", "buscar_en_internet", {"consulta": "el clima en cusco", "navegador": "edge"}),
    ("Brave", "abrir", {"nombre": "brave"}),
    ("cambia a Brave", "cambiar_a_ventana", {"nombre": "brave"}),
]
for frase, herramienta, args in CASOS:
    pasos = ruta(frase)
    ultimo = pasos[-1] if pasos else ("", {})
    ok = ultimo[0] == herramienta and all(ultimo[1].get(k) == v for k, v in (args or {}).items())
    revisar(ok, f"orden {frase!r:42} -> {ultimo}")

# 'abre Word y escribe hola' es un solo paso (escribir_en ya abre Word)
revisar(len(ruta("abre Word y escribe hola")) == 1, "compuesta: abrir+escribir es un solo paso")
revisar([h for h, _ in ruta("pon cumbia y sube el volumen")] == ["reproducir_en_youtube", "controlar_multimedia"],
        "compuesta: musica y luego volumen")
revisar([h for h, _ in ruta("selecciona todo y copia")] == ["presionar_teclas", "presionar_teclas"],
        "compuesta: seleccionar todo y copiar")

# --------------------------------------------- ejecutar_orden con herramientas falsas
llamadas = []


def falsa(nombre):
    def f(**kw):
        llamadas.append((nombre, kw))
        return {"exito": True, "decir": f"hecho {nombre}"}
    return f


FALSAS = {k: falsa(k) for k in ac.HERRAMIENTAS}
r = ac.ejecutar_orden("abre Word y escribe hola mundo", hacer=FALSAS)
revisar(r["exito"] and llamadas == [("escribir_en", {"texto": "hola mundo", "aplicacion": "word"})],
        f"ejecutar: abre Word y escribe -> {llamadas}")
llamadas.clear()
r = ac.ejecutar_orden("apaga la computadora", hacer=FALSAS)
revisar(not r["exito"] and r["pasos"][0].get("requiere_confirmacion") and not llamadas,
        "ejecutar: apagar no se hace sin confirmar")
llamadas.clear()
r = ac.ejecutar_orden("Word", hacer=FALSAS)
revisar(r["exito"] and llamadas == [("abrir", {"nombre": "word"})] and r.get("decir"), "ejecutar: solo 'Word'")
revisar(not ac.ejecutar_orden("", hacer=FALSAS)["exito"], "ejecutar: frase vacia")

# abrir_lo_que_sea: app instalada o pagina web
APPS = [{"Name": "WhatsApp", "AppID": "wa"}, {"Name": "Word", "AppID": "w"}]
abiertas = []
ac.aw.abrir_pagina_web = (lambda d, abrir=None, _o=ac.aw.abrir_pagina_web: (abiertas.append(("web", d)) or {"exito": True}))
ac._abrir_app_y_esperar = lambda n: (abiertas.append(("app", n)) or {"exito": True})
ac.abrir_lo_que_sea("whatsapp", apps=APPS)
ac.abrir_lo_que_sea("facebook", apps=APPS)
ac.abrir_lo_que_sea("word", apps=APPS)
revisar(abiertas == [("app", "whatsapp"), ("web", "facebook"), ("app", "word")], f"abrir lo que sea -> {abiertas}")

# --------------------------------------------- elegir navegador (se guarda en un archivo)
import tempfile  # noqa: E402
ac.aw.ARCHIVO_NAVEGADOR = os.path.join(tempfile.mkdtemp(), "KusiVox", "navegador.txt")
r = ac.aw.elegir_navegador("Brave", ruta=lambda n: "C:/brave.exe")
revisar(r["exito"] and ac.aw.navegador_elegido() == "brave", f"elegir Brave: {r.get('decir')}")
r = ac.aw.elegir_navegador("netscape", ruta=lambda n: None)
revisar(not r["exito"], "elegir navegador desconocido")
r = ac.aw.elegir_navegador("firefox", ruta=lambda n: None)
revisar(not r["exito"] and ac.aw.navegador_elegido() == "brave", "no elige un navegador que no esta instalado")

# --------------------------------------------- atajos por nombre (Windows no esta en espanol aqui)
for frase, esperado in {"copiar": "ctrl+c", "guardalo": "ctrl+s", "nueva pestana": "ctrl+t",
                        "selecciona todo": "ctrl+a", "cierra esta pestana": "ctrl+w", "pantalla completa": "f11",
                        "mostrar escritorio": "win+d", "zoom": "ctrl+mas"}.items():
    a = ac.atajo_por_nombre(frase)
    revisar(a and a[1] == esperado, f"atajo {frase!r:22} -> {a}")
revisar(ac.atajo_por_nombre("hola que tal") is None, "atajo: no inventa")
enviados = []
r = ac.presionar_por_nombre("guardar", enviar=enviados.append)
revisar(r["exito"] and r.get("accion") == "guardar" and enviados, "presionar 'guardar' por nombre")
r = ac.presionar_por_nombre("win+r", enviar=enviados.append)
revisar(not r["exito"], "presionar: Win+R sigue bloqueado")

# --------------------------------------------- mouse
for frase, esperado in {"haz clic": {"tipo": "clic", "clic": "normal"},
                        "doble clic": {"tipo": "clic", "clic": "doble"},
                        "clic derecho": {"tipo": "clic", "clic": "derecho"},
                        "mueve el mouse a la derecha": {"tipo": "mover", "sentido": "derecha", "pixeles": 150},
                        "mueve el puntero un poco arriba": {"tipo": "mover", "sentido": "arriba", "pixeles": 60},
                        "baja": {"tipo": "rueda", "sentido": "abajo", "pasos": 5},
                        "sube mucho": {"tipo": "rueda", "sentido": "arriba", "pasos": 12},
                        "desplazate hacia abajo": {"tipo": "rueda", "sentido": "abajo", "pasos": 5},
                        "pon el mouse en el centro": {"tipo": "centro"}}.items():
    r = ac.interpretar_mouse(frase)
    revisar(r == esperado, f"mouse {frase!r:34} -> {r}")
revisar(ac.interpretar_mouse("haz un cafe")["tipo"] == "desconocido", "mouse: no inventa")

# --------------------------------------------- elegir el boton por su nombre
CANDIDATOS = [(1, "Guardar (Ctrl+G)", 50000), (2, "Guardar como", 50011), (3, "Archivo", 50011),
              (4, "Negrita (Ctrl+N)", 50000), (5, "Documento en blanco", 50007), (6, "Aceptar", 50000),
              (7, "Imprimir", 50000), (8, "Inicio", 50019)]
for dicho, esperado in {"guardar": 1, "el boton guardar": 1, "guardar como": 2, "archivo": 3, "negrita": 4,
                        "documento en blanco": 5, "aceptar": 6, "acepta": 6, "imprimir": 7,
                        "la pestana inicio": 8, "documento": 5}.items():
    e = ac.elegir_elemento(dicho, CANDIDATOS)
    revisar(e is not None and e[0] == esperado, f"elegir {dicho!r:22} -> {e[1] if e else None}")
revisar(ac.elegir_elemento("cancelar compra", CANDIDATOS) is None, "elegir: no hace clic en otra cosa")

print(f"\nTOTAL: {total}  FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
