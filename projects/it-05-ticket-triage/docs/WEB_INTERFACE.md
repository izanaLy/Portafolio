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

- Python 3.12.14: `python3 -m pytest -q` desde la raíz: **200 pasadas**, 0 fallos (187 existentes + 13 HTTP/snapshot).
- Sintaxis JavaScript comprobada con `node --check`.
- Chrome real en la vista previa: apertura desde el portafolio; carga de 24 casos; filtro P1 con cuatro resultados; escenario ransomware con 15 usuarios y alternativa disponible: devuelve P1, canal de seguridad y escalación inmediata, explicando por qué la alternativa no baja la urgencia. El caso nuevo aparece en la bandeja y eleva el total a 25.
- Inspección visual de escritorio. La hoja de estilos incluye adaptación móvil; no se verificó en un teléfono físico ni en Safari/Firefox. No se afirma equivalencia visual entre navegadores.

## Alcance

Es un laboratorio educativo sobre reglas y datos ficticios, sin tickets de empresas, cuentas, autenticación, almacenamiento persistente ni conexión a plataformas externas. Los conteos describen el dataset y la sesión, no resultados laborales. La documentación histórica de las pruebas del motor conserva sus cifras y métodos originales.
