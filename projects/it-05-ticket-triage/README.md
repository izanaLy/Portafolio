# IT-05 — Ticket Triage Simulator

Simulador en Python que **clasifica y prioriza tickets de soporte técnico** con reglas explícitas y explicables. Cada decisión (categoría, impacto, urgencia, prioridad y escalación) incluye las razones que la produjeron.

- Núcleo solo con la **biblioteca estándar** de Python (sin dependencias ni APIs de pago).
- Datos **100 % sintéticos** (ver [`data/synthetic_tickets.json`](data/synthetic_tickets.json)).
- Pruebas con **pytest** (200 pruebas en esta rama: 187 del motor y CLI, 13 de la interfaz HTTP; resultados en [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md)).

> **Estado:** implementado y probado localmente el 2026-11-04. La revisión técnica del PR #2 pidió ajustes (validación del cargador, política de urgencia en seguridad y documentación del canal de seguridad); están aplicados y pendientes de revisión final. Es una **demostración de reglas sobre datos ficticios**: no se ha usado con tickets reales ni se presentan métricas de rendimiento operativo.

## Estructura

```
projects/it-05-ticket-triage/
├── ticket_triage/
│   ├── models.py     # Ticket, TriageResult, Level, Priority
│   ├── rules.py      # reglas: categoría, impacto, urgencia, prioridad, escalación
│   ├── triage.py     # orquesta las reglas y arma el resultado explicable
│   ├── dataset.py    # carga/validación del JSON (exige meta.synthetic = true)
│   └── cli.py        # interfaz de línea de comandos
├── data/synthetic_tickets.json   # 24 tickets ficticios con etiquetas esperadas
├── tests/                        # pytest
└── docs/TEST_RESULTS.md          # salida real de las pruebas y del CLI
```

## Requisitos e instalación

- Python 3.9 o superior (probado con 3.13.18).
- Para ejecutar el simulador no hay que instalar nada.
- Para las pruebas: `pip install pytest`.

## Interfaz web: Triage Studio

Desde la raíz del repositorio, ejecutar `py run-demo.py --open` en Windows o `python3 run-demo.py --open` en macOS/Linux. En Windows también se puede abrir `INICIAR_DEMO.bat` con doble clic.

Incluye una cola con búsqueda y filtros, selección de incidentes con razones, indicadores derivados de los datos y un laboratorio para modificar usuarios afectados y alternativa temporal. Los análisis nuevos llaman al motor Python existente mediante `/api/triage`; no se duplican las reglas en JavaScript.

[Instrucciones, evidencia y limitaciones](docs/WEB_INTERFACE.md). El historial original de 187 pruebas sigue en `docs/TEST_RESULTS.md`.

## Uso

Desde la carpeta `projects/it-05-ticket-triage/`:

```bash
# Clasificar los tickets sintéticos incluidos (tabla)
python -m ticket_triage triage

# Ver por qué se tomó cada decisión
python -m ticket_triage triage --explain

# Salida JSON (útil para otros proyectos)
python -m ticket_triage triage --format json

# Conteos por categoría, prioridad y escalación
python -m ticket_triage summary

# Usar otro archivo (debe declarar meta.synthetic = true)
python -m ticket_triage triage ruta/a/otros_tickets.json
```

Ejemplo de salida real (fragmento):

```
TICKET     CATEGORÍA            IMPACTO  URGENCIA  PRIO  ESCALACIÓN
-------------------------------------------------------------------
TKT-0003   red                  medio    alto      P2    nivel_2
TKT-0004   infraestructura      alto     alto      P1    nivel_3 (inmediata)
TKT-0005   seguridad            medio    medio     P2    seguridad
TKT-0023   otros                bajo     medio     P4    nivel_1 (revisión manual)
```

Uso como biblioteca:

```python
from ticket_triage import Ticket, triage

ticket = Ticket.from_dict({
    "id": "TKT-X", "title": "VPN caída",
    "description": "Nadie puede conectarse. Urgente.", "affected_users": 12,
})
result = triage(ticket)
print(result.priority.label, result.escalation_level)  # P1 nivel_3
print(*result.reasons, sep="\n")
```

## Reglas

Todas están en [`ticket_triage/rules.py`](ticket_triage/rules.py) como datos y funciones simples. El texto se normaliza (minúsculas, sin acentos) y las palabras clave coinciden como palabra completa, con plural simple `s`/`es`.

### 1. Categoría

Se suman los pesos de las palabras clave encontradas en el título y la descripción; gana la categoría con mayor puntaje. En empates se usa este orden: `seguridad`, `infraestructura`, `red`, `cuenta_acceso`, `correo_colaboracion`, `impresion`, `hardware`, `software`. Sin coincidencias → `otros` con `needs_manual_review = true`.

Reglas de diseño: las señales de seguridad pesan 5 y dominan sobre otras categorías; el nombre de un producto (Teams, Excel…) pesa más que síntomas genéricos como «se cierra» o «no abre».

### 2. Impacto (bajo / medio / alto)

Se toma el **máximo** de las reglas aplicables:

| Regla | Impacto |
|---|---|
| 1 usuario afectado | bajo |
| 2–9 usuarios afectados | medio |
| 10 o más usuarios afectados | alto |
| «toda la empresa», «toda la oficina», «todos los usuarios», «todos los empleados», «sistema de producción», «ransomware», «fuga de datos» | alto |
| «departamento», «varios usuarios», «todo el equipo», «sucursal», «oficina» | medio |
| Categoría `infraestructura` o `seguridad` | medio como mínimo |

### 3. Urgencia (baja / media / alta)

- **Alta:** «urgente», «crítico», «no puedo/puede/pueden trabajar», «fuera de servicio», «caído/a», «detenido/a», «sin acceso», «ransomware», «cliente(s) esperando».
- **Baja:** «no es urgente», «sin prisa», «cuando pueda», «cuando tengan tiempo», «consulta», «solicitud», «sugerencia», «mejora», «cosmético». Estas frases se retiran del texto antes de buscar urgencia alta, de modo que «no es urgente» no cuenta como «urgente».
- **Media:** valor por defecto.
- Si `workaround_available = true`, la urgencia baja un nivel (mínimo bajo). Si es `false`, no cambia, pero queda anotado en las razones.
- **Excepción conservadora para seguridad:** si el texto contiene una *señal crítica de seguridad* (`ransomware`, `ciberataque`, `hackeo`, `malware`, `fuga de datos`, `datos expuestos`, `credenciales expuestas`, `credenciales filtradas`, `cuenta comprometida`, `acceso no autorizado`), una alternativa temporal **no** reduce la urgencia, porque aislar un equipo no elimina el riesgo activo. La razón queda anotada en el resultado. Es un supuesto de laboratorio **acotado a esa lista** (`CRITICAL_SECURITY_SIGNALS` en `rules.py`), no una regla universal: otros incidentes de seguridad, como un phishing sin clic, sí pueden bajar por alternativa temporal, y fuera de seguridad la regla normal no cambia.

### 4. Prioridad (matriz impacto × urgencia)

| Impacto \ Urgencia | alta | media | baja |
|---|---|---|---|
| **alto** | P1 | P2 | P3 |
| **medio** | P2 | P3 | P4 |
| **bajo** | P3 | P4 | P4 |

Los incidentes de `seguridad` nunca bajan de **P2**.

### 5. Escalación (se aplica la primera regla que coincida)

1. Categoría `seguridad` → **equipo de seguridad**.
2. Prioridad P1 → **nivel 3** (`escalate_immediately = true`).
3. Prioridad P2 → **nivel 2**.
4. Categoría `infraestructura` → **nivel 2** como mínimo.
5. En otro caso → **nivel 1** (sin escalación).

**`seguridad` es un canal independiente, no un escalón de la jerarquía nivel 1/2/3:** toda la categoría va al equipo de seguridad, sea cual sea la prioridad, y `escalate` es `true`. La urgencia de atención se expresa aparte con `escalate_immediately`, que depende solo de la prioridad (P1) y también aplica a ese canal. Un incidente de seguridad P1 produce `escalation_level = "seguridad"` y `escalate_immediately = true`, y sus razones lo explican; uno de prioridad P2–P4 va al mismo canal con `escalate_immediately = false`.

## Parámetros editables y supuestos de laboratorio

Los umbrales y las reglas de arriba son **supuestos de laboratorio** para demostrar el razonamiento. **No** son un SLA ni una implementación estándar de ITIL, y no se calibraron en ninguna organización. Están visibles como constantes en [`ticket_triage/rules.py`](ticket_triage/rules.py) para poder cambiarlos:

| Parámetro | Valor actual | Constante |
|---|---|---|
| Usuarios afectados para impacto medio / alto | 2 / 10 | `USERS_FOR_MEDIUM_IMPACT`, `USERS_FOR_HIGH_IMPACT` |
| Impacto mínimo por categoría | `infraestructura` y `seguridad`: medio | `CATEGORY_IMPACT_FLOOR` |
| Prioridad mínima de seguridad | P2 | `SECURITY_PRIORITY_FLOOR` |
| Escalación mínima por categoría | `infraestructura`: nivel 2 | `CATEGORY_MIN_ESCALATION` |
| Señales críticas de seguridad (sin reducción por alternativa temporal) | lista de 10 señales | `CRITICAL_SECURITY_SIGNALS` |
| Matriz impacto × urgencia | tabla de la sección 4 | `PRIORITY_MATRIX` |

Una prueba (`test_visible_parameters_have_the_documented_values`) fija los valores documentados, de modo que cambiar uno obliga a actualizar también esta tabla.

## Validación de los datos de entrada

`load_dataset` / `parse_dataset` validan la estructura completa y lanzan `ValueError` con un mensaje que indica dónde está el problema: la raíz debe ser un objeto; `meta` debe ser un objeto con `synthetic = true`; `tickets` debe ser una lista de objetos; y si un ticket trae `expected`, debe ser un objeto con claves permitidas (`category`, `impact`, `urgency`, `priority`, `escalation_level`) y valores de texto. El CLI convierte cualquiera de esos errores, además de archivos inexistentes, directorios, JSON roto o codificación inválida, en `Error: …` por stderr y **código de salida 2**, sin trazas.

## Esquema de ticket (para `software-09` y `data-02`)

Entrada (`Ticket`):

| Campo | Tipo | Notas |
|---|---|---|
| `id` | texto | único, obligatorio |
| `title`, `description` | texto | obligatorios |
| `requester` | texto | seudónimo, p. ej. `usuario-001` |
| `created_at` | texto ISO 8601 o `null` | opcional |
| `affected_users` | entero ≥ 1 | por defecto 1 |
| `workaround_available` | `true` / `false` / `null` | `null` = no informado |

Salida (`TriageResult.to_dict()`): `ticket_id`, `category`, `impact`, `urgency`, `priority`, `escalation_level`, `escalation_team`, `escalate`, `escalate_immediately`, `needs_manual_review`, `reasons[]`.

Valores permitidos: `impact`/`urgency` ∈ {`bajo`, `medio`, `alto`}; `priority` ∈ {`P1`…`P4`}; `escalation_level` ∈ {`nivel_1`, `nivel_2`, `nivel_3`, `seguridad`}; `category` ∈ {`seguridad`, `infraestructura`, `red`, `cuenta_acceso`, `correo_colaboracion`, `impresion`, `hardware`, `software`, `otros`}.

## Pruebas

```bash
pip install pytest
python -m pytest -v
```

Cubren validación del modelo, cada regla (incluida la monotonía de la matriz de prioridad), el caso «no es urgente», la política de señales críticas de seguridad, el canal de seguridad P1, el cargador de datos con entradas estructuralmente inválidas, la ausencia de patrones de datos personales en los tickets y el CLI con códigos de salida. Ver [`docs/TEST_RESULTS.md`](docs/TEST_RESULTS.md).

## Limitaciones

- **Las reglas son palabras clave**, no comprensión del lenguaje: no detectan negaciones generales («esto no es phishing»), sarcasmo, errores ortográficos ni sinónimos que no estén en las listas.
- **Solo español.** Un ticket en otro idioma probablemente caerá en `otros`.
- **Las etiquetas esperadas las definió el autor** del proyecto, y una de ellas motivó un ajuste de pesos después de ver el resultado (TKT-0011, ver `docs/TEST_RESULTS.md`). Por eso la prueba de regresión detecta cambios involuntarios en las reglas, pero **no es una medida de precisión** ni valida las reglas con datos reales.
- Los umbrales (por ejemplo, 10 usuarios = impacto alto), la matriz y la lista de señales críticas de seguridad son supuestos de laboratorio, no valores calibrados en una organización concreta ni un SLA/ITIL universal (ver «Parámetros editables»).
- La excepción de urgencia para señales críticas de seguridad es una lista corta de palabras clave: un incidente grave descrito con otras palabras no activará la excepción.
- Los datos son ficticios; no se hicieron mediciones de tiempo de resolución, carga ni satisfacción.
- La interfaz web de esta rama es un laboratorio local con datos sintéticos. No hay integración con sistemas de tickets reales ni persistencia; `software-09` sigue pendiente.

## Trabajo relacionado

- `software-09` Help Desk Portal y `data-02` Customer Support Metrics podrán reutilizar el esquema de ticket anterior.
