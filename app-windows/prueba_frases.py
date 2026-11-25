"""Pruebas: KusiVox entiende distintas formas de pedir lo mismo."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apps_windows as aw
import control_windows as cw
import sistema_windows as sw

fallos = 0
total = 0


def revisar(ok, texto):
    global fallos, total
    total += 1
    fallos += not ok
    print(("OK  " if ok else "MAL ") + texto)


# ---------------- aplicaciones
APPS = [{"Name": n, "AppID": "id:" + n} for n in [
    "Google Chrome", "Microsoft Edge", "Word", "Excel", "PowerPoint", "Bloc de notas", "Calculadora",
    "Explorador de archivos", "WhatsApp", "Spotify", "Paint", "Lupa", "Narrador", "Teclado en pantalla",
    "Recortes", "Microsoft Store", "Outlook (new)", "Grabadora de sonido", "Zoom Workplace",
]]
casos = {
    "la calcu": "Calculadora", "puedes abrir la calculadora por favor": "Calculadora", "calculdora": "Calculadora",
    "block de notas": "Bloc de notas", "ejecuta el block": "Bloc de notas", "notepad": "Bloc de notas",
    "guord": "Word", "ejecuta word": "Word", "inicia excel": "Excel", "la hoja de cálculo": "Excel",
    "las diapositivas": "PowerPoint", "google": "Google Chrome", "entra a chrome": "Google Chrome",
    "el internet": "Google Chrome", "wasap": "WhatsApp", "guasap": "WhatsApp", "espotifai": "Spotify",
    "pain": "Paint", "la lupa": "Lupa", "activa el narrador": "Narrador",
    "el teclado en pantalla": "Teclado en pantalla", "teclado virtual": "Teclado en pantalla",
    "recortes": "Recortes", "la tienda": "Microsoft Store", "el correo": "Outlook (new)",
    "grabadora de voz": "Grabadora de sonido", "zoom": "Zoom Workplace",
}
for dicho, esperado in casos.items():
    lanzadas = []
    r = aw.abrir_aplicacion(dicho, apps=APPS, lanzar_appid=lanzadas.append, lanzar_directo=lanzadas.append)
    revisar(r.get("exito") and r.get("abierta") == esperado, f"app {dicho!r:40} -> {r.get('abierta')}")

# Sin estar en el menu Inicio: lupa, narrador y teclado se abren directo
for dicho, exe in {"lupa": "magnify.exe", "narrador": "narrator.exe", "teclado en pantalla": "osk.exe",
                   "calcu": "calc.exe"}.items():
    lanzadas = []
    r = aw.abrir_aplicacion(dicho, apps=[], lanzar_appid=lanzadas.append, lanzar_directo=lanzadas.append)
    revisar(r.get("exito") and lanzadas == [exe], f"directo {dicho!r:22} -> {lanzadas}")

# ---------------- web y carpetas
for dicho, url in {"yutub": "https://www.youtube.com", "la página de youtube": "https://www.youtube.com",
                   "el traductor": "https://translate.google.com", "hotmail": "https://outlook.live.com",
                   "abre facebook": "https://www.facebook.com", "insta": "https://www.instagram.com",
                   "github.com": "https://github.com"}.items():
    revisar(aw.url_para(dicho) == url, f"web {dicho!r:26} -> {aw.url_para(dicho)}")
revisar(aw.url_para("javascript:alert(1)").startswith("https://www.google.com/search"), "web: no abre esquemas raros")

for dicho, destino in {"mis descargas": "shell:Downloads", "abre la carpeta de descargas por favor": "shell:Downloads",
                       "las capturas de pantalla": "shell:Screenshots", "mis fotos": "shell:My Pictures",
                       "la papelera": "shell:RecycleBinFolder", "mi computadora": "shell:MyComputerFolder"}.items():
    lanzadas = []
    r = aw.abrir_carpeta(dicho, lanzar=lanzadas.append)
    revisar(r["exito"] and lanzadas == [destino], f"carpeta {dicho!r:42} -> {lanzadas}")

# ---------------- musica y volumen
SUBIR, BAJAR, MUTE, SIG, ANT, PLAY, STOP = 0xAF, 0xAE, 0xAD, 0xB0, 0xB1, 0xB3, 0xB2
for dicho, vk in {"más fuerte": SUBIR, "súbele": SUBIR, "sube un poco": SUBIR, "no escucho nada": SUBIR,
                  "aumenta el volumen": SUBIR, "bájale": BAJAR, "está muy fuerte": BAJAR, "más bajito": BAJAR,
                  "está muy alto": BAJAR, "más suave": BAJAR, "quita el sonido": MUTE, "silencio": MUTE,
                  "cállate": MUTE, "pasa a la otra": SIG, "la siguiente canción": SIG, "salta esta": SIG,
                  "la anterior": ANT, "regresa a la de antes": ANT, "pausa": PLAY, "para la música": PLAY,
                  "dale play": PLAY, "continúa": PLAY, "sigue": PLAY, "detén": STOP}.items():
    revisar(cw.accion_multimedia(dicho) == vk, f"multimedia {dicho!r:26} -> {cw.accion_multimedia(dicho)}")
revisar(cw.accion_multimedia("haz un café") is None, "multimedia: no inventa acciones")

# ---------------- ventanas
VENTANAS = [(1, "YouTube - Google Chrome"), (2, "Documento1 - Word"), (3, "Calculadora"),
            (4, "Sin título: Bloc de notas"), (5, "Descargas")]
for dicho, esperado in {"cambia a chrome": [1], "la ventana de Word": [2], "el navegador": [1], "la calcu": [3],
                        "block de notas": [4], "la música": [1], "pasa a descargas": [5]}.items():
    r = [h for h, _ in cw.buscar_ventanas(dicho, VENTANAS)]
    revisar(r == esperado, f"ventana {dicho!r:22} -> {r}")
revisar(cw.buscar_ventanas("excel", VENTANAS) == [], "ventana inexistente -> []")

# ---------------- energia (apagar siempre pide confirmacion)
for dicho, esperado in {"apágate": "apagar", "apaga el equipo": "apagar", "reiníciate": "reiniciar",
                        "ya no apagues": "cancelar", "no reinicies": "cancelar", "a dormir": "suspender",
                        "ponla en reposo": "suspender", "bloquéala": "bloquear", "salir de la sesión": "cerrar sesion",
                        "pantalla negra": "apagar pantalla"}.items():
    lanzados = []
    r = sw.energia(dicho, lanzar=lanzados.append, apagar_monitor=lambda: lanzados.append("monitor"))
    if esperado in sw.NECESITAN_CONFIRMAR:
        ok = r.get("requiere_confirmacion") and lanzados == []
    else:
        ok = r.get("exito") and lanzados != []
    revisar(bool(ok), f"energia {dicho!r:22} -> {r.get('accion', r.get('mensaje', '')[:40])}")

# ---------------- configuracion
for dicho, destino in {"accesibilidad": "ms-settings:easeofaccess", "pon las letras grandes": "ms-settings:easeofaccess-display",
                       "el alto contraste": "ms-settings:easeofaccess-highcontrast", "los audífonos": "ms-settings:sound",
                       "configuración del wifi": "ms-settings:network-wifi", "la pantalla de bloqueo": "ms-settings:lockscreen",
                       "brillo de la pantalla": "ms-settings:display", "el puntero del mouse": "ms-settings:easeofaccess-mousepointer"}.items():
    abiertos = []
    r = sw.abrir_configuracion(dicho, abrir=abiertos.append)
    revisar(r["exito"] and abiertos == [destino], f"config {dicho!r:30} -> {abiertos}")

# ---------------- cerrar aplicaciones (sigue protegiendo terminales y VS Code)
VENT = [(1, "YouTube - Google Chrome"), (2, "Documento1 - Word"), (3, "Windows PowerShell"),
        (4, "escritorio.py - Visual Studio Code")]
for dicho, esperado in {"cierra el navegador": [1], "cierra word": [2], "la ventana de chrome": [1]}.items():
    cerradas = []
    sw.cerrar_aplicacion(dicho, ventanas=VENT, cerrar=cerradas.append)
    revisar(cerradas == esperado, f"cerrar {dicho!r:24} -> {cerradas}")
cerradas = []
r = sw.cerrar_aplicacion("powershell", ventanas=VENT, cerrar=cerradas.append)
revisar(cerradas == [] and not r["exito"], "cerrar: no cierra PowerShell")
cerradas = []
r = sw.cerrar_aplicacion("visual studio code", ventanas=VENT, cerrar=cerradas.append)
revisar(cerradas == [] and not r["exito"], "cerrar: no cierra VS Code")

# Los atajos peligrosos siguen bloqueados
for combo in ("win+r", "win+x"):
    r = cw.presionar_teclas(combo, enviar=lambda e: None)
    revisar(not r["exito"], f"bloqueado {combo}")

print(f"\nTOTAL: {total}  FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
