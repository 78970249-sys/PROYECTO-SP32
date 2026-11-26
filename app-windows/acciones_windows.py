"""
Acciones extra de KusiVox para que una persona maneje toda la PC con la voz:

- usar_mouse: clic, doble clic, clic derecho, mover el puntero y desplazar con la rueda.
- hacer_clic_en: hace clic en un boton, menu, enlace o pestana por su nombre (UI Automation).
- leer_pantalla: dice que ventana esta al frente, que texto tiene el foco y que botones hay.
- atajo_por_nombre: 'copiar', 'guardar', 'nueva pestana', 'negrita'... sin saber el atajo.
- preparar_aplicacion: abre (o trae al frente) una aplicacion y espera a que este lista para escribir.
- navegar_en_pestana: reutiliza la pestana de YouTube abierta en vez de abrir otra.
- ejecutar_orden: entiende una orden libre, completa o de una sola palabra ('Word', 'pon cumbia',
  'abre Word y escribe hola') y la reparte entre las demas herramientas.
"""

import ctypes
import difflib
import logging
import re
import time
import urllib.parse

import apps_windows as aw
import control_windows as cw
import sistema_windows as sw

log = logging.getLogger("escritorio")

ES_WINDOWS = cw.ES_WINDOWS
LONG = ctypes.c_int32
normalizar = cw.normalizar


class POINT(ctypes.Structure):
    _fields_ = [("x", LONG), ("y", LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", LONG), ("top", LONG), ("right", LONG), ("bottom", LONG)]


user32 = cw.user32
if ES_WINDOWS:
    user32.GetCursorPos.argtypes = (ctypes.POINTER(POINT),)
    user32.SetCursorPos.argtypes = (ctypes.c_int, ctypes.c_int)
    user32.WindowFromPoint.argtypes = (POINT,)
    user32.WindowFromPoint.restype = cw.HWND
    user32.GetAncestor.argtypes = (cw.HWND, ctypes.c_uint)
    user32.GetAncestor.restype = cw.HWND
    user32.GetWindowRect.argtypes = (cw.HWND, ctypes.POINTER(RECT))
    user32.GetSystemMetrics.argtypes = (ctypes.c_int,)
    shell32 = ctypes.WinDLL("shell32")
    shell32.ShellExecuteW.argtypes = (cw.HWND, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                                      ctypes.c_wchar_p, ctypes.c_int)
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    kernel32 = ctypes.WinDLL("kernel32")
else:
    shell32 = kernel32 = None

PROTEGIDO = "Por seguridad no actuo sobre terminales, PowerShell, la ventana Ejecutar ni VS Code."


# ================================================================ ventanas

def enfocar(hwnd) -> bool:
    """Trae una ventana al frente y confirma que quedo activa."""
    if not ES_WINDOWS:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    cw._enviar([cw._evento(0x12, 0, 0), cw._evento(0x12, 0, cw.KEYEVENTF_KEYUP)])  # Alt libera el foco
    user32.SetForegroundWindow(hwnd)
    for _ in range(10):
        if user32.GetForegroundWindow() == hwnd:
            return True
        time.sleep(0.05)
    return user32.GetForegroundWindow() == hwnd


def ventana_activa_protegida() -> bool:
    activa = cw.ventana_activa()
    return cw.es_ventana_prohibida(activa["titulo"], activa["clase"])


# ================================================================ atajos por nombre

# accion -> (atajo general, atajo en Office en espanol). Office en espanol cambia varios atajos
# (Ctrl+G guarda, Ctrl+N es negrita...), asi que se elige segun la ventana que esta al frente.
ATAJOS = {
    "copiar": ("ctrl+c", None), "pegar": ("ctrl+v", None), "cortar": ("ctrl+x", None),
    "deshacer": ("ctrl+z", None), "rehacer": ("ctrl+y", None),
    "seleccionar todo": ("ctrl+a", "ctrl+e"), "guardar": ("ctrl+s", "shift+f12"),
    "buscar en la pagina": ("ctrl+f", "ctrl+b"), "imprimir": ("ctrl+p", None),
    "nuevo documento": ("ctrl+n", "ctrl+u"), "negrita": ("ctrl+b", "ctrl+n"),
    "cursiva": ("ctrl+i", "ctrl+k"), "subrayado": ("ctrl+u", "ctrl+s"),
    "nueva pestana": ("ctrl+t", None), "cerrar pestana": ("ctrl+w", None),
    "reabrir pestana": ("ctrl+shift+t", None), "siguiente pestana": ("ctrl+tab", None),
    "pestana anterior": ("ctrl+shift+tab", None), "recargar": ("f5", None),
    "pantalla completa": ("f11", None), "acercar": ("ctrl+mas", None), "alejar": ("ctrl+menos", None),
    "tamano normal": ("ctrl+0", None), "atras": ("alt+izquierda", None), "adelante": ("alt+derecha", None),
    "aceptar": ("enter", None), "cancelar": ("esc", None), "siguiente campo": ("tab", None),
    "campo anterior": ("shift+tab", None), "borrar": ("retroceso", None), "suprimir": ("suprimir", None),
    "ir al inicio": ("ctrl+home", None), "ir al final": ("ctrl+fin", None),
    "bajar": ("avpag", None), "subir": ("repag", None),
    "minimizar": ("win+abajo", None), "maximizar": ("win+arriba", None),
    "mostrar escritorio": ("win+d", None), "cambiar de ventana": ("alt+tab", None),
    "menu contextual": ("shift+f10", None), "menu inicio": ("win", None),
}

# Formas de decir cada accion (se buscan dentro de la frase; la mas larga gana).
SINONIMOS_ATAJOS = {
    "copia": "copiar", "copialo": "copiar", "pega": "pegar", "pegalo": "pegar", "corta": "cortar",
    "deshaz": "deshacer", "regresa lo que hice": "deshacer", "rehaz": "rehacer",
    "selecciona todo": "seleccionar todo", "marca todo": "seleccionar todo", "seleccionalo todo": "seleccionar todo",
    "guarda": "guardar", "guardalo": "guardar", "graba el archivo": "guardar",
    "busca en la pagina": "buscar en la pagina", "buscar en el documento": "buscar en la pagina",
    "imprime": "imprimir", "nuevo archivo": "nuevo documento", "documento nuevo": "nuevo documento",
    "en negrita": "negrita", "en cursiva": "cursiva", "subraya": "subrayado", "subrayalo": "subrayado",
    "abre una pestana": "nueva pestana", "otra pestana": "nueva pestana", "cierra la pestana": "cerrar pestana",
    "cierra esta pestana": "cerrar pestana", "la siguiente pestana": "siguiente pestana",
    "actualiza": "recargar", "recarga": "recargar", "refresca": "recargar",
    "agranda": "acercar", "mas grande": "acercar", "zoom": "acercar", "achica": "alejar", "mas pequeno": "alejar",
    "regresa a la pagina anterior": "atras", "vuelve atras": "atras", "pagina anterior": "atras",
    "pagina siguiente": "adelante", "da enter": "aceptar", "presiona enter": "aceptar", "enter": "aceptar",
    "escape": "cancelar", "borra": "borrar", "baja la pagina": "bajar", "baja un poco": "bajar",
    "sube la pagina": "subir", "minimiza": "minimizar", "maximiza": "maximizar",
    "ve al escritorio": "mostrar escritorio", "el escritorio": "mostrar escritorio",
    "abre el menu inicio": "menu inicio", "abre inicio": "menu inicio",
}


def _office_en_espanol() -> bool:
    """True si la ventana al frente es Word/Excel/PowerPoint y Windows esta en espanol."""
    titulo = normalizar(cw.ventana_activa()["titulo"])
    if not re.search(r"(?:^| - )(?:word|excel|powerpoint)$", titulo):
        return False
    try:
        return (kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0A
    except Exception:
        return False


def atajo_por_nombre(frase: str):
    """'guardalo' -> ('guardar', 'ctrl+s') o None si la frase no nombra una accion conocida."""
    clave = normalizar(frase)
    if clave in ATAJOS:
        accion = clave
    elif clave in SINONIMOS_ATAJOS:
        accion = SINONIMOS_ATAJOS[clave]
    else:
        accion = None
        todas = {**{k: k for k in ATAJOS}, **SINONIMOS_ATAJOS}
        for k in sorted(todas, key=len, reverse=True):
            if len(k) > 3 and re.search(r"\b" + re.escape(k) + r"\b", clave):
                accion = todas[k]
                break
    if not accion:
        return None
    general, office = ATAJOS[accion]
    return accion, (office if office and _office_en_espanol() else general)


# ================================================================ mouse

INPUT_MOUSE = 0
MOUSE_IZQ_ABAJO, MOUSE_IZQ_ARRIBA = 0x0002, 0x0004
MOUSE_DER_ABAJO, MOUSE_DER_ARRIBA = 0x0008, 0x0010
MOUSE_RUEDA, MOUSE_RUEDA_H = 0x0800, 0x1000


def _evento_mouse(flags: int, datos: int = 0):
    entrada = cw.INPUT(type=INPUT_MOUSE)
    entrada.mi = cw.MOUSEINPUT(dx=0, dy=0, mouseData=datos & 0xFFFFFFFF, dwFlags=flags, time=0, dwExtraInfo=0)
    return entrada


def posicion_mouse():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _ventana_bajo_mouse() -> dict:
    x, y = posicion_mouse()
    hwnd = user32.GetAncestor(user32.WindowFromPoint(POINT(x, y)), 2)  # GA_ROOT
    return {"titulo": cw._titulo(hwnd), "clase": cw._clase(hwnd)} if hwnd else {"titulo": "", "clase": ""}


def _clic(tipo: str = "normal") -> None:
    if tipo == "derecho":
        cw._enviar([_evento_mouse(MOUSE_DER_ABAJO), _evento_mouse(MOUSE_DER_ARRIBA)])
        return
    veces = 2 if tipo == "doble" else 1
    for _ in range(veces):
        cw._enviar([_evento_mouse(MOUSE_IZQ_ABAJO), _evento_mouse(MOUSE_IZQ_ARRIBA)])
        time.sleep(0.05)


def interpretar_mouse(accion: str, direccion: str = "", cantidad: int = 0) -> dict:
    """Traduce lo que pidio la persona a una orden de mouse (sin ejecutarla).
    Devuelve {'tipo': 'clic'|'mover'|'rueda'|'centro', ...}."""
    texto = normalizar(f"{accion} {direccion}")
    cantidad = int(cantidad or 0)
    if "un poco" in texto or "poquito" in texto:
        factor = 0.4
    elif "mucho" in texto or "bastante" in texto:
        factor = 2.5
    else:
        factor = 1.0
    if re.search(r"\b(clic|click|cliquea|pulsa|presiona|aprieta|selecciona)", texto):
        tipo = "doble" if "doble" in texto else "derecho" if "derech" in texto else "normal"
        return {"tipo": "clic", "clic": tipo}
    if "centro" in texto or "medio" in texto:
        return {"tipo": "centro"}
    sentido = ("arriba" if re.search(r"\b(arriba|sube|subir|subelo)", texto) else
               "abajo" if re.search(r"\b(abajo|baja|bajar|bajalo)", texto) else
               "izquierda" if "izquierd" in texto else "derecha" if "derech" in texto else "")
    if re.search(r"\b(desplaz|scroll|rueda|baja|bajar|sube|subir)", texto) and not re.search(r"\b(mueve|mover|lleva|puntero|cursor)", texto):
        pasos = max(1, min(int((cantidad or 5) * factor), 50))
        return {"tipo": "rueda", "sentido": sentido or "abajo", "pasos": pasos}
    if sentido:
        pixeles = max(10, min(int((cantidad or 150) * factor), 2000))
        return {"tipo": "mover", "sentido": sentido, "pixeles": pixeles}
    return {"tipo": "desconocido"}


def usar_mouse(accion: str, direccion: str = "", cantidad: int = 0) -> dict:
    orden = interpretar_mouse(accion, direccion, cantidad)
    if orden["tipo"] == "desconocido":
        return {"exito": False, "mensaje": "No entendi que hacer con el mouse. Puedo hacer clic, doble clic, "
                                           "clic derecho, mover el puntero o desplazar hacia arriba o abajo."}
    if not ES_WINDOWS:
        return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
    if orden["tipo"] == "clic":
        bajo = _ventana_bajo_mouse()
        if cw.es_ventana_prohibida(bajo["titulo"], bajo["clase"]):
            return {"exito": False, "mensaje": PROTEGIDO}
        _clic(orden["clic"])
        nombre = {"normal": "clic", "doble": "doble clic", "derecho": "clic derecho"}[orden["clic"]]
        return {"exito": True, "accion": nombre, "decir": f"Listo, hice {nombre}."}
    if orden["tipo"] == "centro":
        r = RECT()
        user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(r))
        user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
        return {"exito": True, "decir": "Puse el puntero en el centro de la ventana."}
    if orden["tipo"] == "rueda":
        horizontal = orden["sentido"] in ("izquierda", "derecha")
        delta = 120 * orden["pasos"] * (1 if orden["sentido"] in ("arriba", "derecha") else -1)
        cw._enviar([_evento_mouse(MOUSE_RUEDA_H if horizontal else MOUSE_RUEDA, delta)])
        return {"exito": True, "decir": f"Desplace hacia {orden['sentido']}."}
    x, y = posicion_mouse()
    dx = {"izquierda": -1, "derecha": 1}.get(orden["sentido"], 0) * orden["pixeles"]
    dy = {"arriba": -1, "abajo": 1}.get(orden["sentido"], 0) * orden["pixeles"]
    ancho, alto = user32.GetSystemMetrics(78) or 1920, user32.GetSystemMetrics(79) or 1080  # pantalla virtual
    user32.SetCursorPos(max(0, min(x + dx, ancho - 1)), max(0, min(y + dy, alto - 1)))
    return {"exito": True, "decir": f"Movi el puntero hacia {orden['sentido']}."}


# ================================================================ UI Automation (clic por nombre)

TIPOS_CLIC = {50000: "boton", 50031: "boton", 50011: "menu", 50005: "enlace", 50019: "pestana",
              50007: "elemento", 50002: "casilla", 50013: "opcion", 50003: "lista", 50024: "elemento",
              50004: "campo de texto", 50030: "documento"}
PALABRAS_TIPO = r"\b(?:el|la|los|las|boton|botoncito|menu|opcion|enlace|link|pestana|casilla|icono|la palabra|que dice|donde dice)\b"


def _uia():
    """Objeto IUIAutomation para el hilo actual."""
    import comtypes
    import comtypes.client
    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    try:
        from comtypes.gen import UIAutomationClient as U
    except ImportError:
        U = comtypes.client.GetModule("UIAutomationCore.dll")
    aut = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    return U, aut


def _limpiar_nombre(nombre: str) -> str:
    """'Negrita (Ctrl+N)' -> 'negrita'; quita atajos y simbolos que no se pronuncian."""
    nombre = re.sub(r"\(.*?\)|\[.*?\]", " ", nombre or "")
    return normalizar(re.sub(r"[^\w\s]", " ", nombre))


def elegir_elemento(buscado: str, candidatos: list):
    """Elige el candidato (obj, nombre, tipo) cuyo nombre mejor coincide con lo dicho, o None."""
    objetivo = normalizar(re.sub(PALABRAS_TIPO, " ", normalizar(buscado)))
    objetivo = " ".join(objetivo.split())
    if not objetivo:
        return None
    mejor, puntaje_mejor = None, 0.0
    for cand in candidatos:
        nombre = _limpiar_nombre(cand[1])
        if not nombre:
            continue
        if nombre == objetivo:
            puntaje = 100
        elif nombre.startswith(objetivo + " ") or nombre.startswith(objetivo):
            puntaje = 90 - min(len(nombre) - len(objetivo), 30) * 0.2
        elif re.search(r"\b" + re.escape(objetivo) + r"\b", nombre):
            puntaje = 80 - min(len(nombre) - len(objetivo), 40) * 0.2
        elif re.search(r"\b" + re.escape(nombre) + r"\b", objetivo) and len(nombre) > 2:
            puntaje = 70
        else:
            parecido = difflib.SequenceMatcher(None, nombre, objetivo).ratio()
            puntaje = parecido * 70 if parecido >= 0.78 else 0
        if puntaje and cand[2] in (50000, 50031, 50011):
            puntaje += 2  # a igualdad, preferir botones y menus
        if puntaje > puntaje_mejor:
            mejor, puntaje_mejor = cand, puntaje
    return mejor


def _elementos(U, aut, hwnd, limite: int = 1500) -> list:
    import comtypes
    raiz = aut.ElementFromHandle(hwnd)
    condicion = None
    for tipo in TIPOS_CLIC:
        c = aut.CreatePropertyCondition(30003, tipo)  # UIA_ControlTypePropertyId
        condicion = c if condicion is None else aut.CreateOrCondition(condicion, c)
    encontrados = raiz.FindAll(4, condicion)  # TreeScope_Descendants
    lista = []
    for i in range(min(encontrados.Length, limite)):
        el = encontrados.GetElement(i)
        try:
            nombre = el.CurrentName or ""
            if nombre.strip() and not el.CurrentIsOffscreen and el.CurrentIsEnabled:
                lista.append((el, nombre.strip(), el.CurrentControlType))
        except comtypes.COMError:
            continue
    return lista


def _activar(U, el, tipo_control: int, clic: str) -> str:
    import comtypes
    if tipo_control in (50004, 50030):  # campo de texto o documento: solo darle el foco
        el.SetFocus()
        return "foco"
    if clic == "normal":
        for patron, interfaz, metodo in ((10000, "IUIAutomationInvokePattern", "Invoke"),
                                         (10010, "IUIAutomationSelectionItemPattern", "Select"),
                                         (10015, "IUIAutomationTogglePattern", "Toggle"),
                                         (10005, "IUIAutomationExpandCollapsePattern", "Expand")):
            try:
                p = el.GetCurrentPattern(patron)
                if p:
                    getattr(p.QueryInterface(getattr(U, interfaz)), metodo)()
                    return "invocado"
            except comtypes.COMError:
                continue
    r = el.CurrentBoundingRectangle
    if r.right <= r.left or r.bottom <= r.top:
        el.SetFocus()
        cw._enviar(cw.eventos_combinacion([0x0D]))
        return "enter"
    user32.SetCursorPos((r.left + r.right) // 2, (r.top + r.bottom) // 2)
    time.sleep(0.05)
    _clic(clic)
    return "clic"


def hacer_clic_en(nombre: str, tipo_clic: str = "normal") -> dict:
    if not ES_WINDOWS:
        return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
    if ventana_activa_protegida():
        return {"exito": False, "mensaje": PROTEGIDO}
    tipo_clic = "doble" if "doble" in normalizar(tipo_clic) else "derecho" if "derech" in normalizar(tipo_clic) else "normal"
    try:
        U, aut = _uia()
        hwnd = user32.GetForegroundWindow()
        candidatos = _elementos(U, aut, hwnd)
        elegido = elegir_elemento(nombre, candidatos)
        if not elegido:
            nombres = list(dict.fromkeys(_limpiar_nombre(c[1]) for c in candidatos if _limpiar_nombre(c[1])))
            return {"exito": False, "mensaje": f"No encontre '{nombre}' en la ventana.",
                    "opciones_visibles": nombres[:30]}
        modo = _activar(U, elegido[0], elegido[2], tipo_clic)
    except Exception as error:  # la app al frente puede no exponer su interfaz
        log.warning("No se pudo hacer clic en %s: %s", nombre, error)
        return {"exito": False, "mensaje": f"No pude hacer clic en '{nombre}': {error}"}
    log.info("Clic en '%s' (%s)", elegido[1], modo)
    return {"exito": True, "elemento": elegido[1], "tipo": TIPOS_CLIC.get(elegido[2], "control"),
            "decir": f"Listo, hice clic en {elegido[1]}."}


def leer_pantalla(limite: int = 40) -> dict:
    """Ventana al frente, texto con el foco y botones/opciones visibles, para decirlos en voz alta."""
    activa = cw.ventana_activa()
    resultado = {"ventana": activa["titulo"]}
    if not ES_WINDOWS:
        return resultado
    try:
        U, aut = _uia()
        enfocado = aut.GetFocusedElement()
        texto = ""
        for patron, interfaz in ((10002, "IUIAutomationValuePattern"), (10014, "IUIAutomationTextPattern")):
            try:
                p = enfocado.GetCurrentPattern(patron)
                if not p:
                    continue
                p = p.QueryInterface(getattr(U, interfaz))
                texto = p.CurrentValue if patron == 10002 else p.DocumentRange.GetText(1500)
                if texto:
                    break
            except Exception:
                continue
        resultado["enfocado"] = {"nombre": enfocado.CurrentName or "", "texto": (texto or "")[:1500]}
        if not cw.es_ventana_prohibida(activa["titulo"], activa["clase"]):
            nombres = [c[1] for c in _elementos(U, aut, user32.GetForegroundWindow(), limite=800)]
            resultado["opciones_visibles"] = list(dict.fromkeys(nombres))[:limite]
    except Exception as error:
        log.warning("No se pudo leer la pantalla: %s", error)
        resultado["nota"] = "Esta ventana no deja leer sus botones."
    return resultado


# ================================================================ abrir y escribir

# Aplicaciones que se abren ya listas para escribir: Word con un documento en blanco (/w).
LISTAS_PARA_ESCRIBIR = {
    "word": ("winword.exe", "/w", r" - word$"),
    "bloc de notas": ("notepad.exe", "", r"bloc de notas|notepad"),
}
NOMBRES_LISTAS = {
    "word": "word", "guord": "word", "uord": "word", "documento": "word", "documento de word": "word",
    "procesador de texto": "word", "microsoft word": "word",
    "bloc de notas": "bloc de notas", "block de notas": "bloc de notas", "block": "bloc de notas",
    "bloc": "bloc de notas", "notepad": "bloc de notas", "notas": "bloc de notas",
}


def _clave_lista(nombre: str):
    for v in aw._variantes(nombre):
        if v in NOMBRES_LISTAS:
            return NOMBRES_LISTAS[v]
    return None


def preparar_aplicacion(nombre: str, espera: float = 15.0) -> dict:
    """Deja al frente una ventana de 'nombre' lista para escribir; la abre si no esta abierta."""
    if not ES_WINDOWS:
        return {"exito": False, "mensaje": "Este programa solo funciona en Windows."}
    clave = _clave_lista(nombre)
    patron = LISTAS_PARA_ESCRIBIR[clave][2] if clave else None
    ventanas = cw.listar_ventanas()
    if patron:
        existentes = [(h, t) for h, t in ventanas if re.search(patron, normalizar(t))]
    else:
        existentes = cw.buscar_ventanas(nombre, ventanas)
    for hwnd, titulo in existentes:
        if not cw.es_ventana_prohibida(titulo, cw._clase(hwnd)) and enfocar(hwnd):
            return {"exito": True, "ventana": titulo, "abierta_ahora": False}
    antes = {h for h, _ in ventanas}
    if clave:
        exe, argumentos, _ = LISTAS_PARA_ESCRIBIR[clave]
        codigo = shell32.ShellExecuteW(None, "open", exe, argumentos or None, None, 1) or 0
        if codigo <= 32:  # no esta instalada con ese nombre: se busca en el menu Inicio
            r = aw.abrir_aplicacion(nombre)
            if not r.get("exito"):
                return r
    else:
        r = aw.abrir_aplicacion(nombre)
        if not r.get("exito"):
            return r
    fin = time.time() + espera
    while time.time() < fin:
        time.sleep(0.4)
        nuevas = [(h, t) for h, t in cw.listar_ventanas() if h not in antes]
        if patron:
            nuevas = [(h, t) for h, t in nuevas if re.search(patron, normalizar(t))]
        for hwnd, titulo in nuevas:
            if not cw.es_ventana_prohibida(titulo, cw._clase(hwnd)) and enfocar(hwnd):
                time.sleep(1.0 if clave == "word" else 0.4)  # que termine de cargar antes de escribir
                return {"exito": True, "ventana": titulo, "abierta_ahora": True}
    return {"exito": False, "mensaje": f"Abri '{nombre}' pero su ventana no aparecio a tiempo."}


def escribir_en(texto: str, aplicacion: str = "", presionar_enter: bool = False) -> dict:
    """Escribe texto; si se indica aplicacion, primero la abre o la trae al frente."""
    destino = None
    if (aplicacion or "").strip():
        destino = preparar_aplicacion(aplicacion)
        if not destino.get("exito"):
            return destino
    resultado = cw.escribir_texto(texto, presionar_enter)
    if resultado.get("exito"):
        donde = f" en {aplicacion}" if destino else ""
        resultado["decir"] = f"Listo, lo escribi{donde}."
    return resultado


# ================================================================ YouTube en la misma pestana

NAVEGADORES = ("google chrome", "microsoft edge", "mozilla firefox", "brave", "opera")


def navegar_en_pestana(url: str, clave: str = "youtube") -> bool:
    """Si hay una ventana de navegador mostrando YouTube, abre la URL ahi mismo (Ctrl+L, URL, Enter)."""
    if not ES_WINDOWS:
        return False
    for hwnd, titulo in cw.listar_ventanas():
        t = normalizar(titulo)
        if clave in t and any(n in t for n in NAVEGADORES):
            if not enfocar(hwnd):
                return False
            time.sleep(0.15)
            cw._enviar(cw.eventos_combinacion([0x11, ord("L")]))  # Ctrl+L: barra de direcciones
            time.sleep(0.15)
            cw._enviar(cw.eventos_texto(url))
            cw._enviar(cw.eventos_combinacion([0x2E]))  # Supr: quita el autocompletado
            cw._enviar(cw.eventos_combinacion([0x0D]))
            log.info("Misma pestana (%s): %s", titulo, url)
            return True
    return False


def abrir_reutilizando(url: str) -> None:
    if not navegar_en_pestana(url):
        aw.abrir_en_navegador(url)


# ================================================================ orden libre

VERBOS_ABRIR = r"^(?:abre|abrir|abreme|abrime|abri|ejecuta|inicia|lanza|entra a|entra en|ir a|ve a|muestrame|muestra|ensename|activa|enciende|prende|quiero usar|quiero abrir|necesito|dame)\s+"
VERBOS_MUSICA = r"^(?:pon|ponme|ponle|reproduce|reproducir|toca|tocame|quiero escuchar|quiero oir|quiero ver|escuchar|escuchemos|me gustaria escuchar|pasame)\s+"
VERBOS_ESCRIBIR = r"^(?:escribe|escribir|escribeme|dicta|anota|apunta|redacta|teclea|pon el texto|pon|ponle)\s+"
CLIC_FUERTE = r"^(?:haz|has|da|dale|un|doble)?\s*(?:clic|click|cliquea)\b(?:\s+derecho)?\s*(?:en|sobre)?\s*|^(?:toca|presiona|pulsa|aprieta) el boton\s+(?:de\s+)?"
CLIC_SUAVE = r"^(?:presiona|pulsa|aprieta|selecciona|elige|marca|activa la opcion|abre el menu)\s+(?:en\s+)?"
VERBOS_BUSCAR = r"^(?:busca|buscar|buscame|googlea|investiga|averigua)\s+"
VERBOS_CAMBIAR = r"^(?:cambia a|cambiate a|pasa a|pasate a|vuelve a|regresa a|ve a la ventana de|muestrame la ventana de)\s+"
VERBOS_CERRAR = r"^(?:cierra|cierrame|cerrar|quita)\s+"
CORTESIA = r"\b(?:por favor|porfa|porfavor|kusivox|kusi vox|oye|hey|ahora|rapido|ahorita)\b"
CONTEXTO_MULTIMEDIA = r"\b(volumen|sonido|musica|cancion|tema|video|pausa|pausala|pausar|continua|reanuda|siguiente|anterior|silencio|silencia|mute|fuerte|bajito|bajale|subele|play|no escucho|no se escucha|no oigo|muy alto|demasiado alto|mas alto|mas bajo)\b"
CONTROL_MULTIMEDIA = (r"(?:(?:la|el|un|poco|poquito|mas|menos|de)\s+)*(?:pausa|pausala|play|continua|reanuda|sigue|siguiente|"
                      r"anterior|otra cancion|otro video|otro tema|otra|silencio|mute|volumen|fuerte|bajo|alto|bajito|stop)")
SEPARADOR_COMPUESTO = r"\s+(?:y luego|y despues|despues|luego|y)\s+(?=(?:escribe|escribir|dicta|anota|redacta|pon|ponle|ponme|reproduce|busca|haz clic|has clic|dale clic|da clic|presiona|pulsa|guarda|guardalo|selecciona|copia|pega|baja|sube|abre|cierra)\b)"
INICIO_ESCRIBIR = ("escrib", "dicta", "anota", "apunta", "redacta", "teclea", "pon el texto")


def _sin_cortesia(frase: str) -> str:
    texto = re.sub(r"[¡!¿?,;:\"“”«»()]", " ", frase or "")
    return " ".join(re.sub(CORTESIA, " ", normalizar(texto)).split())


def _consulta_musica(texto: str) -> str:
    texto = re.sub(VERBOS_MUSICA, "", texto)
    texto = re.sub(r"\b(?:en|de|desde)\s+(?:youtube|yutub)\b|\b(?:youtube|yutub)\b", " ", texto)
    texto = re.sub(r"^(?:un|una|el|la|algo de|algo|un poco de)\s+", "", " ".join(texto.split()))
    return texto.strip()


def interpretar_orden(frase: str) -> list:
    """Convierte una orden libre en una lista de pasos [(herramienta, argumentos)]. No ejecuta nada."""
    texto = _sin_cortesia(frase)
    if not texto:
        return []
    partes = [p.strip() for p in re.split(SEPARADOR_COMPUESTO, texto) if p.strip()]
    pasos, app_abierta = [], None
    for parte in partes:
        paso = _interpretar_parte(parte, app_abierta)
        if paso[0] == "abrir":
            app_abierta = paso[1]["nombre"]
        pasos.append(paso)
    # 'abre Word y escribe hola' o 'abre YouTube y pon cumbia': el segundo paso ya abre lo necesario.
    if len(pasos) >= 2 and pasos[0][0] == "abrir" and pasos[1][0] in ("escribir_en", "reproducir_en_youtube"):
        pasos = pasos[1:]
    return pasos


NAVEGADOR_EN_FRASE = r"(brave|chrome|google chrome|edge|microsoft edge|firefox|mozilla|opera)"


def _interpretar_parte(texto: str, app_abierta) -> tuple:
    # 0. Navegador: 'usa Brave como navegador', 'abre YouTube en Brave', 'busca el clima en Chrome'.
    m = re.fullmatch(r"(?:usa|usar|utiliza|elige|pon|deja)\s+(?:el navegador\s+)?" + NAVEGADOR_EN_FRASE
                     + r"(?:\s+como (?:mi |el )?navegador.*)?|(?:cambia|pon|configura) el navegador (?:a|en|como)?\s*"
                     + NAVEGADOR_EN_FRASE + r".*", texto)
    if m and (m.group(1) or m.group(2)):
        return ("elegir_navegador", {"texto": m.group(1) or m.group(2)})
    m = re.search(r"\s+(?:en|con)\s+(?:el\s+)?" + NAVEGADOR_EN_FRASE + r"$", texto)
    if m and not re.search(VERBOS_ESCRIBIR, texto):
        paso = _interpretar_parte(texto[:m.start()], app_abierta)
        if paso[0] in ("abrir", "buscar_en_internet", "abrir_pagina_web"):
            paso[1]["navegador"] = m.group(1)
        return paso
    # 1. Energia. Apagar, reiniciar y cerrar sesion siempre piden confirmacion aparte.
    if re.search(r"\bcancela\b.*\b(apagado|reinicio|apagar|reiniciar)\b|\b(no apagues|no reinicies|deten el apagado)\b", texto):
        return ("energia", {"accion": "cancelar"})
    if re.search(r"\b(apaga|apagate|apagar|reinicia|reiniciate|reiniciar|cierra (la )?sesion|suspende|suspender|bloquea|bloquear|bloqueala|a dormir|hiberna)\b", texto) \
            and not re.search(r"\b(musica|cancion|video|volumen|sonido|luz|wifi|bluetooth)\b", texto):
        destino = next((v for k, v in sorted(sw.ENERGIA.items(), key=lambda kv: -len(kv[0])) if k in texto), None)
        if destino:
            return ("energia", {"accion": destino})
    # 2. Clic dicho con claridad: 'haz clic en Guardar', 'doble clic', 'clic derecho en la imagen'.
    if re.search(CLIC_FUERTE, texto):
        tipo = "doble" if "doble" in texto else "derecho" if re.search(r"(clic|click) derecho", texto) else "normal"
        objetivo = re.sub(CLIC_FUERTE, "", texto).strip()
        if objetivo and not re.fullmatch(r"(aqui|ahi|alli|aca)", objetivo):
            return ("hacer_clic_en", {"nombre": objetivo, "tipo_clic": tipo})
        return ("usar_mouse", {"accion": texto})
    # 3. Escribir o dictar, con o sin aplicacion: 'escribe hola en Word', 'abre Word y pon la fecha'.
    if re.search(VERBOS_ESCRIBIR, texto):
        cuerpo = re.sub(VERBOS_ESCRIBIR, "", texto)
        m = re.search(r"\s+en\s+(?:el\s+|la\s+|un\s+)?(word|bloc de notas|block de notas|notepad|documento|excel|chat)$", cuerpo)
        if m:
            return ("escribir_en", {"texto": cuerpo[:m.start()], "aplicacion": m.group(1)})
        musica = re.search(r"^(?:musica|cancion|video|algo|un tema|una cancion)", cuerpo) or re.search(r"\b(?:en )?youtube\b", cuerpo)
        app_para_escribir = app_abierta and not es_sitio(app_abierta)
        if texto.startswith(INICIO_ESCRIBIR) or (app_para_escribir and not musica):
            return ("escribir_en", {"texto": cuerpo, "aplicacion": app_abierta or ""})
    # 4. Mouse.
    if re.search(r"\b(mouse|raton|puntero|cursor|rueda|scroll|desplaz)", texto):
        return ("usar_mouse", {"accion": texto})
    # 5. Buscar (antes que la musica: 'busca recetas en YouTube' muestra resultados).
    if re.search(VERBOS_BUSCAR, texto) and not atajo_por_nombre(texto):
        consulta = re.sub(VERBOS_BUSCAR, "", texto)
        if re.search(r"\b(?:en|de) (?:youtube|yutub)\b", consulta):
            return ("buscar_en_youtube", {"consulta": _consulta_musica(consulta)})
        return ("buscar_en_internet", {"consulta": re.sub(r"\s+en\s+(?:google|internet)$", "", consulta)})
    # 6. Configuracion de Windows y accesibilidad ('pon las letras grandes', 'activa el alto contraste').
    if re.search(r"\b(configuracion|ajustes|accesibilidad|letras grandes|letra grande|texto grande|alto contraste|puntero mas grande)\b", texto):
        return ("abrir_configuracion", {"seccion": texto})
    # 7. Poner musica o un video ('pon Despacito', 'quiero escuchar cumbia', 'videos de gatos en YouTube').
    if re.search(VERBOS_MUSICA, texto) or re.search(r"\b(?:en|de) (?:youtube|yutub)\b", texto):
        consulta = _consulta_musica(texto)
        if consulta and re.fullmatch(CONTROL_MULTIMEDIA, consulta):
            return ("controlar_multimedia", {"accion": texto})
        if not consulta:
            return ("abrir", {"nombre": "youtube"})
        return ("reproducir_en_youtube", {"consulta": consulta})
    # 8. Controlar lo que ya suena: 'mas fuerte', 'pasa a la siguiente', 'no escucho nada'.
    if (re.search(CONTEXTO_MULTIMEDIA, texto) and cw.accion_multimedia(texto) is not None
            and not re.search(VERBOS_ABRIR, texto) and "pagina" not in texto) or re.fullmatch(CONTROL_MULTIMEDIA, texto):
        return ("controlar_multimedia", {"accion": texto})
    # 9. Atajos con nombre: 'guardalo', 'copia esto', 'nueva pestana', 'presiona enter', 'selecciona todo'.
    atajo = atajo_por_nombre(re.sub(CLIC_SUAVE, "", texto)) or atajo_por_nombre(texto)
    if atajo and len(texto.split()) <= 5:
        return ("presionar_teclas", {"teclas": atajo[0]})
    # 10. Clic dicho de otra forma: 'presiona Aceptar', 'selecciona la opcion Imprimir'.
    if re.search(CLIC_SUAVE, texto):
        return ("hacer_clic_en", {"nombre": re.sub(CLIC_SUAVE, "", texto), "tipo_clic": "normal"})
    # 11. Ventanas.
    if re.search(VERBOS_CAMBIAR, texto):
        return ("cambiar_a_ventana", {"nombre": re.sub(VERBOS_CAMBIAR, "", texto)})
    if re.search(VERBOS_CERRAR, texto):
        objetivo = re.sub(VERBOS_CERRAR, "", texto)
        if re.fullmatch(r"(?:esto|eso|esta ventana|la ventana|todo esto|esta)", objetivo):
            return ("cerrar_ventana_activa", {})
        return ("cerrar_aplicacion", {"nombre": objetivo})
    # 12. Carpetas.
    sin_verbo = re.sub(VERBOS_ABRIR, "", texto)
    if "carpeta" in texto or re.fullmatch(r"(?:mis |la |el |las )?(descargas|documentos|imagenes|fotos|videos|papelera|papelera de reciclaje|capturas de pantalla|este equipo|mi pc)", sin_verbo):
        return ("abrir_carpeta", {"nombre": sin_verbo})
    # 13. Abrir lo que sea: una aplicacion o una pagina (sirve aunque solo diga 'Word' o 'YouTube').
    return ("abrir", {"nombre": re.sub(r"^(?:el|la|los|las|un|una|mi)\s+", "", sin_verbo)})


def es_sitio(nombre: str) -> bool:
    """True si 'nombre' es una pagina conocida ('youtube', 'facebook') o una direccion ('github.com')."""
    return aw.url_para(nombre) != "https://www.google.com/search?q=" + urllib.parse.quote_plus(nombre)


def abrir_lo_que_sea(nombre: str, apps=None, navegador: str = "") -> dict:
    """Abre una aplicacion instalada; si no hay, la pagina web con ese nombre."""
    clave = normalizar(nombre)
    sitio = es_sitio(nombre)
    if navegador:  # 'abre YouTube en Brave': siempre la pagina, en ese navegador
        r = aw.abrir_pagina_web(nombre, navegador=navegador)
        r["decir"] = f"Listo, abri {nombre} en {navegador.capitalize()}."
        return r
    es_app_conocida = clave in aw.ALIAS or clave in aw.DIRECTOS or _clave_lista(nombre)
    if sitio and not es_app_conocida:
        instaladas = aw.buscar_apps(nombre, apps if apps is not None else aw.leer_apps_inicio())
        if not instaladas or normalizar(instaladas[0]["Name"]) != clave:
            r = aw.abrir_pagina_web(nombre, abrir=abrir_reutilizando if "youtube" in aw.url_para(nombre) else None)
            r["decir"] = f"Listo, abri {nombre}."
            return r
    r = _abrir_app_y_esperar(nombre)
    if not r.get("exito") and sitio:
        r = aw.abrir_pagina_web(nombre)
        r["decir"] = f"Listo, abri {nombre}."
    return r


def ejecutar_orden(frase: str, hacer: dict = None) -> dict:
    """Interpreta y ejecuta una orden libre. 'hacer' permite reemplazar las herramientas (pruebas)."""
    hacer = hacer or HERRAMIENTAS
    pasos = interpretar_orden(frase)
    if not pasos:
        return {"exito": False, "mensaje": "No escuche ninguna orden."}
    resultados = []
    for herramienta, argumentos in pasos:
        if herramienta == "energia" and argumentos["accion"] in sw.NECESITAN_CONFIRMAR:
            resultados.append({"exito": False, "requiere_confirmacion": True,
                               "mensaje": f"Para {argumentos['accion']} pregunta al usuario si esta seguro "
                                          f"y luego usa la herramienta energia con confirmado=true."})
            break
        try:
            r = hacer[herramienta](**argumentos)
        except Exception as error:
            r = {"exito": False, "mensaje": str(error)}
        r = dict(r or {})
        r["paso"] = herramienta
        resultados.append(r)
        log.info("Orden libre '%s' -> %s %s", frase, herramienta, argumentos)
        if not r.get("exito"):
            break
    ultimo = resultados[-1]
    respuesta = {"exito": all(r.get("exito") for r in resultados), "pasos": resultados}
    if ultimo.get("decir"):
        respuesta["decir"] = ultimo["decir"]
    return respuesta


def _abrir_app_y_esperar(nombre: str) -> dict:
    r = aw.abrir_aplicacion(nombre)
    if r.get("exito"):
        time.sleep(0.5)
        r["decir"] = f"Listo, abri {r.get('abierta', nombre)}."
    return r


def _reproducir(consulta: str) -> dict:
    r = cw.reproducir_en_youtube(consulta, abrir=abrir_reutilizando)
    if r.get("exito"):
        r["decir"] = f"Listo, puse {consulta} en YouTube." if r.get("reproduciendo") else "Te muestro los resultados en YouTube."
    return r


HERRAMIENTAS = {
    "abrir": abrir_lo_que_sea,
    "abrir_aplicacion": _abrir_app_y_esperar,
    "abrir_pagina_web": lambda direccion: aw.abrir_pagina_web(direccion, abrir=abrir_reutilizando if "youtube" in aw.url_para(direccion) else None),
    "reproducir_en_youtube": _reproducir,
    "buscar_en_youtube": lambda consulta: aw.buscar_en_youtube(consulta, abrir=abrir_reutilizando),
    "buscar_en_internet": lambda consulta, navegador="": aw.buscar_en_internet(
        consulta, abrir=(lambda u: aw.abrir_en_navegador(u, navegador)) if navegador else None),
    "elegir_navegador": lambda texto: aw.elegir_navegador(texto),
    "abrir_carpeta": aw.abrir_carpeta,
    "controlar_multimedia": lambda accion: cw.controlar_multimedia(accion),
    "presionar_teclas": lambda teclas: presionar_por_nombre(teclas),
    "escribir_en": escribir_en,
    "hacer_clic_en": hacer_clic_en,
    "usar_mouse": lambda accion: usar_mouse(accion),
    "abrir_configuracion": sw.abrir_configuracion,
    "cambiar_a_ventana": cw.cambiar_a_ventana,
    "cerrar_aplicacion": sw.cerrar_aplicacion,
    "cerrar_ventana_activa": cw.cerrar_ventana_activa,
    "energia": lambda accion: sw.energia(accion),
}


def presionar_por_nombre(teclas: str, veces: int = 1, enviar=None) -> dict:
    """presionar_teclas que tambien entiende nombres de acciones: 'guardar', 'copiar', 'nueva pestana'."""
    r = cw.presionar_teclas(teclas, veces, enviar=enviar)
    if r.get("exito") or "seguridad" in r.get("mensaje", ""):
        return r
    atajo = atajo_por_nombre(teclas)
    if not atajo:
        return r
    r = cw.presionar_teclas(atajo[1], veces, enviar=enviar)
    if r.get("exito"):
        r["accion"] = atajo[0]
        r["decir"] = f"Listo: {atajo[0]}."
    return r
