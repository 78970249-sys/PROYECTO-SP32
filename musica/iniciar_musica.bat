@echo off
REM Inicia el servidor de musica del Asistente UC (XiaoZhi).
REM 1) Pega tu punto de acceso MCP de xiaozhi.me entre las comillas de abajo.
REM 2) Guarda este archivo en la carpeta mcp-calculator, junto a mcp_pipe.py y musica.py.
REM 3) Haz doble clic en este archivo y deja la ventana abierta mientras usas el asistente.
cd /d "%~dp0"
set "MCP_ENDPOINT=PEGA_AQUI_TU_PUNTO_DE_ACCESO_wss"
python mcp_pipe.py musica.py
pause
