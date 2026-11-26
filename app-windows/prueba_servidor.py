"""Prueba de compilacion: arranca KusiVoxServidor.exe y comprueba que anuncia sus 24 herramientas por MCP
y que, ya compilado, puede leer la pantalla y entender una orden libre (sin ejecutar nada peligroso)."""

import json
import subprocess
import sys

ESPERADAS = 24


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
        if sys.platform == "win32":
            # leer_pantalla usa UI Automation (comtypes): confirma que viaja dentro del .exe.
            enviar({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "leer_pantalla", "arguments": {}}})
            texto = recibir(3)["result"]["content"][0]["text"]
            print("leer_pantalla:", texto[:300])
            assert "no deja leer" not in texto, "UI Automation no funciona dentro del ejecutable"
        # Una orden de apagar por la orden libre debe pedir confirmacion y no apagar nada.
        enviar({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "ejecutar_orden", "arguments": {"frase": "apaga la computadora"}}})
        texto = recibir(4)["result"]["content"][0]["text"]
        print("ejecutar_orden(apaga):", texto[:200])
        assert "requiere_confirmacion" in texto, "apagar debe pedir confirmacion"
        print("prueba del servidor: OK")
        return 0
    finally:
        proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
