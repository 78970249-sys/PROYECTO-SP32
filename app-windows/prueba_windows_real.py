"""Prueba en un Windows real (GitHub Actions): abrir y escribir en el Bloc de notas, leer la pantalla,
atajos por nombre, clic por nombre, mouse y YouTube en la misma pestana."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acciones_windows as ac  # noqa: E402
import control_windows as cw  # noqa: E402

fallos = total = 0


def revisar(ok, texto, obligatoria=True):
    global fallos, total
    total += 1
    if not ok and obligatoria:
        fallos += 1
    print(("OK   " if ok else ("MAL  " if obligatoria else "AVISO ")) + texto, flush=True)


r = ac.escribir_en("Hola KusiVox 123", "bloc de notas")
revisar(r.get("exito"), f"abrir el Bloc de notas y escribir: {r}")
time.sleep(1.0)

p = ac.leer_pantalla()
texto = p.get("enfocado", {}).get("texto", "")
revisar("Hola KusiVox 123" in texto, f"leer_pantalla lee lo escrito: ventana={p.get('ventana')!r} texto={texto[:60]!r}")
opciones = p.get("opciones_visibles", [])
revisar(len(opciones) > 0, f"leer_pantalla ve opciones: {opciones[:12]}")

r = ac.presionar_por_nombre("seleccionar todo")
revisar(r.get("exito"), f"atajo por nombre 'seleccionar todo': {r}")
r = ac.escribir_en("Texto nuevo")
time.sleep(0.5)
texto = ac.leer_pantalla().get("enfocado", {}).get("texto", "")
revisar(texto.strip() == "Texto nuevo", f"seleccionar todo + escribir reemplaza el texto: {texto!r}")

menu = next((n for n in ("File", "Archivo", "Edit", "Editar") if n in opciones), "File")
r = ac.hacer_clic_en(menu)
revisar(r.get("exito"), f"hacer_clic_en({menu!r}): {r}")
time.sleep(0.5)
cw.presionar_teclas("esc")
r = ac.hacer_clic_en("boton que no existe")
revisar(not r.get("exito") and r.get("opciones_visibles"), f"clic en algo inexistente devuelve opciones: {str(r)[:120]}")

x, y = ac.posicion_mouse()
r = ac.usar_mouse("mover", "derecha", 100)
x2, y2 = ac.posicion_mouse()
revisar(r.get("exito") and x2 != x, f"mover el mouse: ({x},{y}) -> ({x2},{y2})")
r = ac.usar_mouse("centro")
revisar(r.get("exito"), f"mouse al centro: {r}")
r = ac.usar_mouse("desplazar", "abajo", 3)
revisar(r.get("exito"), f"rueda del mouse: {r}")

r = ac.ejecutar_orden("abre la calculadora")
revisar(r.get("exito"), f"orden libre 'abre la calculadora': {str(r)[:160]}", obligatoria=False)

# YouTube en la misma pestana (informativa: depende de Chrome y de la red del servidor de pruebas)
ac.abrir_reutilizando("https://www.youtube.com/watch?v=jNQXAC9IVRw")
time.sleep(12)
def ventanas_youtube():
    return [t for _, t in cw.listar_ventanas() if "youtube" in t.lower()]


antes = ventanas_youtube()
reutilizo = ac.navegar_en_pestana("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
time.sleep(6)
despues = ventanas_youtube()
revisar(reutilizo and len(antes) == 1 and len(despues) == 1, f"YouTube en la misma pestana: antes={antes} despues={despues}",
        obligatoria=False)

print(f"\nTOTAL: {total}  FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
