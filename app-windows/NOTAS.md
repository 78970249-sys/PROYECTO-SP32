## KusiVox 1.2.0

Asistente de escritorio por voz KusiVox: app de Windows y firmware del dispositivo.

Novedades de la 1.2.0: KusiVox entiende muchas más formas de pedir lo mismo. Por ejemplo «más fuerte», «bájale», «está muy alto», «pasa a la otra», «la calcu», «block de notas», «wasap», «a dormir» o «pon las letras grandes». También abre las herramientas de accesibilidad de Windows: lupa, narrador, teclado en pantalla, texto grande y alto contraste.

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
