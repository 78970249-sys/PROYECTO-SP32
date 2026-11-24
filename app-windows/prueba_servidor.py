"""Prueba de compilacion: arranca KusiVoxServidor.exe y comprueba que anuncia las 20 herramientas por MCP."""

import json
import subprocess
import sys

ESPERADAS = 20


def main(comando: list) -> int:
    proc = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def enviar(mensaje: dict) -> None:
        proc.stdin.write((json.dumps(mensaje) + "\n").encode("utf-8"))
        proc.stdin.flush()

    def recibir(id_esperado: int) -> dict:
        while True:
            linea = proc.stdout.readline()
            if not linea:
                raise RuntimeError("el servidor se cerró: " + proc.stderr.read().decode("utf-8", "replace"))
            datos = json.loads(linea)
            if datos.get("id") == id_esperado:
                return datos

    try:
        enviar({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "prueba-kusivox", "version": "1.0"}}})
        inicio = recibir(1)
        print("servidor:", inicio["result"]["serverInfo"])
        enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})
        enviar({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        herramientas = [h["name"] for h in recibir(2)["result"]["tools"]]
        print(len(herramientas), "herramientas:", ", ".join(herramientas))
        assert len(herramientas) == ESPERADAS, f"se esperaban {ESPERADAS}"
        print("prueba del servidor: OK")
        return 0
    finally:
        proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
