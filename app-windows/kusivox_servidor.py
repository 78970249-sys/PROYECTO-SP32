"""KusiVoxServidor.exe: servidor MCP con las 20 herramientas, por entrada y salida estandar.
Lo arranca la app KusiVox; no hace falta abrirlo a mano."""

import sys

import escritorio

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    escritorio.servidor.run(transport="stdio")
