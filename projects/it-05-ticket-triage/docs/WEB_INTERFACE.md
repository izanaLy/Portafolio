# Triage Studio — interfaz web

Implementada y verificada el 2026-11-05 (UTC), sobre `e35cf04` de PR #2, en una rama separada. PR #2 continúa pendiente; esta interfaz no inicia `software-09`.

## Qué incorpora

- Portafolio con proyecto destacado y enlace funcional a la demo. El catálogo conserva los 90 registros y sus estados reales (89 planificados, 1 en revisión).
- Panel con 24 casos sintéticos, filtros P1–P4, búsqueda y detalle de impacto, urgencia, destino y razones.
- Laboratorio con tres escenarios iniciales y formulario editable. Las decisiones vienen de `ticket_triage.triage`, sin reconstruir las reglas en JavaScript.
- API HTTP de biblioteca estándar, local por defecto, validación del esquema existente, límite de 16 KiB, rechazo de POST de otro origen y restricción de archivos servidos.
- Modo muestra para hosting estático: snapshot de los 24 resultados del motor. Si cambian las reglas o los datos, regenerar `web/demo-data.json`; la prueba de paridad detecta divergencias.

## Ejecutar

Desde la raíz: `py run-demo.py --open` (Windows) o `python3 run-demo.py --open` (macOS/Linux). También se puede abrir `INICIAR_DEMO.bat` en Windows. Puerto por defecto: 8001. Cambiarlo con `--port 8002`. Cerrar con Ctrl+C.

Desde la carpeta del proyecto: `python -m ticket_triage.web --open`.

Un servidor estático permite recorrer la muestra; no ejecuta Python ni analiza casos nuevos. Los casos creados se conservan únicamente en la página abierta y se pierden al recargar. No ingresar datos reales.

## Verificación

- Ejecución original del autor del PR (Python 3.12.14): **200 pasadas**, 0 fallos (187 existentes + 13 HTTP/snapshot). La revisión posterior la reprodujo y la amplió; ver «Revisión técnica» más abajo.
- Sintaxis JavaScript comprobada con `node --check`.
- Chrome real en la vista previa: apertura desde el portafolio; carga de 24 casos; filtro P1 con cuatro resultados; escenario ransomware con 15 usuarios y alternativa disponible: devuelve P1, canal de seguridad y escalación inmediata, explicando por qué la alternativa no baja la urgencia. El caso nuevo aparece en la bandeja y eleva el total a 25.
- Inspección visual de escritorio. La hoja de estilos incluye adaptación móvil; no se verificó en un teléfono físico ni en Safari/Firefox. No se afirma equivalencia visual entre navegadores.

## Revisión técnica del PR #3 (2026-11-05)

Revisión independiente con Python 3.13.18 y Google Chrome 153 real (sin interfaz) controlado con Playwright, sobre `1f26d00`. Las 200 pruebas originales se reprodujeron (200 pasadas). La suite actual tiene **234 pruebas, todas pasadas** (187 del motor y CLI + 47 de la interfaz: 13 originales y 34 nuevas).

### Verificado sin defectos

Flujo completo con el motor conectado: abrir la demo desde el portafolio, 24 casos, filtro P1 (4 casos), búsqueda «vpn», detalle con razones y escenario nuevo que aparece en la bandeja como `LAB-0001` y sube el total a 25. Texto con HTML (`<img onerror>`, `<script>`) se muestra literal y no se ejecuta. Modo muestra (servidor estático): se exploran los 24 casos y «Analizar» explica que hace falta `INICIAR_DEMO.bat`. Teclado: `/` enfoca la búsqueda, Enter selecciona una fila, el diálogo se cierra con Escape y devuelve el foco. El portafolio mantiene 89 proyectos «Planificado» y `it-05` «Implementado · PR en revisión». Las decisiones las toma `ticket_triage.triage`; `app.js` no reimplementa reglas.

### Defectos encontrados y corregidos

| # | Defecto (reproducido antes de corregir) | Corrección |
|---|---|---|
| 1 | `HEAD` devolvía 200 y el tamaño de `AGENTS.md`, `.git/config` o `rules.py`, aunque `GET` diera 404 | `do_HEAD` aplica la misma lista cerrada que `GET` |
| 2 | JSON anidado de 16 KB: `RecursionError` sin capturar y conexión cortada sin respuesta | Respuesta 400 «El JSON está demasiado anidado» |
| 3 | `Content-Length: abc` devolvía el mensaje interno de Python | 400 con mensaje en español; JSON o UTF-8 inválidos también |
| 4 | El servidor aceptaba título de 5000 caracteres y 10³⁰ personas afectadas (el formulario limita a 180, 3000 y 1 000 000) | `check_limits` aplica los mismos límites en el servidor |
| 5 | La cabecera `Host` no se validaba (DNS rebinding) | Solo `localhost`, `127.0.0.1` y `::1`; `--host` específico añade ese host; `0.0.0.0` lo desactiva y avisa |
| 6 | Un cuerpo incompleto dejaba un hilo esperando para siempre | Tiempo límite de 10 s y respuesta 408 |
| 7 | El README se servía como `text/markdown` y el navegador lo descargaba | Se sirve como `text/plain` |
| 8 | Puerto ocupado: traza de Python | Mensaje con el comando para otro puerto y código de salida 1 |
| 9 | 15 reglas `font:` con «Space Grotesk» o «DM Sans» sin familia genérica: sin Google Fonts los títulos salían en Times | Se añadió `sans-serif` / `system-ui` |
| 10 | Texto de 7 a 9 px y contrastes de 1.8:1 a 4.4:1 en texto funcional | Mínimo de 11 px (10 px en cabeceras de columna) y 41 colores oscurecidos a 4.6:1 o más, más la variable `--muted` |
| 11 | Foco de teclado de 2.9:1 sobre blanco | `#9a7ae8`: 3.3:1 sobre blanco y 3.9:1 a 4.9:1 sobre los fondos oscuros |
| 12 | En móvil, barra y enlaces de 14 a 38 px de alto | Objetivos de 44 px |
| 13 | En móvil, el pie del héroe se cortaba y «PRIORIDAD» tocaba el borde del panel | Se ocultan los adornos cortados y la columna pasa de 48/55 a 64 px |
| 14 | `/favicon.ico` daba 404; los botones de la barra móvil solo mostraban un icono | Icono incrustado y atributo `title` |
| 15 | `INICIAR_DEMO.bat` usaba saltos LF, sin alternativa si falta `py` | CRLF fijado con `.gitattributes`; usa `python` si no hay `py` y avisa si no hay Python |
| 16 | Si el servidor se cerraba durante la sesión, el formulario mostraba «Failed to fetch» | Mensaje en español que remite a `INICIAR_DEMO.bat` |

### Evidencia

- Contra el código anterior (copia temporal con `web.py`, CSS, HTML y lanzador de `1f26d00`), **28 de las 47 pruebas de `tests/test_web.py` fallan**; con la corrección pasan las 47. En esa copia `/.git/config` no se puede probar porque `git archive` no incluye `.git`.
- Navegador: 51 comprobaciones, 0 fallos, en 1366, 390 y 320 px: sin desplazamiento horizontal (también en laboratorio y diálogo), sin texto funcional por debajo de 11 px, contraste de 4.5:1 o más en todo el texto funcional medido, anillo de foco visible en los primeros 14 elementos y objetivos táctiles de 40 px o más.
- Se descartó un falso positivo: `.orbit` sobresale en móvil pero está recortado por `overflow:hidden` del héroe y `scrollWidth` coincide con el viewport.

### Limitaciones pendientes

- **`INICIAR_DEMO.bat` no se ejecutó**: la revisión corrió en Linux. Se comprobaron su contenido, sus saltos de línea y su coherencia con el README y con `ticket_triage.web`. Falta una prueba en Windows.
- Chrome sin interfaz con emulación de móvil. No se probó en teléfonos reales, Safari ni Firefox, ni en GitHub Pages.
- Las fuentes DM Sans y Space Grotesk se piden a Google Fonts. Sin conexión la página funciona con la fuente sans-serif del sistema, con otra apariencia. No se autoalojaron porque este entorno no puede descargarlas.
- Sin `Content-Security-Policy` ni `X-Frame-Options`. Es razonable para una demo local con datos sintéticos, pero conviene añadirlas antes de publicar un servidor accesible desde Internet.
- El contraste lo mide un script contra el primer fondo opaco de cada elemento; se excluyen la maqueta y el arte decorativos, que son `aria-hidden`.
- Los datos y las reglas siguen siendo sintéticos: nada de esto valida las reglas con tickets reales.

## Alcance

Es un laboratorio educativo sobre reglas y datos ficticios, sin tickets de empresas, cuentas, autenticación, almacenamiento persistente ni conexión a plataformas externas. Los conteos describen el dataset y la sesión, no resultados laborales. La documentación histórica de las pruebas del motor conserva sus cifras y métodos originales.
