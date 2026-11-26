## KusiVox 1.3.0

Asistente de escritorio por voz KusiVox: app de Windows y firmware del dispositivo.

Novedades de la 1.3.0:

- **Lenguaje libre:** entiende la orden completa tal como la dices, aunque sea una sola palabra («Word», «YouTube») u órdenes compuestas («abre Word y escribe hola»).
- **YouTube en la misma pestaña:** si pides otra canción, cambia el video sin abrir otra ventana.
- **Todo lo que se hace con el mouse:** clic por nombre («haz clic en Guardar»), doble clic, clic derecho, mover el puntero y desplazar.
- **Atajos por nombre:** «guárdalo», «copia», «selecciona todo», «negrita», «nueva pestaña», «atrás».
- **Lectura de pantalla:** dice qué ventana está al frente, el texto donde está el cursor y qué botones hay.
- **Brave y otros navegadores:** usa el navegador predeterminado de Windows o el que elijas por voz («usa Brave como navegador», «abre YouTube en Brave»).
- **Siempre conectado:** el instalador lo deja iniciando con Windows, la X lo minimiza en vez de cerrarlo, se reconecta en pocos segundos y evita que la PC se suspenda.
- **Ventana nueva:** KusiVox animado según el estado de la conexión y ejemplos de órdenes.
- **Más rápido:** menos esperas al abrir programas y el menú Inicio se lee al arrancar.

**Descargas**

- `KusiVox-Setup.exe`: instalador para Windows 10 y 11 (64 bits). No necesita Python ni permisos de administrador.
- `KusiVox-Portable.zip`: la misma app sin instalar (descomprimir y abrir `KusiVox.exe`).
- `kusivox-v2-shihtzu.bin`: firmware del dispositivo con KusiVox como cachorro shih tzu animado, y emociones que cambian en cada frase (grabar con ESP Tool en la dirección 0x0).
- `kusivox-lcd-240x240-20mhz-bateria.bin`: firmware anterior con caritas, por si se quiere volver atrás.

**Primer uso**

1. Instala y abre KusiVox.
2. En xiaozhi.me abre tu agente → Configurar → Extensiones y copia el MCP endpoint (`wss://…?token=…`).
3. Pega el endpoint en KusiVox y pulsa **Guardar y conectar**. El estado debe decir *Conectado*.
4. Di "KusiVox" al dispositivo y pide, por ejemplo, "abre la calculadora".

Windows puede mostrar "Windows protegió su PC" porque la app no tiene firma digital: pulsa **Más información → Ejecutar de todas formas**.

App para el celular: https://78970249-sys.github.io/PROYECTO-SP32/
