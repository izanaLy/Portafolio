# Resultados de las pruebas — IT-05 Ticket Triage Simulator

Salida real obtenida el **2026-11-04** en un entorno Linux con **Python 3.13.18** y **pytest 9.1.1**, ejecutando desde `projects/it-05-ticket-triage/`.

## Resumen (estado actual)

```
$ python -m pytest -q
........................................................................ [ 38%]
........................................................................ [ 77%]
...........................................                              [100%]
187 passed in 0.28s
```

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `tests/test_models.py` | 25 | validación de `Ticket`, niveles y prioridades |
| `tests/test_rules.py` | 66 | normalización, categoría, impacto, urgencia (incluida la política de señales críticas de seguridad), matriz de prioridad, escalación, canal de seguridad, parámetros visibles |
| `tests/test_triage.py` | 13 | resultado explicable, escalación inmediata, seguridad P1 de extremo a extremo, revisión manual, resumen |
| `tests/test_dataset.py` | 31 | datos sintéticos, IDs únicos, patrones de datos personales, regresión contra etiquetas, validación estructural del cargador |
| `tests/test_cli.py` | 52 | salidas de tabla/JSON/resumen y código de salida 2 ante entradas inválidas |
| **Total** | **187** | |

## Ronda 2 — correcciones tras la revisión técnica del PR #2

La revisión pidió cuatro cambios. Esto es lo que se verificó para cada uno.

### 1. Robustez del cargador (`dataset.py`)

**Reproducción antes de corregir** (cada caso ejecutado a través del CLI con `python -m ticket_triage triage <archivo>`):

| Entrada | Resultado antes | Resultado ahora |
|---|---|---|
| `meta: null` | `AttributeError` no capturada | `Error: 'meta' debe ser un objeto JSON, no null`, exit 2 |
| `meta: []` | `AttributeError` no capturada | error explicativo, exit 2 |
| `tickets: null` | `TypeError` no capturada | error explicativo, exit 2 |
| `tickets: {"a": 1}` | `AttributeError` no capturada | error explicativo, exit 2 |
| item de `tickets` = texto | `AttributeError` no capturada | `tickets[0] debe ser un objeto JSON, no str`, exit 2 |
| item de `tickets` = `null` | `AttributeError` no capturada | error explicativo, exit 2 |
| `expected` = lista | exit 2 por casualidad, con mensaje críptico (`dictionary update sequence…`) | error explicativo, exit 2 |
| `expected: {"priority": 1}` | **aceptado sin aviso** | error: la etiqueta debe ser texto, exit 2 |
| `expected: {"foo": "bar"}` | **aceptado sin aviso** | error: claves no permitidas, exit 2 |

Seis de los nueve casos terminaban en una excepción sin capturar. Ahora todos devuelven `ValueError` con la ubicación del problema y el CLI responde con código de salida 2, sin trazas. Se añadieron pruebas para cada caso en las tres formas de uso del CLI (`triage`, `triage --format json`, `summary`), además de archivo no UTF-8, directorio en lugar de archivo, raíz `null` y raíz lista.

### 2. Política de urgencia para señales críticas de seguridad

Antes, `workaround_available = true` reducía la urgencia de cualquier ticket, incluso con `ransomware`. Ahora, si el texto contiene una señal de `CRITICAL_SECURITY_SIGNALS` (10 señales, ver README), la alternativa temporal no reduce la urgencia y la razón queda registrada. Es un supuesto de laboratorio acotado a esa lista; la regla normal sigue aplicando a phishing sin clic y fuera de seguridad (hay pruebas de ambos casos). Una prueba parametrizada recorre las 10 señales; otras comprueban de extremo a extremo que un ransomware con alternativa temporal sigue siendo P1.

### 3. Canal de seguridad independiente

La escalación `seguridad` queda documentada como canal independiente de la jerarquía nivel 1/2/3. Las razones del resultado lo dicen explícitamente y, para P1, añaden «atención inmediata por el canal de seguridad». Prueba explícita de seguridad P1: `escalation_level = "seguridad"`, `escalate = True`, `escalate_immediately = True`; y para seguridad P2, `escalate_immediately = False`. Además, el «nivel 2 mínimo» de infraestructura pasó de estar escrito dentro de la función a la constante `CATEGORY_MIN_ESCALATION`.

### 4. Parámetros y supuestos

El README tiene ahora una tabla de parámetros editables con su constante y aclara que son supuestos de laboratorio, no un SLA ni ITIL universal. Una prueba fija los valores documentados.

### Comprobación de que las pruebas nuevas detectan los problemas

Las pruebas nuevas se ejecutaron contra el código anterior, en copias temporales:

| Código probado | Resultado |
|---|---|
| Política crítica desactivada (la alternativa temporal vuelve a reducir siempre) | **13 fallaron**, 174 pasaron |
| `tests/test_cli.py` contra el `dataset.py` del commit anterior | **31 fallaron**, 21 pasaron |
| Código actual | **187 pasaron**, 0 fallaron |

(Una primera comprobación del cargador anterior se interrumpió con un error de importación, porque `parse_dataset` aún no existía; por eso se repitió solo con las pruebas del CLI.)

## Ronda 1 — historial de ejecuciones (93 pruebas)

1. **Primera comparación de reglas contra etiquetas esperadas:** 23 de 24 tickets coincidían. TKT-0011 («Teams no abre») se clasificaba como `software` en vez de `correo_colaboracion`, porque las frases «se cierra» y «no abre» (peso 3 y 2) sumaban más que «teams» (peso 3). Se redujo el peso de esos síntomas genéricos a 1, con el criterio de que el nombre del producto identifica mejor la categoría. **Este ajuste se hizo después de ver el resultado**, por lo que la prueba de regresión no es una validación independiente.
2. **Primera ejecución de pytest:** 91 pasaron y 1 falló (`test_no_personal_data_patterns`). Era un defecto de la prueba: el patrón de teléfono coincidía con las fechas ISO de `created_at`. Se corrigió revisando solo los campos de texto libre y se añadió una prueba que confirma que los patrones detectan casos obvios.
3. **Segunda ejecución:** 93 pasaron, 0 fallaron.

## Salida del CLI sobre los tickets sintéticos

Los conteos no cambiaron respecto a la ronda 1 (ningún ticket del conjunto combina una señal crítica con alternativa temporal):

```
$ python -m ticket_triage summary
{"total":{"tickets":24},"por_categoria":{"correo_colaboracion":2,"cuenta_acceso":4,"hardware":2,"impresion":2,"infraestructura":4,"otros":1,"red":3,"seguridad":3,"software":3},"por_prioridad":{"P1":4,"P2":5,"P3":4,"P4":11},"por_escalacion":{"nivel_1":15,"nivel_2":3,"nivel_3":3,"seguridad":3}}
```

(Salida compactada en una línea aquí; el comando real la imprime con sangría.) Estos conteos describen únicamente el conjunto ficticio incluido; no representan estadísticas de ninguna operación real.

Decisión explicada de un incidente de seguridad P1 (`python -m ticket_triage triage --explain`):

```
TKT-0010   seguridad            alto     alto      P1    seguridad (inmediata)
    - categoría «seguridad»: coincidencias «ransomware»
    - impacto alto: palabra clave de impacto alto: «ransomware»
    - urgencia alto: palabras de urgencia alta: «urgente», «ransomware»
    - urgencia alto: no existe alternativa temporal (sin cambio de urgencia)
    - matriz impacto alto x urgencia alto -> P1
    - categoría «seguridad»: se deriva al equipo de seguridad, canal independiente de la jerarquía nivel 1/2/3
    - prioridad P1: atención inmediata por el canal de seguridad
```

Error de entrada inválida:

```
$ python -m ticket_triage triage meta_null.json
Error: 'meta' debe ser un objeto JSON, no null
$ echo $?
2
```

## Cómo reproducir

```bash
cd projects/it-05-ticket-triage
pip install pytest
python -m pytest -v
python -m ticket_triage summary
python -m ticket_triage triage --explain
```
