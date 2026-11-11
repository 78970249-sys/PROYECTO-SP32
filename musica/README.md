# Música por voz en la computadora

`musica.py` da al asistente (ESP32-S3 + xiaozhi.me + DeepSeek) herramientas para poner
**cualquier canción, artista, género o ambiente** buscándolo en **YouTube**. La música
suena en la **computadora**, no en el parlante del ESP32: el firmware de XiaoZhi no
reproduce canciones, así que el ESP32 recibe la orden por voz y la PC la ejecuta.

```
voz → ESP32-S3 → xiaozhi.me (DeepSeek elige la herramienta)
    → punto de acceso MCP (WebSocket) → mcp_pipe.py → musica.py → YouTube en la PC
```

## Herramientas MCP

| Herramienta | Qué hace |
|---|---|
| `reproducir_musica(busqueda)` | Busca en YouTube y abre el primer resultado |
| `pausar_o_reanudar_musica()` | Pausa o reanuda (tecla multimedia de Windows) |
| `siguiente_cancion()` | Pasa a la siguiente recomendada |
| `detener_musica()` | Detiene la música |
| `volumen_computadora(accion, pasos)` | Sube, baja o silencia el volumen de la PC |
| `musica_actual()` | Dice qué se pidió por última vez |

## Instalación (Windows)

1. Instala **Python** desde python.org y marca **"Add Python to PATH"**.
2. Descarga el conector oficial de XiaoZhi: <https://github.com/78/mcp-calculator>
   (**Code → Download ZIP**) y descomprímelo.
3. Copia `musica.py` e `iniciar_musica.bat` dentro de esa carpeta, junto a `mcp_pipe.py`.
4. En una terminal dentro de esa carpeta: `pip install -r requirements.txt`

## Conexión con el agente

1. En xiaozhi.me → tu agente → **Configure → Extensions**, copia el punto de acceso
   **MCP** (empieza con `wss://`).
2. Abre `iniciar_musica.bat` con el Bloc de notas, pega la dirección en lugar de
   `PEGA_AQUI_TU_PUNTO_DE_ACCESO_wss` y guarda.
3. Haz doble clic en `iniciar_musica.bat` y deja la ventana abierta.
4. Agrega al rol del agente: *"Si te piden música de cualquier tipo, usa la herramienta
   reproducir_musica con la canción, artista, género o ambiente que pidan."*
   (Con el rol [asistente_musical.md](../roles/asistente_musical.md), cambia también la
   regla que dice que no puede reproducir audio.)

## Ejemplos de órdenes

- "Pon Bohemian Rhapsody de Queen" · "Pon cumbia peruana" · "Música para estudiar"
- "Pausa la música" · "Siguiente canción" · "Detén la música"
- "Sube el volumen" · "Baja el volumen"

> Si la primera canción se abre pero no empieza sola, pulsa play una vez en el navegador.
> El control de pausa, siguiente y volumen usa teclas multimedia y solo funciona en Windows.
