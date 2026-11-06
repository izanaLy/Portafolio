# Gustavo Pacheco Carballo — Portafolio profesional

Portafolio de IT Infrastructure, Software Development y Data Analytics.

**Estado actual:** catálogo de 90 proyectos: 89 planificados y `it-05` completado. El portafolio incluye la demo interactiva Triage Studio, con 234 pruebas automatizadas y una validación manual en Windows. No se atribuyen fechas históricas ni experiencia laboral a los ejercicios.

## Sitio

En Windows, con Python instalado, hacer doble clic en **`INICIAR_DEMO.bat`**. Se abre Triage Studio en el navegador. Mantener la consola abierta; `Ctrl+C` detiene el servidor.

También, desde esta carpeta:

```powershell
py run-demo.py --open
```

En macOS/Linux: `python3 run-demo.py --open`.

- Portafolio: <http://127.0.0.1:8001/>
- Demo: <http://127.0.0.1:8001/projects/it-05-ticket-triage/web/>
- Si el puerto está ocupado: `py run-demo.py --port 8002 --open`.

El servidor usa la biblioteca estándar de Python, escucha solo en esta computadora por defecto y analiza casos ficticios con el motor original. No requiere npm ni servicios de pago. Los casos creados viven en memoria del navegador y desaparecen al recargar.

Con un servidor estático como `py -m http.server 8000` o GitHub Pages se pueden explorar los 24 casos precalculados en **modo muestra**. Para analizar escenarios nuevos se necesita el servidor Python anterior. [Detalles y verificación](projects/it-05-ticket-triage/docs/WEB_INTERFACE.md).

## Organización

- `index.html`: sitio web responsive y filtros por categoría.
- `projects.json`: catálogo y estado verificable de cada proyecto.
- `AGENTS.md`: reglas para colaborar con Codex y Claude.

## Criterios para completar proyectos

Cada proyecto deberá tener código reproducible, instrucciones, pruebas y evidencia. Registrar las fechas reales de desarrollo de cada proyecto, sin inventar historial de 2022–2026. Los proyectos planificados todavía no están completados.

## Perfil

Experiencia profesional en soporte técnico y operaciones de centro de datos. Las habilidades y certificaciones se documentarán con precisión.
