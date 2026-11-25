"""
Genera las 21 animaciones de cuerpo completo de KusiVox (GIF 240x240, fondo negro).

Personaje original: KusiVox como cachorro shih tzu sin ropa, solo con su pelaje blanco y
dorado: copete en la cabeza, orejas largas, bigote y barba blancos y cola esponjosa.
Cada emocion es una animacion corta de 8 cuadros: salta, mueve las patas y la cola,
levanta o baja las orejas y cambia ojos y hocico.

Se dibuja a 3x y se reduce para que los bordes salgan suaves.
Uso: python3 generar_kusi.py [carpeta_salida]
"""

import math
import os
import sys

from PIL import Image, ImageDraw

TAM = 240
S = 3
W = TAM * S
SALIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "gif")

# ------------------------------------------------------------ colores
NEGRO = (0, 0, 0)
BLANCO = (255, 255, 255)
PELO = (250, 246, 238)          # pelaje blanco
PELO_SOMBRA = (214, 204, 190)   # contorno suave sobre lo blanco
DORADO = (226, 172, 96)         # manchas doradas
DORADO_OSCURO = (184, 126, 64)
DORADO_CLARO = (244, 206, 140)
PIEL = DORADO                   # parpados: los ojos estan sobre las manchas doradas
HOCICO = PELO
NARIZ = (36, 24, 28)
CHULLO = (214, 44, 72)
CHULLO_AMARILLO = (252, 198, 58)
CHULLO_BLANCO = (250, 246, 236)
CHULLO_AZUL = (44, 150, 214)
PONCHO = (30, 150, 186)
PONCHO_OSCURO = (22, 110, 140)
FRANJA_1 = (252, 198, 58)
FRANJA_2 = (232, 60, 98)
MANGA = PIEL
PANTALON = (66, 72, 128)
OJOTA = (150, 98, 62)
IRIS_ARRIBA = (176, 118, 66)
IRIS_ABAJO = (70, 38, 20)
PUPILA = (20, 10, 8)
BOCA = (110, 26, 48)
LENGUA = (255, 120, 150)
DIENTES = (255, 255, 255)
MEJILLA = (255, 100, 140)
LAGRIMA = (110, 196, 255)
CORAZON = (255, 70, 120)
ENOJO = (255, 76, 76)
AMARILLO = (255, 222, 90)
CEJA = (70, 40, 34)
LENTES = (20, 22, 30)
CHOCLO = (250, 214, 70)
HOJA = (110, 190, 90)

# Puntos de referencia (coordenadas de 240)
SUELO = 204
CENTRO_CABEZA = (120, 96)
RADIO_CABEZA = 46
CUELLO = (120, 136)
HOMBRO_I = (100, 142)
HOMBRO_D = (140, 142)
CADERA_I = (110, 178)
CADERA_D = (130, 178)


# Orejas y cola segun la emocion: (orejas, angulo de la cola, meneo, rapidez del meneo)
ESTILO_PERRITO = {
    "neutral": ("normal", -50, 10, 1), "happy": ("arriba", -55, 28, 4), "laughing": ("normal", -55, 24, 4),
    "funny": ("normal", -50, 20, 2), "sad": ("caidas", 70, 4, 1), "angry": ("atras", -85, 3, 2),
    "crying": ("caidas", 75, 3, 1), "loving": ("normal", -55, 28, 3), "embarrassed": ("caidas", 35, 8, 1),
    "surprised": ("arriba", -85, 4, 2), "shocked": ("arriba", 100, 2, 4), "thinking": ("normal", -40, 6, 1),
    "winking": ("normal", -55, 20, 2), "cool": ("normal", -45, 8, 1), "relaxed": ("normal", -35, 8, 1),
    "delicious": ("arriba", -55, 24, 3), "kissy": ("normal", -55, 16, 2), "confident": ("arriba", -70, 10, 1),
    "sleepy": ("caidas", 60, 2, 1), "silly": ("normal", -50, 26, 4), "confused": ("normal", -40, 5, 1),
}
EMOCION_ACTUAL = ["neutral"]


def estilo():
    return ESTILO_PERRITO.get(EMOCION_ACTUAL[0], ESTILO_PERRITO["neutral"])


def p(v):
    return int(round(v * S))


def capa():
    return Image.new("RGBA", (W, W), (0, 0, 0, 0))


class Lapiz:
    """Dibuja en coordenadas de 240 sobre una capa de 720."""

    def __init__(self, img):
        self.img = img
        self.d = ImageDraw.Draw(img)

    def elipse(self, cx, cy, rx, ry, color, borde=None, grosor=0):
        self.d.ellipse([p(cx - rx), p(cy - ry), p(cx + rx), p(cy + ry)], fill=color,
                       outline=borde, width=p(grosor) if grosor else 0)

    def circulo(self, cx, cy, r, color):
        self.elipse(cx, cy, r, r, color)

    def poligono(self, puntos, color):
        self.d.polygon([(p(x), p(y)) for x, y in puntos], fill=color)

    def linea(self, puntos, color, grosor, redondo=True):
        pts = [(p(x), p(y)) for x, y in puntos]
        self.d.line(pts, fill=color, width=p(grosor), joint="curve")
        if redondo:
            for x, y in puntos:
                r = grosor / 2
                self.d.ellipse([p(x - r), p(y - r), p(x + r), p(y + r)], fill=color)

    def arco(self, cx, cy, rx, ry, inicio, fin, color, grosor):
        self.d.arc([p(cx - rx), p(cy - ry), p(cx + rx), p(cy + ry)], inicio, fin, fill=color, width=p(grosor))

    def cuerda(self, cx, cy, rx, ry, inicio, fin, color):
        self.d.chord([p(cx - rx), p(cy - ry), p(cx + rx), p(cy + ry)], inicio, fin, fill=color)

    def rect(self, x1, y1, x2, y2, color, radio=0):
        self.d.rounded_rectangle([p(x1), p(y1), p(x2), p(y2)], radius=p(radio), fill=color)


def degradado_circulo(radio_px, arriba, abajo):
    tam = max(2, int(radio_px * 2))
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(tam):
        t = y / max(1, tam - 1)
        color = tuple(int(arriba[i] * (1 - t) + abajo[i] * t) for i in range(3)) + (255,)
        d.line([(0, y), (tam, y)], fill=color)
    mascara = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(mascara).ellipse([0, 0, tam - 1, tam - 1], fill=255)
    img.putalpha(mascara)
    return img


def corazon(l, cx, cy, tam, color):
    r = tam * 0.3
    l.circulo(cx - r * 0.95, cy - r * 0.35, r, color)
    l.circulo(cx + r * 0.95, cy - r * 0.35, r, color)
    l.poligono([(cx - tam * 0.58, cy - r * 0.1), (cx + tam * 0.58, cy - r * 0.1), (cx, cy + tam * 0.6)], color)


def estrella(l, cx, cy, r, color):
    pts = []
    for i in range(8):
        a = math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.32
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    l.poligono(pts, color)


# ------------------------------------------------------------ cara

OJO_I = (103, 99)
OJO_D = (137, 99)


def ojo_abierto(l, cx, cy, mira=(0, 0), escala=1.0, iris=1.0):
    rx, ry = 10 * escala, 13 * escala
    l.elipse(cx, cy, rx, ry, BLANCO)
    ri = 8 * escala * iris
    ix, iy = cx + mira[0], cy + 2 * escala + mira[1]
    circ = degradado_circulo(p(ri), IRIS_ARRIBA, IRIS_ABAJO)
    l.img.alpha_composite(circ, (p(ix - ri), p(iy - ri)))
    rp = 4 * escala * iris
    l.circulo(ix, iy, rp, PUPILA)
    l.circulo(ix - 3 * escala, iy - 4 * escala, 2.6 * escala, BLANCO)
    l.circulo(ix + 2.5 * escala, iy + 2.5 * escala, 1.1 * escala, BLANCO)


def parpado(l, cx, cy, inclinacion, altura, escala=1.0):
    """Tapa la parte de arriba del ojo con piel: altura 0..1, inclinacion en grados."""
    rx, ry = 11 * escala, 14 * escala
    y0 = cy - ry + 2 * ry * altura
    a = math.radians(inclinacion)
    dy = math.tan(a) * rx
    l.poligono([(cx - rx - 2, cy - ry - 4), (cx + rx + 2, cy - ry - 4),
                (cx + rx + 2, y0 + dy), (cx - rx - 2, y0 - dy)], PIEL)
    l.linea([(cx - rx, y0 - dy), (cx + rx, y0 + dy)], CEJA, 2.2)


def ojos(l, tipo, mira=(0, 0), t=0):
    (xi, yi), (xd, yd) = OJO_I, OJO_D
    if tipo == "abierto":
        ojo_abierto(l, xi, yi, mira)
        ojo_abierto(l, xd, yd, mira)
    elif tipo == "grande":
        ojo_abierto(l, xi, yi, mira, escala=1.18, iris=0.7)
        ojo_abierto(l, xd, yd, mira, escala=1.18, iris=0.7)
    elif tipo == "chico":
        ojo_abierto(l, xi, yi, mira, escala=1.2, iris=0.45)
        ojo_abierto(l, xd, yd, mira, escala=1.2, iris=0.45)
    elif tipo == "feliz":
        for x, y in ((xi, yi), (xd, yd)):
            l.arco(x, y + 4, 9, 9, 200, 340, BLANCO, 3.4)
    elif tipo == "cerrado":
        for x, y in ((xi, yi), (xd, yd)):
            l.arco(x, y - 2, 9, 7, 20, 160, BLANCO, 3.0)
    elif tipo == "apretado":
        l.linea([(xi - 8, yi - 6), (xi + 6, yi), (xi - 8, yi + 6)], BLANCO, 3.2)
        l.linea([(xd + 8, yd - 6), (xd - 6, yd), (xd + 8, yd + 6)], BLANCO, 3.2)
    elif tipo == "guino":
        ojo_abierto(l, xi, yi, mira)
        l.arco(xd, yd + 4, 9, 9, 200, 340, BLANCO, 3.4)
    elif tipo == "triste":
        ojo_abierto(l, xi, yi, (0, 3))
        ojo_abierto(l, xd, yd, (0, 3))
        parpado(l, xi, yi, -16, 0.34)
        parpado(l, xd, yd, 16, 0.34)
    elif tipo == "enojado":
        ojo_abierto(l, xi, yi, (0, 1))
        ojo_abierto(l, xd, yd, (0, 1))
        parpado(l, xi, yi, 22, 0.36)
        parpado(l, xd, yd, -22, 0.36)
    elif tipo == "entrecerrado":
        ojo_abierto(l, xi, yi, mira)
        ojo_abierto(l, xd, yd, mira)
        parpado(l, xi, yi, 0, 0.46)
        parpado(l, xd, yd, 0, 0.46)
    elif tipo == "corazon":
        lat = 1.0 + (0.12 if t % 2 else 0)
        corazon(l, xi, yi, 22 * lat, CORAZON)
        corazon(l, xd, yd, 22 * lat, CORAZON)
    elif tipo == "loco":
        ojo_abierto(l, xi, yi, mira, escala=1.2)
        ojo_abierto(l, xd, yd + 2, (-mira[0], -mira[1]), escala=0.8)
    elif tipo == "dormido":
        for x, y in ((xi, yi), (xd, yd)):
            l.arco(x, y + 2, 9, 5, 10, 170, BLANCO, 2.8)


def lentes(l, brillo):
    (xi, yi), (xd, yd) = OJO_I, OJO_D
    l.rect(xi - 14, yi - 9, xi + 13, yi + 10, LENTES, 6)
    l.rect(xd - 13, yd - 9, xd + 14, yd + 10, LENTES, 6)
    l.linea([(xi + 13, yi - 4), (xd - 13, yd - 4)], LENTES, 3)
    l.linea([(xi - 14, yi - 6), (78, yi - 10)], LENTES, 2.4)
    l.linea([(xd + 14, yd - 6), (162, yd - 10)], LENTES, 2.4)
    bx = -6 + brillo * 6
    l.linea([(xi + bx - 3, yi + 6), (xi + bx + 5, yi - 6)], (230, 240, 255), 2.4)
    l.linea([(xd + bx - 3, yd + 6), (xd + bx + 5, yd - 6)], (230, 240, 255), 2.4)


def cejas(l, tipo):
    (xi, yi), (xd, yd) = OJO_I, OJO_D
    y = 83
    if tipo == "triste":
        l.linea([(xi - 9, y + 2), (xi + 7, y - 3)], CEJA, 2.6)
        l.linea([(xd - 7, y - 3), (xd + 9, y + 2)], CEJA, 2.6)
    elif tipo == "enojado":
        l.linea([(xi - 9, y - 3), (xi + 8, y + 4)], CEJA, 3)
        l.linea([(xd - 8, y + 4), (xd + 9, y - 3)], CEJA, 3)
    elif tipo == "arriba":
        l.arco(xi, y, 9, 4, 200, 340, CEJA, 2.6)
        l.arco(xd, y, 9, 4, 200, 340, CEJA, 2.6)
    elif tipo == "duda":
        l.linea([(xi - 9, y + 1), (xi + 8, y + 1)], CEJA, 2.6)
        l.arco(xd, y - 2, 9, 5, 200, 340, CEJA, 2.6)


def boca(l, tipo, t=0):
    """Hocico de perrito: la boca va debajo de la nariz."""
    cx, cy = 120, 127
    if tipo in ("sonrisa", "lengua", "rico", "neutral", "lado", "ondulada"):
        l.linea([(cx, 118), (cx, cy - 5)], NARIZ, 1.8)
    if tipo == "sonrisa":
        l.arco(cx - 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
        l.arco(cx + 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
    elif tipo == "feliz":
        l.cuerda(cx, cy - 6, 11, 9, 0, 180, BOCA)
        l.rect(cx - 5, cy - 2, cx + 5, cy + 9 + (t % 2), LENGUA, 5)
        l.linea([(cx, cy - 1), (cx, cy + 5)], (220, 80, 110), 1.2)
    elif tipo == "risa":
        abre = 11 + (2 if t % 2 else 0)
        l.cuerda(cx, cy - 7, 14, abre, 0, 180, BOCA)
        l.rect(cx - 6, cy - 2, cx + 6, cy + abre - 4, LENGUA, 6)
    elif tipo == "o":
        l.elipse(cx, cy - 1, 4, 4.5, BOCA)
    elif tipo == "O":
        l.elipse(cx, cy, 6 + (t % 2), 7.5 + (t % 2), BOCA)
        l.elipse(cx, cy + 4, 3.5, 2, LENGUA)
    elif tipo == "triste":
        l.arco(cx, cy + 3, 8, 6, 200, 340, NARIZ, 2.6)
    elif tipo == "enojada":
        l.cuerda(cx, cy + 4, 11, 8, 180, 360, BOCA)
        l.rect(cx - 9, cy - 4, cx + 9, cy - 1, DIENTES, 1)
        l.poligono([(cx - 8, cy - 1), (cx - 4.5, cy - 1), (cx - 6.3, cy + 3)], DIENTES)
        l.poligono([(cx + 4.5, cy - 1), (cx + 8, cy - 1), (cx + 6.3, cy + 3)], DIENTES)
    elif tipo == "neutral":
        l.linea([(cx - 6, cy - 4), (cx + 6, cy - 4)], NARIZ, 2.4)
    elif tipo == "lengua":
        l.arco(cx - 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
        l.arco(cx + 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
        mueve = (-2, 2, -2, 2)[t % 4]
        l.rect(cx - 4 + mueve, cy - 3, cx + 4 + mueve, cy + 10, LENGUA, 4)
    elif tipo == "beso":
        l.arco(cx + 1, cy - 4, 3.5, 3, 270, 90, BOCA, 2.4)
        l.arco(cx + 1, cy + 1, 3.5, 3, 270, 90, BOCA, 2.4)
    elif tipo == "lado":
        l.linea([(cx - 7, cy - 3), (cx + 2, cy - 3), (cx + 8, cy - 7)], NARIZ, 2.4)
    elif tipo == "ondulada":
        pts = [(cx - 9 + i, cy - 3 + 1.8 * math.sin(i * 0.8 + t)) for i in range(0, 19, 2)]
        l.linea(pts, NARIZ, 2.2)
    elif tipo == "bostezo":
        l.elipse(cx, cy, 6 + (t % 3), 7 + 2 * (t % 3), BOCA)
    elif tipo == "rico":
        l.arco(cx - 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
        l.arco(cx + 5, cy - 6, 5, 4.5, 10, 170, NARIZ, 2.4)
        x = cx + (-7, -3, 2, 7, 2, -3, -7, -3)[t % 8]
        l.elipse(x, cy - 1, 4, 3.5, LENGUA)


def mejillas(l, fuerza=1.0):
    color = MEJILLA + (int(150 * fuerza),)
    capa_m = capa()
    lm = Lapiz(capa_m)
    lm.elipse(90, 112, 8, 4.5, color)
    lm.elipse(150, 112, 8, 4.5, color)
    l.img.alpha_composite(capa_m)


def rubor_lineas(l):
    for x0 in (88, 140):
        for k in range(3):
            l.linea([(x0 + k * 5, 115), (x0 + k * 5 + 3, 109)], (255, 70, 110), 1.6)


# ------------------------------------------------------------ cabeza y chullo

ANGULO_OREJAS = {"normal": 4, "arriba": 40, "caidas": -5, "atras": 22}


def oreja(img, lado, angulo):
    """Oreja larga y peluda de shih tzu; gira hacia afuera desde arriba de la cabeza."""
    ax, ay = 120 + lado * 44, 84
    capa_o = capa()
    lo = Lapiz(capa_o)
    lo.elipse(ax, ay + 22, 11, 25, DORADO)
    for k in (-6, 0, 6):
        lo.circulo(ax + k, ay + 44 + (2 if k == 0 else 0), 5.5, DORADO)
    for k in (-4, 0, 4):
        lo.linea([(ax + k, ay + 18), (ax + k * 1.3, ay + 42)], DORADO_OSCURO, 1.3)
    capa_o = capa_o.rotate(lado * angulo, resample=Image.BICUBIC, center=(p(ax), p(ay)))
    img.alpha_composite(capa_o)


def copete(l, t):
    """Mono de pelo dorado sobre la cabeza (sin lazo: solo pelaje)."""
    vaiven = (0, 1, 2, 1, 0, -1, -2, -1)[t % 8]
    x = 120 + vaiven
    for dx in (-7, 0, 7):
        l.linea([(x, 38), (x + dx * 1.2, 27 + abs(dx) * 0.6)], DORADO_CLARO, 3)
    l.circulo(x - 8, 53, 8, DORADO)
    l.circulo(x + 8, 53, 8, DORADO)
    l.circulo(x, 45, 10.5, DORADO)
    l.arco(x - 2, 44, 5, 4, 200, 300, DORADO_CLARO, 1.6)
    l.linea([(x - 4, 47), (x - 3, 56)], DORADO_OSCURO, 1.3)
    l.linea([(x + 4, 47), (x + 3, 56)], DORADO_OSCURO, 1.3)


def cabeza(t, cara):
    """Dibuja la cabeza del shih tzu en una capa propia (luego se inclina)."""
    img = capa()
    l = Lapiz(img)
    cx, cy = CENTRO_CABEZA
    l.circulo(cx, cy, 47, PELO)
    l.cuerda(cx, 88, 46, 38, 180, 360, DORADO)
    l.elipse(103, 99, 14.5, 13.5, DORADO)
    l.elipse(137, 99, 14.5, 13.5, DORADO)
    l.elipse(cx, 86, 6, 15, PELO)
    l.elipse(cx, 137, 17, 9, PELO)
    l.elipse(109, 123, 11, 8, PELO)
    l.elipse(131, 123, 11, 8, PELO)
    l.elipse(cx, 114, 7.5, 5.5, NARIZ)
    l.circulo(cx - 2.5, 112.5, 1.8, (200, 190, 200))
    if cara.get("cejas"):
        cejas(l, cara["cejas"])
    if cara.get("lentes") is not None:
        lentes(l, cara["lentes"])
    else:
        ojos(l, cara.get("ojos", "abierto"), cara.get("mira", (0, 0)), t)
    mejillas(l, cara.get("mejillas", 0.8))
    if cara.get("rubor"):
        rubor_lineas(l)
    boca(l, cara.get("boca", "sonrisa"), t)
    base = ANGULO_OREJAS[cara.get("orejas", estilo()[0])]
    vaiven = (0, 3, 5, 3, 0, -3, -5, -3)[t % 8] * cara.get("mueve_orejas", 0.6)
    oreja(img, -1, base + vaiven)
    oreja(img, 1, base - vaiven)
    l = Lapiz(img)
    copete(l, t)
    for extra in cara.get("extras", []):
        extra(l)
    return img


# ------------------------------------------------------------ cuerpo

def piernas(l, pose):
    pi, pd = pose
    for (cx, cy), (fx, fy) in ((CADERA_I, pi), (CADERA_D, pd)):
        l.linea([(cx, cy), (fx, fy - 4)], PELO, 15)
        dx = -3 if fx < 120 else 3
        l.elipse(fx + dx, fy, 10.5, 6, PELO)
        for k in (-4, 0, 4):
            l.linea([(fx + k + dx, fy + 1), (fx + k + dx, fy + 5)], PELO_SOMBRA, 1.2, redondo=False)


def cola(l, angulo):
    """Cola esponjosa de shih tzu: un penacho que se curva sobre la espalda."""
    bx, by = 140, 160
    a = math.radians(angulo)
    b = math.radians(angulo + 40)
    punta = (bx + 34 * math.cos(a), by + 34 * math.sin(a))
    control = (bx + 22 * math.cos(b), by + 22 * math.sin(b))
    for i in range(9):
        u = i / 8
        x = (1 - u) ** 2 * bx + 2 * (1 - u) * u * control[0] + u ** 2 * punta[0]
        y = (1 - u) ** 2 * by + 2 * (1 - u) * u * control[1] + u ** 2 * punta[1]
        l.circulo(x, y, 8.5 - u * 2, DORADO if i < 7 else PELO)


def cuerpo_peludo(l, ancho=1.0):
    """Cuerpo esponjoso: pecho blanco, manchas doradas a los lados y flecos de pelo abajo."""
    cx = 120
    l.elipse(cx, 158, 31 * ancho, 28, PELO)
    l.elipse(cx - 24 * ancho, 152, 9, 15, DORADO)
    l.elipse(cx + 24 * ancho, 152, 9, 15, DORADO)
    for i in range(-3, 4):
        l.circulo(cx + i * 8.5 * ancho, 182 + (1 if i % 2 else 0), 7, PELO)
    for x, y in ((112, 146), (126, 150), (118, 162), (130, 166), (108, 168)):
        l.arco(x, y, 5, 3, 20, 160, PELO_SOMBRA, 1.2)


def brazo(l, hombro, codo, mano):
    l.linea([hombro, codo, mano], PELO_SOMBRA, 13)
    l.linea([hombro, codo, mano], PELO, 10.4)
    l.circulo(mano[0], mano[1], 7.6, PELO_SOMBRA)
    l.circulo(mano[0], mano[1], 6.6, PELO)


def mover(img, dx=0, dy=0, sx=1.0, sy=1.0, ancla=(120, SUELO)):
    """Desplaza y estira la capa del personaje con ancla en los pies."""
    if sx != 1.0 or sy != 1.0:
        nw, nh = int(W * sx), int(W * sy)
        img = img.resize((nw, nh), Image.LANCZOS)
        ax, ay = p(ancla[0]), p(ancla[1])
        ox, oy = int(ax - ax * sx), int(ay - ay * sy)
    else:
        ox = oy = 0
    out = capa()
    out.alpha_composite(img, (ox + p(dx), oy + p(dy))) if (ox + p(dx) >= 0 and oy + p(dy) >= 0) else \
        out.paste(img, (ox + p(dx), oy + p(dy)), img)
    return out


def personaje(t, pose):
    """pose: dict con dy, sx, sy, inclina, brazo_i/brazo_d ((codo),(mano)), piernas, cara, frente."""
    img = capa()
    l = Lapiz(img)
    pie_i, pie_d = pose.get("piernas", ((108, SUELO), (132, SUELO)))
    _, cola_base, cola_menea, cola_rapidez = estilo()
    menea = pose.get("menea", cola_menea)
    angulo_cola = pose.get("cola", cola_base) + menea * math.sin(t / 8 * 2 * math.pi * pose.get("rapidez", cola_rapidez))
    cola(l, angulo_cola)
    piernas(l, (pie_i, pie_d))
    cuerpo_peludo(l, pose.get("ancho", 1.0))
    bi = pose.get("brazo_i", ((92, 158), (90, 172)))
    bd = pose.get("brazo_d", ((148, 158), (150, 172)))
    atras = pose.get("brazos_atras", False)
    if not pose.get("frente_i"):
        brazo(l, HOMBRO_I, *bi)
    if not pose.get("frente_d"):
        brazo(l, HOMBRO_D, *bd)
    cab = cabeza(t, pose.get("cara", {}))
    ang = pose.get("inclina", 0)
    if ang:
        cab = cab.rotate(ang, resample=Image.BICUBIC, center=(p(CUELLO[0]), p(CUELLO[1])))
    hy = pose.get("cabeza_dy", 0)
    if hy:
        cab = mover(cab, 0, hy)
    img.alpha_composite(cab)
    if pose.get("frente_i"):
        brazo(l, HOMBRO_I, *bi)
    if pose.get("frente_d"):
        brazo(l, HOMBRO_D, *bd)
    for objeto in pose.get("objetos", []):
        objeto(l, t)
    return mover(img, pose.get("dx", 0), pose.get("dy", 0), pose.get("sx", 1.0), pose.get("sy", 1.0))


def cuadro(t, pose, efectos=()):
    base = Image.new("RGBA", (W, W), NEGRO + (255,))
    l = Lapiz(base)
    alto = -pose.get("dy", 0)
    ancho_sombra = max(16, 34 - alto * 0.8)
    l.elipse(120 + pose.get("dx", 0), SUELO + 3, ancho_sombra, 4, (40, 44, 60))
    base.alpha_composite(personaje(t, pose))
    lb = Lapiz(base)
    for efecto in efectos:
        efecto(lb, t)
    return base


# ------------------------------------------------------------ efectos

def ef_destellos(l, t):
    for i, (x, y, r) in enumerate(((52, 70, 7), (190, 60, 9), (200, 140, 6), (44, 150, 6))):
        if (t + i) % 2 == 0:
            estrella(l, x, y, r, AMARILLO)


def ef_corazones(l, t):
    for i, x in enumerate((50, 190, 70, 176)):
        fase = (t + i * 2) % 8
        y = 170 - fase * 16
        if 24 < y < 180:
            corazon(l, x + 3 * math.sin(fase), y, 14 - fase * 0.6, CORAZON)


def ef_zzz(l, t):
    for k in range(3):
        fase = (t + k * 3) % 8
        x, y = 160 + k * 10 + fase * 2, 80 - k * 12 - fase * 3
        tam = 7 + k * 3
        if y > 30:
            l.linea([(x, y), (x + tam, y), (x, y + tam), (x + tam, y + tam)], (200, 220, 255), 2.2)


def ef_interrogacion(l, t):
    y = 40 + (2 if t % 2 else 0)
    l.arco(186, y, 9, 9, 180, 90, AMARILLO, 3.6)
    l.linea([(195, y), (186, y + 10), (186, y + 15)], AMARILLO, 3.6)
    l.circulo(186, y + 23, 2.6, AMARILLO)
    if t % 4 < 2:
        l.arco(52, 54, 6, 6, 180, 90, AMARILLO, 2.6)
        l.linea([(58, 54), (52, 60), (52, 63)], AMARILLO, 2.6)
        l.circulo(52, 69, 2, AMARILLO)


def ef_exclamacion(l, t):
    for x, y in ((188, 44), (52, 52)):
        dy = (0, -3)[t % 2]
        l.linea([(x, y + dy), (x, y + 18 + dy)], ENOJO if x > 100 else AMARILLO, 4.4)
        l.circulo(x, y + 26 + dy, 2.8, ENOJO if x > 100 else AMARILLO)


def ef_vapor(l, t):
    for lado in (-1, 1):
        fase = t % 4
        x = 120 + lado * (58 + fase * 3)
        y = 50 - fase * 6
        l.elipse(x, y, 7 + fase, 5 + fase, (200, 200, 210))
        l.elipse(x + lado * 6, y - 6, 5 + fase * 0.5, 4 + fase * 0.5, (170, 170, 180))


def ef_nubes_pensar(l, t):
    l.circulo(164, 74, 3, BLANCO)
    l.circulo(174, 62, 5, BLANCO)
    l.elipse(198, 44, 26, 16, BLANCO)
    for i in range(3):
        color = PUPILA if i <= t % 4 else (190, 190, 200)
        l.circulo(186 + i * 12, 44, 3.4, color)


def ef_notas(l, t):
    for i, x in enumerate((48, 186)):
        fase = (t + i * 3) % 6
        y = 90 - fase * 9
        l.circulo(x, y, 5, AMARILLO)
        l.linea([(x + 4, y), (x + 4, y - 18), (x + 12, y - 14)], AMARILLO, 2.4)


def ef_ja(l, t):
    for i, (x, y) in enumerate(((40, 60), (176, 46))):
        if (t + i) % 2 == 0:
            # "JA" dibujado con lineas
            l.linea([(x + 8, y), (x + 8, y + 14), (x + 4, y + 18), (x, y + 14)], AMARILLO, 3)
            l.linea([(x + 14, y + 18), (x + 20, y), (x + 26, y + 18)], AMARILLO, 3)
            l.linea([(x + 16, y + 11), (x + 24, y + 11)], AMARILLO, 3)


def ef_rayos(l, t):
    for i, (x, y) in enumerate(((44, 70), (196, 70), (60, 40), (180, 36))):
        if (t + i) % 2 == 0:
            l.linea([(x, y), (x + 6, y + 10), (x - 2, y + 12), (x + 4, y + 22)], AMARILLO, 3)


def ef_lluvia(l, t):
    l.elipse(190, 58, 26, 11, (120, 130, 150))
    l.elipse(174, 62, 14, 9, (120, 130, 150))
    l.elipse(206, 62, 14, 9, (120, 130, 150))
    for i in range(4):
        x = 176 + i * 10
        y = 72 + ((t * 6 + i * 9) % 26)
        l.linea([(x, y), (x - 2, y + 7)], LAGRIMA, 2)


def ef_gotas_sudor(l, t):
    y = 64 + (t % 4) * 3
    l.poligono([(166, y - 8), (161, y + 2), (171, y + 2)], LAGRIMA)
    l.circulo(166, y + 2, 5, LAGRIMA)


def ef_beso(l, t):
    fase = t % 8
    corazon(l, 160 + fase * 6, 104 - fase * 9, 10 + fase, CORAZON)


def ef_brillo_lentes(l, t):
    if t % 4 == 1:
        estrella(l, 146, 92, 9, BLANCO)


def ef_estrellitas(l, t):
    for i, (x, y) in enumerate(((44, 100), (196, 104))):
        if (t + i) % 2:
            estrella(l, x, y, 6, AMARILLO)


# ------------------------------------------------------------ objetos

def obj_corazon_manos(l, t):
    corazon(l, 120, 154, 26 + (3 if t % 2 else 0), CORAZON)


def obj_hueso(l, t):
    dy = -2 if t % 2 else 0
    for color, extra in (((150, 118, 84), 1.6), ((250, 222, 170), 0)):
        l.linea([(142, 142 + dy), (162, 122 + dy)], color, 6 + extra * 2)
        for x, y in ((142, 142), (162, 122)):
            l.circulo(x - 3, y + dy + 1, 4 + extra, color)
            l.circulo(x + 1, y + dy + 3, 4 + extra, color)


def obj_lagrimas(lado_y=108):
    def f(l, t):
        for x in (OJO_I[0] - 6, OJO_D[0] + 6):
            for k in range(2):
                y = lado_y + ((t * 7 + k * 14) % 28)
                l.poligono([(x, y - 4), (x - 3, y + 2), (x + 3, y + 2)], LAGRIMA)
                l.circulo(x, y + 2, 3, LAGRIMA)
    return f


def lagrima_quieta(l):
    l.poligono([(OJO_D[0] + 8, 110), (OJO_D[0] + 5, 117), (OJO_D[0] + 11, 117)], LAGRIMA)
    l.circulo(OJO_D[0] + 8, 117, 3, LAGRIMA)


# ------------------------------------------------------------ poses base

def reposo(t, cara, **extra):
    b = math.sin(t / 8 * 2 * math.pi)
    pose = {
        "dy": -1.2 * (b + 1) / 2,
        "brazo_i": ((92, 158), (90 - b, 172)),
        "brazo_d": ((148, 158), (150 + b, 172)),
        "cara": cara,
    }
    pose.update(extra)
    return pose


def saltar(t, altura=14):
    fase = t / 8 * 2 * math.pi
    s = max(0.0, math.sin(fase))
    dy = -altura * s
    aplasta = 1.0 if s > 0.15 else 0.94
    return dy, aplasta


# ------------------------------------------------------------ emociones (8 cuadros)

def e_neutral():
    cuadros = []
    for t in range(8):
        cara = {"ojos": "cerrado" if t == 5 else "abierto", "boca": "sonrisa",
                "mira": ((-3, 0), (-3, 0), (0, 0), (3, 0), (3, 0), (0, 0), (0, 0), (0, 0))[t]}
        cuadros.append((cuadro(t, reposo(t, cara)), 160))
    return cuadros


def e_happy():
    cuadros = []
    for t in range(8):
        dy, sy = saltar(t, 16)
        arriba = dy < -4
        pose = {"dy": dy, "sy": sy, "sx": 2 - sy,
                "brazo_i": ((84, 130), (78, 112)) if arriba else ((86, 148), (78, 136)),
                "brazo_d": ((156, 130), (162, 112)) if arriba else ((154, 148), (162, 136)),
                "piernas": ((104, SUELO - 2), (136, SUELO - 2)) if arriba else ((108, SUELO), (132, SUELO)),
                "cara": {"ojos": "feliz", "boca": "feliz", "mejillas": 1.0}}
        cuadros.append((cuadro(t, pose, (ef_destellos,)), 110))
    return cuadros


def e_laughing():
    cuadros = []
    for t in range(8):
        dy = -4 if t % 2 else 0
        pose = {"dy": dy, "inclina": (-6, 6)[t % 2],
                "brazo_i": ((94, 160), (110, 164)), "brazo_d": ((146, 160), (130, 164)), "frente_i": True, "frente_d": True,
                "cara": {"ojos": "apretado", "boca": "risa", "mejillas": 1.0}}
        cuadros.append((cuadro(t, pose, (ef_ja,)), 110))
    return cuadros


def e_funny():
    cuadros = []
    for t in range(8):
        lado = math.sin(t / 8 * 2 * math.pi)
        pose = {"dx": 6 * lado, "inclina": -10 * lado,
                "brazo_i": ((86, 146), (80, 130 + 8 * lado)), "brazo_d": ((154, 146), (160, 130 - 8 * lado)),
                "piernas": ((106 + 3 * lado, SUELO), (134 + 3 * lado, SUELO - 3 * max(0, lado))),
                "cara": {"ojos": "guino" if t in (2, 3) else "feliz", "boca": "lengua", "mejillas": 1.0}}
        cuadros.append((cuadro(t, pose, (ef_estrellitas,)), 120))
    return cuadros


def e_sad():
    cuadros = []
    for t in range(8):
        b = math.sin(t / 8 * 2 * math.pi)
        pose = {"dy": 3, "inclina": 6 + b, "cabeza_dy": 3,
                "brazo_i": ((96, 160), (98, 178)), "brazo_d": ((144, 160), (142, 178)),
                "cara": {"ojos": "triste", "cejas": "triste", "boca": "triste", "mejillas": 0.4,
                         "chullo_caido": True, "extras": [lagrima_quieta] if t >= 4 else []}}
        cuadros.append((cuadro(t, pose, (ef_lluvia,)), 160))
    return cuadros


def e_angry():
    cuadros = []
    for t in range(8):
        pisa = t % 2
        pose = {"dy": 0, "dx": (-1, 1)[t % 2],
                "brazo_i": ((88, 156), (84, 146)), "brazo_d": ((152, 156), (156, 146)),
                "piernas": ((108, SUELO - 8 * pisa), (132, SUELO - 8 * (1 - pisa))),
                "cara": {"ojos": "enojado", "cejas": "enojado", "boca": "enojada", "mejillas": 1.2}}
        cuadros.append((cuadro(t, pose, (ef_vapor,)), 110))
    return cuadros


def e_crying():
    cuadros = []
    for t in range(8):
        sollozo = -3 if t % 2 else 0
        pose = {"dy": sollozo, "inclina": (-3, 3)[t % 2],
                "brazo_i": ((96, 140), (102, 112)), "brazo_d": ((144, 140), (138, 112)), "frente_i": True, "frente_d": True,
                "cara": {"ojos": "apretado", "boca": "O", "mejillas": 0.6, "chullo_caido": True}}
        cuadros.append((cuadro(t, pose, (obj_lagrimas(108),)), 140))
    return cuadros


def e_loving():
    cuadros = []
    for t in range(8):
        b = math.sin(t / 8 * 2 * math.pi)
        pose = {"dy": -2 * (b + 1), "inclina": 5 * b,
                "brazo_i": ((100, 162), (112, 154)), "brazo_d": ((140, 162), (128, 154)), "frente_i": True, "frente_d": True,
                "objetos": [obj_corazon_manos],
                "cara": {"ojos": "corazon", "boca": "feliz", "mejillas": 1.2}}
        cuadros.append((cuadro(t, pose, (ef_corazones,)), 130))
    return cuadros


def e_embarrassed():
    cuadros = []
    for t in range(8):
        b = math.sin(t / 8 * 2 * math.pi)
        pose = {"dx": 3 * b, "inclina": 8 + 3 * b,
                "brazo_i": ((98, 134), (100, 118)), "brazo_d": ((142, 134), (140, 118)), "frente_i": True, "frente_d": True,
                "piernas": ((112, SUELO), (128, SUELO)),
                "cara": {"ojos": "cerrado" if t % 4 == 3 else "abierto", "mira": (0, 4), "boca": "ondulada",
                         "mejillas": 1.6, "rubor": True}}
        cuadros.append((cuadro(t, pose, (ef_gotas_sudor,)), 140))
    return cuadros


def e_surprised():
    cuadros = []
    for t in range(8):
        salto = (0, -10, -14, -8, -2, 0, 0, 0)[t]
        pose = {"dy": salto,
                "brazo_i": ((82, 128), (74, 110)), "brazo_d": ((158, 128), (166, 110)),
                "cara": {"ojos": "grande", "cejas": "arriba", "boca": "O", "mejillas": 0.6}}
        cuadros.append((cuadro(t, pose, (ef_exclamacion,)), 110))
    return cuadros


def e_shocked():
    cuadros = []
    for t in range(8):
        tiembla = (-2, 2, -1, 1, -2, 2, -1, 1)[t]
        pose = {"dx": tiembla, "sy": 1.04,
                "brazo_i": ((86, 128), (96, 104)), "brazo_d": ((154, 128), (144, 104)), "frente_i": True, "frente_d": True,
                "cara": {"ojos": "chico", "cejas": "arriba", "boca": "O", "mejillas": 0.2}}
        cuadros.append((cuadro(t, pose, (ef_rayos,)), 90))
    return cuadros


def e_thinking():
    cuadros = []
    for t in range(8):
        b = math.sin(t / 8 * 2 * math.pi)
        pose = {"inclina": -8 + 2 * b,
                "brazo_i": ((92, 160), (106, 162)),
                "brazo_d": ((146, 150), (128, 132)), "frente_i": True, "frente_d": True,
                "cara": {"ojos": "abierto", "mira": (4, -5), "cejas": "duda", "boca": "lado", "mejillas": 0.7}}
        cuadros.append((cuadro(t, pose, (ef_nubes_pensar,)), 180))
    return cuadros


def e_winking():
    cuadros = []
    for t in range(8):
        guina = t in (2, 3, 4)
        pose = {"inclina": -6 if guina else 0, "dy": -2 if guina else 0,
                "brazo_i": ((92, 158), (90, 172)),
                "brazo_d": ((158, 136), (166, 118 + (3 if t % 2 else 0))),
                "objetos": [lambda l, t: estrella(l, 170, 108, 6, AMARILLO) if t in (3, 4) else None],
                "cara": {"ojos": "guino" if guina else "abierto", "boca": "feliz" if guina else "sonrisa"}}
        cuadros.append((cuadro(t, pose), 150))
    return cuadros


def e_cool():
    cuadros = []
    for t in range(8):
        asiente = (0, 2, 0, 2, 0, 2, 0, 2)[t]
        pose = {"cabeza_dy": asiente, "dy": 0,
                "brazo_i": ((100, 160), (132, 158)), "brazo_d": ((140, 162), (108, 160)), "frente_i": True, "frente_d": True,
                "cara": {"lentes": t % 4, "boca": "lado", "mejillas": 0.5}}
        cuadros.append((cuadro(t, pose, (ef_brillo_lentes,)), 150))
    return cuadros


def e_relaxed():
    cuadros = []
    for t in range(8):
        b = math.sin(t / 8 * 2 * math.pi)
        pose = {"inclina": 6 * b, "dx": 2 * b,
                "brazo_i": ((92, 124), (108, 72)), "brazo_d": ((148, 124), (132, 72)),
                "cara": {"ojos": "cerrado", "boca": "sonrisa", "mejillas": 0.9}}
        cuadros.append((cuadro(t, pose, (ef_notas,)), 170))
    return cuadros


def e_delicious():
    cuadros = []
    for t in range(8):
        pose = {"dy": -2 if t % 4 in (1, 2) else 0,
                "brazo_i": ((92, 158), (100, 162)), "brazo_d": ((150, 150), (152, 142)), "frente_d": True,
                "objetos": [obj_hueso],
                "cara": {"ojos": "feliz", "boca": "rico", "mejillas": 1.1}}
        cuadros.append((cuadro(t, pose, (ef_estrellitas,)), 130))
    return cuadros


def e_kissy():
    cuadros = []
    for t in range(8):
        manda = t >= 3
        pose = {"inclina": -4 if manda else 2,
                "brazo_d": ((150, 140), (156, 116)) if manda else ((140, 146), (128, 122)), "frente_d": True,
                "cara": {"ojos": "guino" if manda else "cerrado", "boca": "beso", "mejillas": 1.2}}
        efectos = (ef_beso,) if manda else ()
        cuadros.append((cuadro(t, pose, efectos), 140))
    return cuadros


def e_confident():
    cuadros = []
    for t in range(8):
        pose = {"dy": -1 if t % 2 else 0, "sy": 1.02, "ancho": 1.04, "inclina": -5,
                "brazo_i": ((86, 152), (100, 170)), "brazo_d": ((154, 152), (140, 170)),
                "piernas": ((104, SUELO), (136, SUELO)),
                "cara": {"ojos": "entrecerrado", "mira": (3, 0), "boca": "lado", "cejas": "duda", "mejillas": 0.6}}
        cuadros.append((cuadro(t, pose, (ef_destellos,)), 160))
    return cuadros


def e_sleepy():
    cuadros = []
    for t in range(8):
        cabeceo = (0, 2, 4, 6, 8, 6, 3, 1)[t]
        pose = {"inclina": 4 + cabeceo, "cabeza_dy": cabeceo * 0.5, "dy": 2,
                "brazo_i": ((96, 160), (98, 176)), "brazo_d": ((144, 160), (142, 176)),
                "cara": {"ojos": "dormido", "boca": "bostezo" if t in (2, 3, 4) else "o", "mejillas": 0.7,
                         "chullo_caido": True}}
        cuadros.append((cuadro(t, pose, (ef_zzz,)), 190))
    return cuadros


def e_silly():
    cuadros = []
    for t in range(8):
        lado = (-1, 1)[t % 2]
        pose = {"dy": (-6, 0)[t % 2], "inclina": 10 * lado,
                "brazo_i": ((84, 134), (72, 120 + 6 * lado)), "brazo_d": ((156, 134), (168, 120 - 6 * lado)),
                "piernas": ((102, SUELO - (6 if lado < 0 else 0)), (138, SUELO - (6 if lado > 0 else 0))),
                "cara": {"ojos": "loco", "mira": (3 * lado, -2), "boca": "lengua", "mejillas": 1.0}}
        cuadros.append((cuadro(t, pose, (ef_estrellitas,)), 120))
    return cuadros


def e_confused():
    cuadros = []
    for t in range(8):
        rasca = (0, 3, 0, 3, 0, 3, 0, 3)[t]
        pose = {"inclina": 10,
                "brazo_d": ((176, 112), (156 - rasca, 62)), "frente_d": True,
                "cara": {"ojos": "abierto", "mira": ((-3, -3), (3, -3))[t // 4 % 2], "cejas": "duda", "boca": "ondulada",
                         "mejillas": 0.6}}
        cuadros.append((cuadro(t, pose, (ef_interrogacion,)), 150))
    return cuadros


EMOCIONES = {
    "neutral": e_neutral, "happy": e_happy, "laughing": e_laughing, "funny": e_funny,
    "sad": e_sad, "angry": e_angry, "crying": e_crying, "loving": e_loving,
    "embarrassed": e_embarrassed, "surprised": e_surprised, "shocked": e_shocked,
    "thinking": e_thinking, "winking": e_winking, "cool": e_cool, "relaxed": e_relaxed,
    "delicious": e_delicious, "kissy": e_kissy, "confident": e_confident, "sleepy": e_sleepy,
    "silly": e_silly, "confused": e_confused,
}


ESCALA = 0.94     # deja libre la barra de estado de arriba
ANCLA_Y = 212


def reducir(img):
    rgb = img.convert("RGB")
    lado = int(W * ESCALA)
    chico = rgb.resize((lado, lado), Image.LANCZOS)
    fondo = Image.new("RGB", (W, W), NEGRO)
    ox = int(p(120) - p(120) * ESCALA)
    oy = int(p(ANCLA_Y) - p(ANCLA_Y) * ESCALA)
    fondo.paste(chico, (ox, oy))
    return fondo.resize((TAM, TAM), Image.LANCZOS)


def guardar_gif(nombre, cuadros):
    imgs = [reducir(c) for c, _ in cuadros]
    tiempos = [ms for _, ms in cuadros]
    mosaico = Image.new("RGB", (TAM * len(imgs), TAM))
    for i, im in enumerate(imgs):
        mosaico.paste(im, (i * TAM, 0))
    paleta = mosaico.quantize(colors=96, method=Image.Quantize.MEDIANCUT)
    cuadros_p = [im.quantize(palette=paleta, dither=Image.Dither.NONE) for im in imgs]
    ruta = os.path.join(SALIDA, f"{nombre}.gif")
    cuadros_p[0].save(ruta, save_all=True, append_images=cuadros_p[1:], duration=tiempos, loop=0,
                      optimize=False, disposal=1)
    return ruta, imgs


if __name__ == "__main__":
    os.makedirs(SALIDA, exist_ok=True)
    total = 0
    for nombre, funcion in EMOCIONES.items():
        EMOCION_ACTUAL[0] = nombre
        ruta, _ = guardar_gif(nombre, funcion())
        tam = os.path.getsize(ruta)
        total += tam
        print(f"{nombre:12} {tam / 1024:6.1f} KB")
    print(f"total        {total / 1024:6.1f} KB")
