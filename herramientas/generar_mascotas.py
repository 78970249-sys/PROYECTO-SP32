"""
Mascotas realistas de KusiVox: perrito (shih tzu), gatito, conejito, osito panda y pajarito (canario).

Cada animal tiene 12 emociones animadas de 6 cuadros (GIF 240x240) con una paleta fija de 64 colores:
  0-15  rampa del pelaje principal (oscuro -> claro)
  16-31 rampa del pelaje secundario
  32-62 colores fijos (ojos, nariz, lengua, corazones, lagrimas, rama...)
  63    marca de KusiVox (ningun pixel la usa): el firmware solo recolorea GIF con esta marca.
El firmware cambia el color de la mascota reemplazando las entradas 0-31 de la paleta (sin guardar copias).

Uso: python3 generar_mascotas.py [carpeta_salida] [animal ...]
"""

import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

W = 720            # se dibuja a 3x y se reduce a 240
LADO = 240
CUADROS = 6
FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MARCA = (7, 254, 13)

EMOCIONES = ["neutral", "happy", "laughing", "sad", "crying", "angry", "surprised", "thinking",
             "sleepy", "loving", "confused", "winking"]
DEMORA = {"neutral": 170, "happy": 110, "laughing": 90, "sad": 200, "crying": 160, "angry": 110,
          "surprised": 120, "thinking": 190, "sleepy": 230, "loving": 150, "confused": 170, "winking": 150}

# ------------------------------------------------------------------ paleta
FIJOS = {
    "fondo": (0, 0, 0), "blanco": (255, 255, 255), "iris": (78, 46, 24), "pupila": (22, 14, 10),
    "iris_verde": (120, 170, 70), "iris_ambar": (205, 145, 45), "nariz": (38, 30, 32), "rosa_oreja": (232, 150, 160),
    "lengua": (232, 104, 122), "boca": (100, 28, 38), "rubor": (250, 135, 150), "corazon": (236, 52, 84),
    "lagrima": (110, 190, 250), "lagrima_luz": (195, 232, 255), "pico": (245, 152, 40), "pico_osc": (185, 98, 22),
    "rama": (112, 72, 40), "rama_osc": (68, 44, 26), "pata_ave": (190, 150, 138), "bigote": (214, 214, 220),
    "chispa": (255, 222, 80), "enojo": (222, 44, 44), "sombra": (26, 26, 32), "sombra2": (44, 44, 52),
    "esclerotica": (238, 232, 222), "gris": (128, 128, 136), "zzz": (150, 200, 255), "rosa_claro": (255, 198, 210),
    "gris_osc": (60, 60, 68), "gris_claro": (172, 172, 180), "crema": (246, 236, 212),
}
NOMBRES_FIJOS = list(FIJOS)
assert len(NOMBRES_FIJOS) == 31


def rampa(base):
    """16 tonos del pelaje: 0-9 de sombra a base, 10-15 de base hacia blanco."""
    r, g, b = base
    tonos = []
    for k in range(16):
        if k <= 9:
            f = 0.16 + 0.84 * k / 9
            tonos.append((r * f, g * f, b * f))
        else:
            m = (k - 9) / 6 * 0.55
            tonos.append((r + (255 - r) * m, g + (255 - g) * m, b + (255 - b) * m))
    return [tuple(int(round(c)) for c in t) for t in tonos]


ANIMALES = {
    # animal: [(nombre del color, base principal, base secundaria), ...] (el primero es el de fabrica)
    "perro": [("blanco y dorado", (246, 241, 230), (214, 158, 84)), ("café", (206, 156, 104), (122, 76, 40)),
              ("negro y blanco", (242, 242, 242), (52, 52, 58))],
    "gato": [("naranja", (232, 142, 62), (246, 233, 212)), ("gris", (150, 152, 160), (240, 240, 242)),
             ("negro", (74, 70, 78), (236, 236, 236))],
    "conejo": [("blanco", (244, 240, 236), (226, 216, 206)), ("café", (172, 122, 82), (236, 222, 198)),
               ("gris", (150, 150, 156), (228, 228, 232))],
    "panda": [("blanco y negro", (242, 240, 232), (44, 44, 48)), ("café", (236, 222, 198), (112, 76, 50)),
              ("gris", (226, 226, 230), (88, 88, 98))],
    "pajaro": [("amarillo", (250, 212, 44), (196, 176, 52)), ("celeste", (124, 196, 240), (60, 100, 162)),
               ("rojo", (222, 54, 48), (122, 30, 30))],
}


def paleta_para(animal, color=0):
    _, p, s = ANIMALES[animal][color]
    return rampa(p) + rampa(s) + [FIJOS[n] for n in NOMBRES_FIJOS] + [MARCA]


# ------------------------------------------------------------------ motor de dibujo

class Lienzo:
    """Capa RGB + alfa en numpy. Las partes del cuerpo se pintan con sombreado de pelaje."""

    def __init__(self, P, S):
        self.rgb = np.zeros((W, W, 3), np.float32)
        self.alfa = np.zeros((W, W), np.float32)
        self.P, self.S = np.array(P, np.float32), np.array(S, np.float32)
        self.textura = textura_pelo()

    def mascara(self, dibujar):
        m = Image.new("L", (W, W), 0)
        dibujar(ImageDraw.Draw(m))
        return m

    def parte(self, dibujar, rampa="P", k=9.0, relieve=3.2, borde=3.0, pelo=1.0, luz=(-0.32, -0.42)):
        """Pinta una parte con luz arriba a la izquierda, borde oscuro y vetas de pelo."""
        m = self.mascara(dibujar)
        caja = m.getbbox()
        if not caja:
            return
        tam = max(caja[2] - caja[0], caja[3] - caja[1])
        r = max(4, tam * 0.16)
        interior = np.asarray(m.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255
        dx, dy = int(luz[0] * tam * 0.35), int(luz[1] * tam * 0.35)
        luz_m = ImageChops.offset(m, -dx, -dy).filter(ImageFilter.GaussianBlur(r * 1.6))
        luz_a = np.asarray(luz_m, np.float32) / 255
        a = np.asarray(m, np.float32) / 255
        tono = k + relieve * (luz_a - 0.55) - borde * np.clip(0.75 - interior, 0, 1) + pelo * self.textura
        tono = np.clip(tono, 0, 15)
        tabla = self.P if rampa == "P" else self.S
        bajo = np.floor(tono).astype(int)
        alto = np.clip(bajo + 1, 0, 15)
        f = (tono - bajo)[..., None]
        color = tabla[bajo] * (1 - f) + tabla[alto] * f
        self.rgb = self.rgb * (1 - a[..., None]) + color * a[..., None]
        self.alfa = np.maximum(self.alfa, a)

    def plano(self, dibujar, color):
        """Pinta una forma de un color fijo (ojos, nariz, corazones...)."""
        m = self.mascara(dibujar)
        a = np.asarray(m, np.float32) / 255
        c = np.array(color, np.float32)
        self.rgb = self.rgb * (1 - a[..., None]) + c * a[..., None]
        self.alfa = np.maximum(self.alfa, a)

    def a_imagen(self):
        rgba = np.dstack([np.clip(self.rgb, 0, 255), self.alfa * 255]).astype(np.uint8)
        return Image.fromarray(rgba, "RGBA")


_TEXTURA = None


def textura_pelo():
    """Vetas cortas de pelo (valores -1..1), siempre las mismas para que no 'hiervan' entre cuadros."""
    global _TEXTURA
    if _TEXTURA is None:
        rnd = random.Random(7)
        t = Image.new("L", (W, W), 128)
        d = ImageDraw.Draw(t)
        for _ in range(5200):
            x, y = rnd.uniform(0, W), rnd.uniform(0, W)
            ang = math.radians(rnd.gauss(90, 18))
            largo = rnd.uniform(8, 20)
            v = rnd.choice((70, 95, 165, 190))
            d.line((x, y, x + math.cos(ang) * largo, y + math.sin(ang) * largo), fill=v, width=2)
        t = t.filter(ImageFilter.GaussianBlur(1.2))
        _TEXTURA = (np.asarray(t, np.float32) - 128) / 128 * 0.9
    return _TEXTURA


def elipse(cx, cy, rx, ry):
    return (cx - rx, cy - ry, cx + rx, cy + ry)


def poligono_rotado(puntos, cx, cy, ang):
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in puntos]


def elipse_rotada(cx, cy, rx, ry, ang, n=48):
    pts = [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return poligono_rotado(pts, cx, cy, ang)


# ------------------------------------------------------------------ ojos, bocas y simbolos

def ojo(lz, cx, cy, r, estado, iris="iris", pupila_v=False, mirar=(0, 0), abierto=1.0):
    """Ojo realista: almendra con iris, pupila y brillo. estado: normal, cerrado, feliz, triste, enojado, dormido."""
    F = FIJOS
    if estado in ("cerrado", "dormido"):
        lz.plano(lambda d: d.arc(elipse(cx, cy - r * 0.2, r * 0.95, r * 0.6), 20, 160, fill=255, width=max(5, int(r * 0.22))), F["pupila"])
        return
    if estado == "feliz":
        lz.plano(lambda d: d.arc(elipse(cx, cy + r * 0.35, r * 0.95, r * 0.75), 200, 340, fill=255, width=max(6, int(r * 0.26))), F["pupila"])
        return
    alto = r * 0.82 * abierto
    lz.plano(lambda d: d.ellipse(elipse(cx, cy, r, alto), fill=255), F["pupila"])
    ix, iy = cx + mirar[0] * r * 0.25, cy + mirar[1] * r * 0.25
    lz.plano(lambda d: d.ellipse(elipse(ix, iy, r * 0.8, min(alto * 0.95, r * 0.8)), fill=255), F[iris])
    if pupila_v:
        lz.plano(lambda d: d.ellipse(elipse(ix, iy, r * 0.18, min(alto * 0.85, r * 0.7)), fill=255), F["pupila"])
    else:
        lz.plano(lambda d: d.ellipse(elipse(ix, iy, r * 0.46, min(alto * 0.6, r * 0.46)), fill=255), F["pupila"])
    lz.plano(lambda d: d.ellipse(elipse(ix - r * 0.3, iy - r * 0.32, r * 0.2, r * 0.2), fill=255), F["blanco"])
    lz.plano(lambda d: d.ellipse(elipse(ix + r * 0.25, iy + r * 0.2, r * 0.09, r * 0.09), fill=255), F["blanco"])
    if estado == "triste":   # parpado caido hacia afuera
        lado = 1 if cx > 360 else -1
        pts = [(cx - r * 1.2, cy - r * 1.2), (cx + r * 1.2, cy - r * 1.2),
               (cx + r * 1.2, cy - r * (0.05 if lado < 0 else 0.55)), (cx - r * 1.2, cy - r * (0.55 if lado < 0 else 0.05))]
        return pts
    if estado == "enojado":
        lado = 1 if cx > 360 else -1
        pts = [(cx - r * 1.2, cy - r * 1.3), (cx + r * 1.2, cy - r * 1.3),
               (cx + r * 1.2, cy - r * (0.85 if lado > 0 else 0.05)), (cx - r * 1.2, cy - r * (0.05 if lado > 0 else 0.85))]
        return pts
    return None


def simbolo_texto(lz, texto, x, y, tam, color):
    fuente = ImageFont.truetype(FUENTE, int(tam))
    lz.plano(lambda d: d.text((x, y), texto, font=fuente, fill=255, anchor="mm"), color)


def corazon(lz, x, y, s, color=None):
    color = color or FIJOS["corazon"]
    def dib(d):
        d.ellipse(elipse(x - s * 0.5, y - s * 0.25, s * 0.55, s * 0.55), fill=255)
        d.ellipse(elipse(x + s * 0.5, y - s * 0.25, s * 0.55, s * 0.55), fill=255)
        d.polygon([(x - s * 1.02, y - s * 0.05), (x + s * 1.02, y - s * 0.05), (x, y + s * 1.1)], fill=255)
    lz.plano(dib, color)
    lz.plano(lambda d: d.ellipse(elipse(x - s * 0.62, y - s * 0.42, s * 0.16, s * 0.16), fill=255), FIJOS["rosa_claro"])


def lagrima(lz, x, y, s):
    lz.plano(lambda d: (d.ellipse(elipse(x, y + s * 0.4, s * 0.55, s * 0.6), fill=255),
                        d.polygon([(x - s * 0.5, y + s * 0.25), (x + s * 0.5, y + s * 0.25), (x, y - s * 0.7)], fill=255)), FIJOS["lagrima"])
    lz.plano(lambda d: d.ellipse(elipse(x - s * 0.15, y + s * 0.3, s * 0.15, s * 0.2), fill=255), FIJOS["lagrima_luz"])


def chispa(lz, x, y, s, color=None):
    color = color or FIJOS["chispa"]
    lz.plano(lambda d: d.polygon([(x, y - s), (x + s * 0.25, y - s * 0.25), (x + s, y), (x + s * 0.25, y + s * 0.25),
                                  (x, y + s), (x - s * 0.25, y + s * 0.25), (x - s, y), (x - s * 0.25, y - s * 0.25)], fill=255), color)


def simbolos(lz, emocion, t, cab):
    """Detalles de cada emocion alrededor de la cabeza (cab = centro x, y y radio de la cabeza)."""
    cx, cy, r = cab
    fase = t / CUADROS
    if emocion == "loving":
        for i, (dx, base) in enumerate(((-1.25, 0.0), (1.3, 0.35), (1.0, 0.7))):
            f = (fase + base) % 1.0
            corazon(lz, cx + dx * r, cy - r * 0.4 - f * r * 1.0, r * (0.13 + 0.06 * math.sin(f * math.pi)))
    elif emocion == "sleepy":
        for i in range(3):
            f = (fase + i / 3) % 1.0
            simbolo_texto(lz, "z", cx + r * (0.9 + f * 0.6), cy - r * (0.6 + f * 0.9), r * (0.22 + f * 0.25), FIJOS["zzz"])
    elif emocion == "thinking":
        n = 1 + t % 4
        for i in range(min(n, 3)):
            lz.plano(lambda d, i=i: d.ellipse(elipse(cx + r * (0.95 + i * 0.28), cy - r * (0.75 + i * 0.32), r * (0.06 + i * 0.035),
                                                       r * (0.06 + i * 0.035)), fill=255), FIJOS["blanco"])
    elif emocion == "confused":
        simbolo_texto(lz, "?", cx + r * 1.15, cy - r * (0.95 + 0.08 * math.sin(fase * 2 * math.pi)), r * 0.55, FIJOS["blanco"])
    elif emocion == "surprised":
        if t >= 1:
            simbolo_texto(lz, "!", cx + r * 1.15, cy - r * 0.95, r * 0.6, FIJOS["chispa"])
    elif emocion == "angry":
        s = r * (0.16 + 0.03 * (t % 2))
        x, y = cx + r * 0.95, cy - r * 0.85
        for ang in (45, 135, 225, 315):
            lz.plano(lambda d, ang=ang: d.line((x + math.cos(math.radians(ang)) * s * 0.35, y + math.sin(math.radians(ang)) * s * 0.35,
                                                 x + math.cos(math.radians(ang)) * s * 1.2, y + math.sin(math.radians(ang)) * s * 1.2),
                                                fill=255, width=int(s * 0.38)), FIJOS["enojo"])
    elif emocion == "laughing":
        for i, (dx, dy) in enumerate(((-1.25, -0.55), (1.25, -0.6))):
            if (t + i) % 2 == 0:
                chispa(lz, cx + dx * r, cy + dy * r, r * 0.13)
    elif emocion == "winking":
        if 1 <= t <= 4:
            chispa(lz, cx + r * 0.95, cy - r * 0.55, r * (0.1 + 0.04 * (t % 2)))
    elif emocion == "happy" and t in (1, 4):
        chispa(lz, cx - r * 1.15, cy - r * 0.5, r * 0.09)
        chispa(lz, cx + r * 1.2, cy - r * 0.35, r * 0.07)


# ------------------------------------------------------------------ pose de cada cuadro

def pose(emocion, t):
    """Movimiento comun: rebote, cabeza, orejas, cola y ojos para la emocion y el cuadro t."""
    fase = 2 * math.pi * t / CUADROS
    p = {"bote": 0.0, "lado": 0.0, "giro": 0.0, "cab_y": 0.0, "orejas": "normal", "cola": math.sin(fase) * 0.4,
         "ojos": "normal", "ojo_der": None, "boca": "cerrada", "mirar": (0, 0), "abierto": 1.0, "rubor": False,
         "respira": 1.0 + 0.012 * math.sin(fase)}
    if emocion == "neutral":
        p["bote"] = 3 * math.sin(fase)
        if t == 3:
            p["ojos"] = "cerrado"
    elif emocion == "happy":
        p.update(bote=-14 * abs(math.sin(fase)), orejas="arriba", cola=math.sin(fase * 2) * 1.0, ojos="normal", boca="sonrisa")
        p["abierto"] = 0.85
    elif emocion == "laughing":
        p.update(lado=7 * math.sin(fase * 2), bote=-6 * abs(math.sin(fase * 2)), orejas="arriba", cola=math.sin(fase * 2),
                 ojos="feliz", boca="risa", giro=4 * math.sin(fase))
    elif emocion in ("sad", "crying"):
        p.update(cab_y=14, orejas="abajo", cola=-0.6, ojos="triste", boca="triste", mirar=(0, 0.5), bote=2 * math.sin(fase))
        if emocion == "crying":
            p["boca"] = "llanto"
    elif emocion == "angry":
        p.update(lado=4 * math.sin(fase * 3), orejas="atras", ojos="enojado", boca="enojo", cola=0.2 * math.sin(fase * 3))
    elif emocion == "surprised":
        salto = {0: 0, 1: -18, 2: -10, 3: -4, 4: 0, 5: 0}[t]
        p.update(bote=salto, orejas="arriba", ojos="normal", boca="o", abierto=1.18)
    elif emocion == "thinking":
        p.update(giro=7, ojos="normal", mirar=(0.7, -0.8), boca="pensando", bote=2 * math.sin(fase))
    elif emocion == "sleepy":
        p.update(cab_y=10, ojos="dormido", orejas="abajo", boca="cerrada", cola=0.0, giro=-4,
                 respira=1.0 + 0.03 * math.sin(fase))
    elif emocion == "loving":
        p.update(ojos="feliz", rubor=True, boca="sonrisa", cola=math.sin(fase * 2) * 0.9, bote=-5 * abs(math.sin(fase)), giro=-3)
    elif emocion == "confused":
        p.update(giro=10 * math.sin(fase), orejas="asimetrica", ojos="normal", boca="confusion", mirar=(-0.4, -0.3))
    elif emocion == "winking":
        p.update(ojos="normal", ojo_der="cerrado" if 1 <= t <= 4 else None, boca="sonrisa", giro=4, bote=-3 * abs(math.sin(fase)))
    return p


# ------------------------------------------------------------------ animales

def suelo(lz, cx, ancho, y=672):
    lz.plano(lambda d: d.ellipse(elipse(cx, y, ancho, 22), fill=255), FIJOS["sombra"])


def boca_mamifero(lz, cx, cy, r, tipo, estilo="perro"):
    """Boca bajo la nariz. cy = punto bajo la nariz, r = radio de la cabeza."""
    F, w = FIJOS, max(5, int(r * 0.045))
    if tipo in ("sonrisa", "risa", "o", "llanto", "enojo"):
        ancho = {"sonrisa": 0.26, "risa": 0.32, "o": 0.13, "llanto": 0.2, "enojo": 0.26}[tipo] * r
        alto = {"sonrisa": 0.22, "risa": 0.34, "o": 0.24, "llanto": 0.18, "enojo": 0.14}[tipo] * r
        y0 = cy + r * 0.06
        if tipo == "o":
            lz.plano(lambda d: d.ellipse(elipse(cx, y0 + alto * 0.7, ancho, alto * 0.8), fill=255), F["boca"])
        elif tipo == "enojo":
            lz.plano(lambda d: d.rounded_rectangle((cx - ancho, y0, cx + ancho, y0 + alto), radius=alto * 0.4, fill=255), F["boca"])
            lz.plano(lambda d: d.rectangle((cx - ancho * 0.8, y0 + 2, cx + ancho * 0.8, y0 + alto * 0.35), fill=255), F["blanco"])
        elif tipo == "llanto":
            lz.plano(lambda d: d.chord(elipse(cx, y0 + alto * 1.1, ancho, alto), 180, 360, fill=255), F["boca"])
        else:
            lz.plano(lambda d: d.chord(elipse(cx, y0, ancho, alto * 1.6), 0, 180, fill=255), F["boca"])
            if estilo in ("perro", "panda"):
                lz.plano(lambda d: d.ellipse(elipse(cx, y0 + alto * 1.05, ancho * 0.62, alto * 0.62), fill=255), F["lengua"])
            if estilo == "conejo":
                lz.plano(lambda d: d.rectangle((cx - r * 0.07, y0, cx + r * 0.07, y0 + r * 0.1), fill=255), F["blanco"])
                lz.plano(lambda d: d.line((cx, y0, cx, y0 + r * 0.1), fill=255, width=3), F["gris"])
        return
    if tipo == "triste":
        lz.plano(lambda d: d.arc(elipse(cx, cy + r * 0.3, r * 0.17, r * 0.12), 200, 340, fill=255, width=w), F["nariz"])
        return
    if tipo == "pensando":
        lz.plano(lambda d: d.line((cx - r * 0.02, cy + r * 0.12, cx + r * 0.14, cy + r * 0.09), fill=255, width=w), F["nariz"])
        return
    if tipo == "confusion":
        lz.plano(lambda d: d.line([(cx - r * 0.14, cy + r * 0.12), (cx - r * 0.04, cy + r * 0.08), (cx + r * 0.05, cy + r * 0.13),
                                   (cx + r * 0.14, cy + r * 0.09)], fill=255, width=w, joint="curve"), F["nariz"])
        return
    # cerrada: la 'w' de los mamiferos
    lz.plano(lambda d: (d.line((cx, cy, cx, cy + r * 0.07), fill=255, width=w),
                        d.arc(elipse(cx - r * 0.08, cy + r * 0.05, r * 0.08, r * 0.06), 20, 160, fill=255, width=w),
                        d.arc(elipse(cx + r * 0.08, cy + r * 0.05, r * 0.08, r * 0.06), 20, 160, fill=255, width=w)), F["nariz"])


def parpados(lz, pts, rampa_k, lz_P=True):
    if pts:
        lz.parte(lambda d: d.polygon(pts, fill=255), "P" if lz_P else "S", rampa_k, relieve=1.0, borde=0.5, pelo=0.3)


def ojos_mamifero(lz, cx, cy, sep, r, p, iris="iris", pupila_v=False, piel="P", k_piel=9.0):
    estado = p["ojos"]
    for lado in (-1, 1):
        est = p["ojo_der"] if (lado == 1 and p["ojo_der"]) else estado
        x = cx + lado * sep
        tapa = ojo(lz, x, cy, r, est, iris, pupila_v, p["mirar"], p["abierto"])
        if tapa:
            lz.parte(lambda d, tapa=tapa: d.polygon(tapa, fill=255), piel, k_piel, relieve=0.6, borde=0.0, pelo=0.4)
    if p["rubor"]:
        for lado in (-1, 1):
            lz.plano(lambda d, lado=lado: d.ellipse(elipse(cx + lado * sep * 1.35, cy + r * 1.25, r * 0.55, r * 0.3), fill=255), FIJOS["rubor"])
    if estado in ("triste",) and p.get("lagrimas"):
        pass


def lagrimas(lz, cx, cy, sep, r, t):
    for lado in (-1, 1):
        f = ((t / CUADROS) + (0.5 if lado > 0 else 0)) % 1.0
        lagrima(lz, cx + lado * (sep + r * 0.3), cy + r * 0.9 + f * r * 3.2, r * 0.42)


def dibujar_perro(p, t, emocion, lz):
    """Shih tzu realista: pelo largo blanco con manchas doradas, orejas largas, cola en penacho."""
    bx = 360 + p["lado"]
    by = p["bote"]
    suelo(lz, bx, 190)
    # cola en penacho sobre el lomo (derecha)
    ang = -25 + p["cola"] * 25
    cola = elipse_rotada(bx + 150, 430 + by, 70, 120, ang)
    lz.parte(lambda d: d.polygon(cola, fill=255), "S", 10, relieve=3.5, borde=3.5, pelo=1.6)
    # cuerpo con pelo largo que cae hasta el suelo en mechones
    def cuerpo(d):
        d.ellipse((bx - 150, 340 + by, bx + 150, 610 + by), fill=255)
        for i in range(9):
            x = bx - 140 + i * 35
            largo = 668 - (10 if i in (0, 8) else 0) + (6 if i % 2 else 0)
            d.ellipse((x - 26, 470 + by, x + 26, largo), fill=255)
    lz.parte(cuerpo, "P", 10.5, relieve=3.5, borde=3.2, pelo=2.0)
    # mechones del pecho (patas delanteras escondidas bajo el pelo)
    for lado in (-1, 1):
        lz.parte(lambda d, lado=lado: d.ellipse((bx + lado * 55 - 46, 430 + by, bx + lado * 55 + 46, 672), fill=255),
                 "P", 11.5, relieve=2.5, borde=3.0, pelo=2.0)
    for lado in (-1, 1):
        lz.plano(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 55, 662, 30, 12), fill=255), FIJOS["sombra2"])
    # manchas doradas del lomo
    lz.parte(lambda d: d.ellipse((bx + 40, 360 + by, bx + 165, 520 + by), fill=255), "S", 10, relieve=3, borde=3, pelo=1.6)
    # cabeza
    hx, hy, hr = bx, 260 + by + p["cab_y"], 128
    cab = (hx, hy, hr)
    orejas = {"normal": 0, "arriba": -14, "abajo": 16, "atras": -6, "asimetrica": 0}[p["orejas"]]
    for lado in (-1, 1):
        extra = (12 * lado if p["orejas"] == "asimetrica" else 0)
        oreja = elipse_rotada(hx + lado * 112, hy + 78 + orejas + extra, 50, 122, lado * (10 - orejas * 0.3))
        lz.parte(lambda d, oreja=oreja: d.polygon(oreja, fill=255), "S", 9.5, relieve=3.5, borde=3.5, pelo=1.8)
    lz.parte(lambda d: d.ellipse(elipse(hx, hy, hr, hr * 0.95), fill=255), "P", 11, relieve=3.0, borde=2.4, pelo=1.4)
    # mascara dorada alrededor de los ojos y copete
    for lado in (-1, 1):
        lz.parte(lambda d, lado=lado: d.ellipse(elipse(hx + lado * 52, hy - 22, 52, 46), fill=255), "S", 10.5, relieve=2, borde=1.4, pelo=1.3)
    lz.parte(lambda d: d.pieslice(elipse(hx, hy - 30, 92, 92), 200, 340, fill=255), "S", 11, relieve=2, borde=1.5, pelo=1.5)
    # hocico blanco con barba
    lz.parte(lambda d: d.ellipse(elipse(hx, hy + 52, 70, 56), fill=255), "P", 12.5, relieve=2, borde=1.6, pelo=1.6)
    lz.parte(lambda d: d.ellipse(elipse(hx, hy + 100, 58, 40), fill=255), "P", 12, relieve=1.6, borde=1.8, pelo=1.8)
    ojos_mamifero(lz, hx, hy - 18, 52, 22, p, piel="S", k_piel=10.5)
    # nariz
    lz.plano(lambda d: d.ellipse(elipse(hx, hy + 30, 22, 16), fill=255), FIJOS["nariz"])
    lz.plano(lambda d: d.ellipse(elipse(hx - 7, hy + 25, 7, 4), fill=255), FIJOS["gris_claro"])
    boca_mamifero(lz, hx, hy + 44, hr, p["boca"], "perro")
    if emocion == "crying":
        lagrimas(lz, hx, hy - 18, 52, 22, t)
    return cab


def dibujar_gato(p, t, emocion, lz):
    """Gato atigrado sentado: orejas triangulares, ojos verdes de pupila vertical, bigotes y cola rodeando las patas."""
    bx, by = 360 + p["lado"], p["bote"]
    suelo(lz, bx + 20, 175)
    # cola enroscada en el suelo
    fase = p["cola"]
    pts = []
    for i in range(30):
        u = i / 29
        x = bx + 120 + 90 * math.sin(u * 2.2) * (1 - 0.35 * u) - 140 * u
        y = 655 - 60 * u * math.sin(u * 3.0 + fase) - 40 * u
        pts.append((x, y))
    lz.parte(lambda d: d.line(pts, fill=255, width=46, joint="curve"), "P", 8.5, relieve=3, borde=2.5, pelo=1.2)
    # cuerpo sentado: torso y ancas
    lz.parte(lambda d: (d.ellipse((bx - 165, 470 + by, bx - 15, 668), fill=255), d.ellipse((bx + 15, 470 + by, bx + 165, 668), fill=255)),
             "P", 8.5, relieve=3.5, borde=3.5, pelo=1.2)
    lz.parte(lambda d: d.ellipse((bx - 120, 330 + by, bx + 120, 640 + by), fill=255), "P", 9.5, relieve=3.2, borde=3, pelo=1.2)
    # pecho claro
    lz.parte(lambda d: d.ellipse((bx - 70, 370 + by, bx + 70, 600 + by), fill=255), "S", 12, relieve=2, borde=1.5, pelo=1.2)
    # rayas del lomo y ancas (tonos oscuros de la rampa principal)
    for i, y in enumerate((500, 545, 590)):
        for lado in (-1, 1):
            lz.parte(lambda d, y=y, lado=lado: d.arc((bx + lado * 95 - 70, y + by - 20, bx + lado * 95 + 70, y + by + 40), 200 if lado < 0 else 270,
                                                     270 if lado < 0 else 340, fill=255, width=14), "P", 4.5, relieve=0.5, borde=0, pelo=0.6)
    # patas delanteras con patitas claras
    for lado in (-1, 1):
        lz.parte(lambda d, lado=lado: d.rounded_rectangle((bx + lado * 38 - 30, 500 + by, bx + lado * 38 + 30, 668), radius=28, fill=255),
                 "P", 9.5, relieve=2.5, borde=3, pelo=1.0)
        lz.parte(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 40, 655, 36, 22), fill=255), "S", 12, relieve=1.5, borde=2, pelo=0.6)
    # cabeza
    hx, hy, hr = bx, 270 + by + p["cab_y"], 112
    orej = {"normal": 0, "arriba": -8, "abajo": 22, "atras": 30, "asimetrica": 0}[p["orejas"]]
    for lado in (-1, 1):
        giro = lado * (12 + orej) + (lado * 18 if p["orejas"] == "asimetrica" and lado > 0 else 0)
        oreja = poligono_rotado([(hx + lado * 40, hy - 70), (hx + lado * 112, hy - 185), (hx + lado * 120, hy - 40)], hx + lado * 80, hy - 70, giro)
        interior = poligono_rotado([(hx + lado * 58, hy - 78), (hx + lado * 106, hy - 160), (hx + lado * 108, hy - 62)], hx + lado * 80, hy - 70, giro)
        lz.parte(lambda d, oreja=oreja: d.polygon(oreja, fill=255), "P", 9, relieve=2.5, borde=2.5, pelo=0.8)
        lz.plano(lambda d, interior=interior: d.polygon(interior, fill=255), FIJOS["rosa_oreja"])
    lz.parte(lambda d: (d.ellipse(elipse(hx, hy, hr * 1.05, hr * 0.92), fill=255),
                        d.ellipse(elipse(hx - 62, hy + 40, 66, 48), fill=255), d.ellipse(elipse(hx + 62, hy + 40, 66, 48), fill=255)),
             "P", 10, relieve=3.0, borde=2.4, pelo=1.0)
    # rayas de la frente
    for dx in (-26, 0, 26):
        lz.parte(lambda d, dx=dx: d.line((hx + dx, hy - 95, hx + dx * 0.6, hy - 52), fill=255, width=11), "P", 4.5, relieve=0.4, borde=0, pelo=0.3)
    # hocico claro
    lz.parte(lambda d: (d.ellipse(elipse(hx - 28, hy + 42, 36, 30), fill=255), d.ellipse(elipse(hx + 28, hy + 42, 36, 30), fill=255),
                        d.ellipse(elipse(hx, hy + 64, 30, 22), fill=255)), "S", 12.5, relieve=1.6, borde=1.2, pelo=0.6)
    ojos_mamifero(lz, hx, hy - 10, 46, 25, p, iris="iris_verde", pupila_v=True)
    lz.plano(lambda d: d.polygon([(hx - 15, hy + 18), (hx + 15, hy + 18), (hx, hy + 32)], fill=255), FIJOS["rosa_oreja"])
    boca_mamifero(lz, hx, hy + 32, hr, p["boca"], "gato")
    for lado in (-1, 1):
        for i, dy in enumerate((-6, 8, 22)):
            lz.plano(lambda d, lado=lado, dy=dy, i=i: d.line((hx + lado * 55, hy + 40 + dy * 0.4, hx + lado * 185, hy + 30 + dy * 1.6), fill=255, width=3),
                     FIJOS["bigote"])
    if emocion == "crying":
        lagrimas(lz, hx, hy - 10, 46, 25, t)
    return (hx, hy, hr)


def dibujar_conejo(p, t, emocion, lz):
    """Conejo sentado: orejas largas, patas traseras grandes, nariz rosada y dientes."""
    bx, by = 360 + p["lado"], p["bote"]
    suelo(lz, bx, 185)
    lz.parte(lambda d: (d.ellipse((bx - 175, 500 + by, bx - 20, 668), fill=255), d.ellipse((bx + 20, 500 + by, bx + 175, 668), fill=255)),
             "P", 9, relieve=3.5, borde=3.5, pelo=1.1)
    lz.parte(lambda d: d.ellipse((bx - 140, 360 + by, bx + 140, 660 + by), fill=255), "P", 10, relieve=3.4, borde=3.0, pelo=1.1)
    lz.parte(lambda d: d.ellipse((bx - 80, 420 + by, bx + 80, 640 + by), fill=255), "S", 12, relieve=2, borde=1.6, pelo=1.0)
    for lado in (-1, 1):   # pies traseros
        lz.parte(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 115, 652, 70, 24), fill=255), "P", 11, relieve=1.6, borde=2, pelo=0.6)
        lz.parte(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 34, 610 + by, 28, 40), fill=255), "P", 10.5, relieve=2, borde=2.4, pelo=0.6)
    hx, hy, hr = bx, 300 + by + p["cab_y"], 100
    caida = {"normal": 0, "arriba": -8, "abajo": 62, "atras": 28, "asimetrica": 0}[p["orejas"]]
    for lado in (-1, 1):
        giro = lado * (6 + caida) + (lado * 55 if p["orejas"] == "asimetrica" and lado > 0 else 0)
        oreja = elipse_rotada(hx + lado * 42, hy - 160, 38, 125, giro)
        oreja = poligono_rotado(oreja, hx + lado * 42, hy - 60, giro)
        interior = poligono_rotado(elipse_rotada(hx + lado * 42, hy - 160, 20, 100, giro), hx + lado * 42, hy - 60, giro)
        lz.parte(lambda d, oreja=oreja: d.polygon(oreja, fill=255), "P", 10, relieve=3, borde=2.8, pelo=0.8)
        lz.plano(lambda d, interior=interior: d.polygon(interior, fill=255), FIJOS["rosa_oreja"])
    lz.parte(lambda d: (d.ellipse(elipse(hx, hy, hr * 1.05, hr * 0.95), fill=255),
                        d.ellipse(elipse(hx - 50, hy + 40, 60, 45), fill=255), d.ellipse(elipse(hx + 50, hy + 40, 60, 45), fill=255)),
             "P", 11, relieve=3, borde=2.3, pelo=0.9)
    lz.parte(lambda d: d.ellipse(elipse(hx, hy + 48, 48, 34), fill=255), "S", 13, relieve=1.4, borde=1.2, pelo=0.6)
    ojos_mamifero(lz, hx, hy - 8, 50, 24, p)
    lz.plano(lambda d: d.ellipse(elipse(hx, hy + 26, 13, 9), fill=255), FIJOS["rosa_oreja"])
    boca_mamifero(lz, hx, hy + 34, hr, p["boca"], "conejo")
    for lado in (-1, 1):
        for dy in (-4, 10):
            lz.plano(lambda d, lado=lado, dy=dy: d.line((hx + lado * 40, hy + 40 + dy * 0.3, hx + lado * 150, hy + 34 + dy * 1.5), fill=255, width=3),
                     FIJOS["bigote"])
    if emocion == "crying":
        lagrimas(lz, hx, hy - 8, 50, 24, t)
    return (hx, hy, hr)


def dibujar_panda(p, t, emocion, lz):
    """Oso panda sentado: cuerpo blanco, brazos, patas, orejas y antifaz negros."""
    bx, by = 360 + p["lado"], p["bote"]
    suelo(lz, bx, 200)
    lz.parte(lambda d: d.ellipse((bx - 175, 330 + by, bx + 175, 668), fill=255), "P", 10.5, relieve=3.4, borde=3.2, pelo=1.0)
    lz.parte(lambda d: d.chord((bx - 175, 330 + by, bx + 175, 560 + by), 180, 360, fill=255), "S", 9.5, relieve=2.5, borde=2, pelo=1.0)
    for lado in (-1, 1):
        lz.parte(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 120, 625, 72, 50), fill=255), "S", 9.5, relieve=2.5, borde=2.6, pelo=0.9)
        lz.plano(lambda d, lado=lado: d.ellipse(elipse(bx + lado * 120, 630, 34, 26), fill=255), FIJOS["gris_osc"])
        brazo = elipse_rotada(bx + lado * 120, 470 + by, 48, 105, lado * -22)
        lz.parte(lambda d, brazo=brazo: d.polygon(brazo, fill=255), "S", 10, relieve=3, borde=2.8, pelo=1.0)
    hx, hy, hr = bx, 260 + by + p["cab_y"], 130
    sube = {"normal": 0, "arriba": -8, "abajo": 10, "atras": 6, "asimetrica": 0}[p["orejas"]]
    for lado in (-1, 1):
        extra = 12 if (p["orejas"] == "asimetrica" and lado > 0) else 0
        lz.parte(lambda d, lado=lado, extra=extra: d.ellipse(elipse(hx + lado * 100, hy - 100 + sube + extra, 46, 42), fill=255), "S", 10,
                 relieve=2.5, borde=2.5, pelo=0.8)
    lz.parte(lambda d: d.ellipse(elipse(hx, hy, hr, hr * 0.9), fill=255), "P", 11.5, relieve=3, borde=2.3, pelo=0.9)
    for lado in (-1, 1):
        mancha = elipse_rotada(hx + lado * 48, hy + 2, 34, 46, lado * -32)
        lz.parte(lambda d, mancha=mancha: d.polygon(mancha, fill=255), "S", 9, relieve=1.2, borde=0.8, pelo=0.5)
    lz.parte(lambda d: d.ellipse(elipse(hx, hy + 54, 52, 38), fill=255), "P", 13, relieve=1.4, borde=1.3, pelo=0.5)
    p2 = dict(p)
    ojos_mamifero(lz, hx, hy + 2, 46, 15, p2, piel="S", k_piel=9)
    lz.plano(lambda d: d.ellipse(elipse(hx, hy + 38, 22, 14), fill=255), FIJOS["nariz"])
    boca_mamifero(lz, hx, hy + 52, hr, p["boca"], "panda")
    if emocion == "crying":
        lagrimas(lz, hx, hy + 2, 46, 15, t)
    return (hx, hy, hr)


def dibujar_pajaro(p, t, emocion, lz):
    """Canario posado en una rama: cuerpo, alas y cola, pico naranja y patitas."""
    bx, by = 360 + p["lado"], p["bote"] * 0.8
    lz.plano(lambda d: d.rounded_rectangle((70, 598, 650, 632), radius=16, fill=255), FIJOS["rama"])
    lz.plano(lambda d: d.line((80, 626, 640, 626), fill=255, width=8), FIJOS["rama_osc"])
    lz.plano(lambda d: d.line((520, 610, 600, 560), fill=255, width=14), FIJOS["rama"])
    cola = [(bx - 40, 560 + by), (bx + 40, 560 + by), (bx + 26 + p["cola"] * 12, 700), (bx - 26 + p["cola"] * 12, 700)]
    lz.parte(lambda d: d.polygon(cola, fill=255), "S", 9, relieve=2.5, borde=2, pelo=0.8)
    lz.parte(lambda d: d.ellipse((bx - 115, 330 + by, bx + 115, 610 + by), fill=255), "P", 10, relieve=3.5, borde=3, pelo=0.8)
    aleteo = {"happy": 14, "laughing": 10, "surprised": 18}.get(emocion, 0) * abs(math.sin(2 * math.pi * t / CUADROS))
    for lado in (-1, 1):
        ala = elipse_rotada(bx + lado * 78, 478 + by - aleteo * 0.6, 42, 105, lado * (10 + aleteo))
        lz.parte(lambda d, ala=ala: d.polygon(ala, fill=255), "S", 10, relieve=3, borde=2.6, pelo=1.0)
        for i in range(3):
            raya = elipse_rotada(bx + lado * (80 + i * 5), 505 + by + i * 28 - aleteo * 0.6, 22, 46, lado * (10 + aleteo))
            lz.parte(lambda d, raya=raya: d.polygon(raya, fill=255), "S", 7.5 + i * 0.5, relieve=0.8, borde=0.6, pelo=0.4)
    for lado in (-1, 1):
        lz.plano(lambda d, lado=lado: (d.line((bx + lado * 36, 590 + by, bx + lado * 40, 612), fill=255, width=10),
                                       d.line((bx + lado * 40, 612, bx + lado * 70, 616), fill=255, width=8),
                                       d.line((bx + lado * 40, 612, bx + lado * 18, 618), fill=255, width=8)), FIJOS["pata_ave"])
    hx, hy, hr = bx, 300 + by + p["cab_y"], 96
    lz.parte(lambda d: d.ellipse(elipse(hx, hy, hr, hr * 0.92), fill=255), "P", 10.5, relieve=3.2, borde=2.4, pelo=0.6)
    ojos_mamifero(lz, hx, hy - 12, 44, 15, p)
    abierto = {"sonrisa": 10, "risa": 18, "o": 16, "llanto": 8, "enojo": 6}.get(p["boca"], 0)
    lz.plano(lambda d: d.polygon([(hx - 22, hy + 12), (hx + 22, hy + 12), (hx, hy + 44)], fill=255), FIJOS["pico"])
    if abierto:
        lz.plano(lambda d: d.polygon([(hx - 14, hy + 22), (hx + 14, hy + 22), (hx, hy + 30 + abierto)], fill=255), FIJOS["boca"])
        lz.plano(lambda d: d.polygon([(hx - 18, hy + 28 + abierto * 0.5), (hx + 18, hy + 28 + abierto * 0.5), (hx, hy + 52 + abierto)], fill=255),
                 FIJOS["pico_osc"])
    lz.plano(lambda d: d.line((hx - 18, hy + 16, hx + 18, hy + 16), fill=255, width=3), FIJOS["pico_osc"])
    if emocion == "crying":
        lagrimas(lz, hx, hy - 12, 44, 15, t)
    return (hx, hy, hr)


DIBUJOS = {"perro": dibujar_perro, "gato": dibujar_gato, "conejo": dibujar_conejo, "panda": dibujar_panda, "pajaro": dibujar_pajaro}


# ------------------------------------------------------------------ cuadros y GIF

def cuadro(animal, emocion, t):
    paleta = paleta_para(animal)
    lz = Lienzo(paleta[0:16], paleta[16:32])
    p = pose(emocion, t)
    cab = DIBUJOS[animal](p, t, emocion, lz)
    simbolos(lz, emocion, t, cab)
    img = lz.a_imagen()
    # inclinacion de toda la figura (cabeza ladeada en 'pensando' y 'confundido')
    if p["giro"]:
        img = img.rotate(-p["giro"] * 0.35, resample=Image.BICUBIC, center=(360, 660))
    fondo = Image.new("RGB", (W, W), (0, 0, 0))
    fondo.paste(img, (0, 0), img)
    return fondo.resize((LADO, LADO), Image.LANCZOS)


def imagen_paleta(animal):
    pal = paleta_para(animal)
    # 63 colores reales + negro repetido en la 63 (luego se marca)
    plano = []
    for c in pal[:63] + [FIJOS["fondo"]]:
        plano += list(c)
    img = Image.new("P", (1, 1))
    img.putpalette(plano)
    return img


def cuantizar(rgb, pal_img):
    q = rgb.quantize(palette=pal_img, dither=Image.Dither.NONE)
    datos = np.array(q)
    datos[datos == 63] = 32       # el negro repetido vuelve al fondo
    q2 = Image.fromarray(datos.astype(np.uint8), "P")
    return q2


def guardar_gif(animal, emocion, carpeta):
    pal_img = imagen_paleta(animal)
    cuadros = [cuantizar(cuadro(animal, emocion, t), pal_img) for t in range(CUADROS)]
    paleta = []
    for c in paleta_para(animal):
        paleta += list(c)
    for c in cuadros:
        c.putpalette(paleta)
    ruta = os.path.join(carpeta, f"{animal}_{emocion}.gif")
    cuadros[0].save(ruta, save_all=True, append_images=cuadros[1:], duration=DEMORA[emocion], loop=0,
                    disposal=1, optimize=False)
    quitar_paletas_locales(ruta)
    return ruta


def quitar_paletas_locales(ruta):
    """Pillow repite la paleta global en algunos cuadros; se quitan para que el firmware solo
    tenga que recolorear la global."""
    datos = bytearray(open(ruta, "rb").read())
    tam = 2 << (datos[10] & 0x07)
    glob = bytes(datos[13:13 + tam * 3])
    salida = bytearray(datos[:13 + tam * 3])
    salida[11] = 32   # color de fondo del GIF: el negro de la paleta fija
    i = 13 + tam * 3
    while i < len(datos):
        b = datos[i]
        if b == 0x21:
            j = i + 2
            while datos[j]:
                j += datos[j] + 1
            salida += datos[i:j + 1]
            i = j + 1
        elif b == 0x2C:
            pk = datos[i + 9]
            cabecera = bytearray(datos[i:i + 10])
            j = i + 10
            if pk & 0x80:
                lt = 2 << (pk & 7)
                local = bytes(datos[j:j + lt * 3])
                assert local[:len(glob)] == glob[:len(local)], "paleta local distinta de la global"
                cabecera[9] = pk & ~0x87
                j += lt * 3
            salida += cabecera
            k = j + 1
            while datos[k]:
                k += datos[k] + 1
            salida += datos[j:k + 1]
            i = k + 1
        elif b == 0x3B:
            salida.append(0x3B)
            break
        else:
            raise AssertionError(f"bloque desconocido {b:#x}")
    open(ruta, "wb").write(bytes(salida))


def revisar_gif(ruta):
    """Comprueba que el GIF tenga solo la paleta global de 64 colores con la marca en la 63."""
    datos = open(ruta, "rb").read()
    flags = datos[10]
    assert flags & 0x80, "sin paleta global"
    tam = 2 << (flags & 0x07)
    assert tam == 64, f"paleta de {tam} colores"
    marca = tuple(datos[13 + 63 * 3:13 + 64 * 3])
    assert marca == MARCA, f"marca {marca}"
    # ningun cuadro con paleta local
    i, locales = 13 + tam * 3, 0
    while i < len(datos):
        b = datos[i]
        if b == 0x21:
            i += 2
            while datos[i]:
                i += datos[i] + 1
            i += 1
        elif b == 0x2C:
            if datos[i + 9] & 0x80:
                locales += 1
                i += 10 + (2 << (datos[i + 9] & 7)) * 3
            else:
                i += 10
            i += 1
            while datos[i]:
                i += datos[i] + 1
            i += 1
        elif b == 0x3B:
            break
        else:
            raise AssertionError(f"bloque desconocido {b:#x} en {i}")
    assert locales == 0, f"{locales} cuadros con paleta local"
    return len(datos)


def encabezado_paletas(ruta):
    """paletas_mascotas.h: para cada animal y color, las 32 entradas (0-31) de la paleta."""
    lineas = ["// Generado por generar_mascotas.py: colores de cada mascota de KusiVox.",
              "// Cada paleta reemplaza las entradas 0-31 (pelaje principal y secundario) del GIF.",
              "#pragma once", "#include <cstdint>", "", "namespace kusivox {", "",
              "struct PaletaMascota {", "    const char* animal;", "    int indice;", "    const char* nombre;",
              "    uint8_t rgb[96];", "};", "", "static const uint8_t kMarcaMascota[3] = {%d, %d, %d};" % MARCA, "",
              "static const PaletaMascota kPaletasMascota[] = {"]
    for animal, colores in ANIMALES.items():
        for i, (nombre, P, S) in enumerate(colores):
            valores = []
            for c in rampa(P) + rampa(S):
                valores += list(c)
            lineas.append('    {"%s", %d, "%s", {%s}},' % (animal, i, nombre, ", ".join(map(str, valores))))
    lineas += ["};", "", "}  // namespace kusivox", ""]
    open(ruta, "w", encoding="utf-8").write("\n".join(lineas))


def hoja_contacto(carpeta, animales, destino):
    filas = []
    for animal in animales:
        fila = Image.new("RGB", (LADO * len(EMOCIONES), LADO), (0, 0, 0))
        for i, e in enumerate(EMOCIONES):
            g = Image.open(os.path.join(carpeta, f"{animal}_{e}.gif"))
            g.seek(1)
            fila.paste(g.convert("RGB"), (i * LADO, 0))
        filas.append(fila)
    hoja = Image.new("RGB", (LADO * len(EMOCIONES), LADO * len(filas)))
    for i, f in enumerate(filas):
        hoja.paste(f, (0, i * LADO))
    hoja.save(destino)


if __name__ == "__main__":
    carpeta = sys.argv[1] if len(sys.argv) > 1 else "mascotas"
    animales = sys.argv[2:] or list(ANIMALES)
    os.makedirs(carpeta, exist_ok=True)
    total = 0
    for animal in animales:
        for emocion in EMOCIONES:
            ruta = guardar_gif(animal, emocion, carpeta)
            total += revisar_gif(ruta)
        print(animal, "listo")
    encabezado_paletas(os.path.join(carpeta, "paletas_mascotas.h"))
    hoja_contacto(carpeta, animales, os.path.join(carpeta, "hoja.png"))
    print(f"{len(animales) * len(EMOCIONES)} GIF, {total / 1024:.0f} KB")
