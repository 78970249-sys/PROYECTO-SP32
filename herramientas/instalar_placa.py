#!/usr/bin/env python3
"""
instalar_placa.py
-----------------
Agrega la placa "asistente-escritorio-uc" a una copia local del proyecto
xiaozhi-esp32, para poder compilar el firmware con los 3 LEDs controlados
por voz (MCP).

Hace tres cosas (y se puede ejecutar varias veces sin duplicar nada):
  1. Copia la carpeta firmware/asistente-escritorio-uc a main/boards/.
  2. Agrega la opcion BOARD_TYPE_ASISTENTE_ESCRITORIO_UC en main/Kconfig.projbuild.
  3. Agrega la rama correspondiente en main/CMakeLists.txt.

Uso (desde la terminal de ESP-IDF):
    python instalar_placa.py RUTA_A_xiaozhi-esp32

Ejemplo en Windows:
    python C:\\proyectos\\PROYECTO-SP32\\herramientas\\instalar_placa.py C:\\proyectos\\xiaozhi-esp32
"""
import shutil
import sys
from pathlib import Path

BOARD_DIR = "asistente-escritorio-uc"
SYMBOL = "BOARD_TYPE_ASISTENTE_ESCRITORIO_UC"

KCONFIG_ENTRY = [
    f"    config {SYMBOL}",
    '        bool "Asistente Escritorio UC (ESP32-S3 + LEDs MCP)"',
    "        depends on IDF_TARGET_ESP32S3",
]

CMAKE_ENTRY = [
    f"elseif(CONFIG_{SYMBOL})",
    f'    set(BOARD_DIR "{BOARD_DIR}")',
    "    set(BUILTIN_TEXT_FONT font_noto_sans_basic_14_1)",
    "    set(BUILTIN_ICON_FONT font_material_symbols_14_1)",
]


def read_lines(path: Path):
    """Lee el archivo conservando su tipo de salto de línea (LF o CRLF)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.split(newline), newline


def write_lines(path: Path, lines, newline: str):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(newline.join(lines))


def patch_kconfig(path: Path) -> str:
    lines, nl = read_lines(path)
    if any(line.strip() == f"config {SYMBOL}" for line in lines):
        return "ya estaba agregada"
    # Se inserta justo después de la placa "bread-compact-wifi" (misma familia)
    for i, line in enumerate(lines):
        if line.strip() == "config BOARD_TYPE_BREAD_COMPACT_WIFI":
            j = i + 1
            while j < len(lines) and lines[j].strip() and not lines[j].strip().startswith("config "):
                j += 1
            lines[j:j] = KCONFIG_ENTRY
            write_lines(path, lines, nl)
            return "agregada"
    raise SystemExit("ERROR: no se encontró 'config BOARD_TYPE_BREAD_COMPACT_WIFI' en Kconfig.projbuild")


def patch_cmake(path: Path) -> str:
    lines, nl = read_lines(path)
    if any(f"CONFIG_{SYMBOL})" in line for line in lines):
        return "ya estaba agregada"
    # Se inserta antes de la rama que sigue a la de "bread-compact-wifi"
    for i, line in enumerate(lines):
        if line.strip() == 'set(BOARD_DIR "bread-compact-wifi")':
            j = i + 1
            while j < len(lines) and not lines[j].lstrip().startswith(("elseif(", "endif(", "else(")):
                j += 1
            if j >= len(lines):
                break
            lines[j:j] = CMAKE_ENTRY
            write_lines(path, lines, nl)
            return "agregada"
    raise SystemExit('ERROR: no se encontró set(BOARD_DIR "bread-compact-wifi") en main/CMakeLists.txt')


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)

    xiaozhi = Path(sys.argv[1]).resolve()
    kconfig = xiaozhi / "main" / "Kconfig.projbuild"
    cmake = xiaozhi / "main" / "CMakeLists.txt"
    boards = xiaozhi / "main" / "boards"
    if not (kconfig.is_file() and cmake.is_file() and boards.is_dir()):
        raise SystemExit(f"ERROR: {xiaozhi} no parece ser la carpeta de xiaozhi-esp32")

    source = Path(__file__).resolve().parent.parent / "firmware" / BOARD_DIR
    if not source.is_dir():
        raise SystemExit(f"ERROR: no se encontró la carpeta {source}")

    destination = boards / BOARD_DIR
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f"[1/3] Placa copiada en {destination}")
    print(f"[2/3] Opción en Kconfig.projbuild: {patch_kconfig(kconfig)}")
    print(f"[3/3] Rama en CMakeLists.txt: {patch_cmake(cmake)}")
    print()
    print("Listo. Ahora compila con:")
    print(f"    python scripts/build.py {BOARD_DIR} --language es-ES")


if __name__ == "__main__":
    main()
