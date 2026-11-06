# Help Desk Portal (software-09) — primera entrega

Portal de tickets de soporte con **datos ficticios**: alguien crea un ticket, el motor de IT-05 lo clasifica y prioriza, y un agente lo gestiona hasta cerrarlo. Es un ejercicio de portafolio; no representa un sistema en producción ni experiencia laboral.

**Estado:** primera entrega en revisión (PR). El catálogo `projects.json` no se modificó: `software-09` sigue figurando como planificado hasta que se revise y fusione.

## Alcance de esta entrega

Incluye:

- Crear tickets (título, descripción, personas afectadas, alternativa temporal) con validación y límites.
- **Triaje automático** con `ticket_triage.triage` de IT-05: categoría, impacto, urgencia, prioridad P1–P4, destino de escalación y razones. Este proyecto no reimplementa reglas.
- Cola ordenada por prioridad, con filtro por prioridad/estado y búsqueda por título, ID o categoría.
- Ciclo de vida: `nuevo → en_progreso → resuelto → cerrado` (un resuelto puede reabrirse; un cerrado no cambia ni admite comentarios).
- Comentarios e historial de eventos por ticket.
- Persistencia en SQLite (memoria por defecto o un archivo con `--db`).
- API JSON y una página web accesible (sin `innerHTML`; el texto de los tickets nunca se interpreta como HTML).

No incluye (decisiones pendientes para la revisión): inicio de sesión y roles, notificaciones, adjuntos, SLA con relojes, despliegue público, servicios externos o de pago.

## Dependencia de IT-05

Usa el paquete `ticket_triage` de `projects/it-05-ticket-triage` y su esquema de ticket (`Ticket`, `TriageResult`). No se copia código: si `ticket_triage` no está instalado, `helpdesk/__init__.py` añade la carpeta hermana a `sys.path`. Por eso esta rama parte de la rama del PR #2 (solo el motor) y **no depende de la interfaz del PR #3**. Hasta que se fusione el PR #2, el PR de este proyecto apunta a esa rama.

## Ejecutar

Requiere Python 3.9 o superior y solo usa la biblioteca estándar. Desde esta carpeta:

```bash
python3 run.py --seed          # Windows: py run.py --seed
```

Abrir <http://127.0.0.1:8002/>. `--seed` carga 5 tickets ficticios; `--port 8003` cambia el puerto; `--db hd.sqlite` conserva los datos entre ejecuciones. Cerrar con `Ctrl+C`. El servidor escucha solo en esta computadora, valida `Host` y `Origin`, limita el cuerpo a 16 KiB y sirve una lista cerrada de archivos. **No ingresar datos reales.**

## API

| Método y ruta | Qué hace |
|---|---|
| `GET /api/tickets?priority=P1&status=nuevo&q=vpn` | Cola ordenada por prioridad |
| `POST /api/tickets` | Crea y clasifica (`title`, `description`, `affected_users`, `workaround_available`, `requester`) |
| `GET /api/tickets/HD-0001` | Detalle con razones e historial |
| `POST /api/tickets/HD-0001/comments` | `{ "body": "...", "author": "..." }` |
| `POST /api/tickets/HD-0001/status` | `{ "status": "en_progreso", "assignee": "..." }` |
| `GET /api/stats` | Totales por estado y prioridad |

## Pruebas

```bash
python3 -m pytest -q
```

29 pruebas: integración con el motor (la prioridad guardada coincide con la de `triage`), cola y filtros, ciclo de vida, validación y límites, inyección SQL inerte, persistencia en archivo, API (errores 400/404/413, Host y Origin, lista cerrada de archivos, paridad HEAD/GET) y ausencia de `innerHTML`.

## Evidencia (2026-11-06)

- Python 3.13.18, Linux: `python3 -m pytest -q` → **29 pasadas**.
- Chrome 153 real (sin interfaz) a 1366, 390 y 320 px: 25 comprobaciones, 0 fallos. Cubren cola sembrada, filtro P1, creación, HTML escapado, razones del motor, estado, comentario, historial, cierre, validación, foco, desbordamiento horizontal y objetivos táctiles de 40 px o más.
- No se probó en teléfonos reales, Safari, Firefox ni Windows.

## Limitaciones

- Sin autenticación: cualquiera con acceso local actúa como solicitante o agente. Es suficiente para una demo local, no para publicarla.
- El triaje depende de las reglas sintéticas de IT-05; no se validaron con tickets reales.
- Sin `Content-Security-Policy`; conviene añadirla antes de exponer el servicio fuera de la computadora local.
- Las marcas de tiempo son del reloj del servidor (UTC) y describen la sesión de demo, no historial laboral.
