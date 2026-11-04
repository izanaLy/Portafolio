# Resultados de las pruebas — IT-05 Ticket Triage Simulator

Salida real obtenida el **2026-11-04** en un entorno Linux con **Python 3.13.18** y **pytest 9.1.1**, ejecutando desde `projects/it-05-ticket-triage/`.

## Resumen

```
$ python -m pytest -q
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 0.15s
```

| Archivo | Pruebas | Qué cubre |
|---|---|---|
| `tests/test_models.py` | 25 | validación de `Ticket`, niveles y prioridades |
| `tests/test_rules.py` | 43 | normalización, categoría, impacto, urgencia, matriz de prioridad, escalación |
| `tests/test_triage.py` | 7 | resultado explicable, escalación inmediata, revisión manual, resumen |
| `tests/test_dataset.py` | 11 | datos sintéticos, IDs únicos, patrones de datos personales, regresión contra etiquetas, validación del cargador |
| `tests/test_cli.py` | 7 | salidas de tabla/JSON/resumen y códigos de error |
| **Total** | **93** | |

## Historial de ejecuciones durante el desarrollo

Se registran los fallos intermedios para que el proceso sea verificable:

1. **Primera comparación de reglas contra etiquetas esperadas:** 23 de 24 tickets coincidían. TKT-0011 («Teams no abre») se clasificaba como `software` en vez de `correo_colaboracion`, porque las frases «se cierra» y «no abre» (peso 3 y 2) sumaban más que «teams» (peso 3). Se redujo el peso de esos síntomas genéricos a 1, con el criterio de que el nombre del producto identifica mejor la categoría. **Este ajuste se hizo después de ver el resultado**, por lo que la prueba de regresión no es una validación independiente.
2. **Primera ejecución de pytest:** 91 pasaron y 1 falló (`test_no_personal_data_patterns`). Era un defecto de la prueba: el patrón de teléfono coincidía con las fechas ISO de `created_at`. Se corrigió revisando solo los campos de texto libre y se añadió una prueba que confirma que los patrones detectan casos obvios.
3. **Segunda ejecución:** 93 pasaron, 0 fallaron.

## Salida del CLI sobre los tickets sintéticos

```
$ python -m ticket_triage summary
{
  "total": {
    "tickets": 24
  },
  "por_categoria": {
    "correo_colaboracion": 2,
    "cuenta_acceso": 4,
    "hardware": 2,
    "impresion": 2,
    "infraestructura": 4,
    "otros": 1,
    "red": 3,
    "seguridad": 3,
    "software": 3
  },
  "por_prioridad": {
    "P1": 4,
    "P2": 5,
    "P3": 4,
    "P4": 11
  },
  "por_escalacion": {
    "nivel_1": 15,
    "nivel_2": 3,
    "nivel_3": 3,
    "seguridad": 3
  }
}
```

Estos conteos describen únicamente el conjunto ficticio incluido; no representan estadísticas de ninguna operación real.

Ejemplos de decisiones explicadas (`python -m ticket_triage triage --explain`):

```
TKT-0005   seguridad            medio    medio     P2    seguridad
    - categoría «seguridad»: coincidencias «phishing», «correo sospechoso», «sospechoso»
    - impacto medio: la categoría «seguridad» tiene impacto mínimo medio
    - urgencia medio: sin palabras de urgencia: urgencia base media
    - matriz impacto medio x urgencia medio -> P3
    - incidente de seguridad: prioridad mínima P2
    - categoría «seguridad»: se deriva siempre al equipo de seguridad
TKT-0011   correo_colaboracion  bajo     medio     P4    nivel_1
    - categoría «correo_colaboracion»: coincidencias «teams»
    - impacto bajo: impacto base: bajo
    - urgencia medio: sin palabras de urgencia: urgencia base media
    - matriz impacto bajo x urgencia medio -> P4
    - sin criterios de escalación: se atiende en nivel 1
TKT-0023   otros                bajo     medio     P4    nivel_1 (revisión manual)
    - categoría «otros»: sin coincidencias; requiere clasificación manual
    - impacto bajo: impacto base: bajo
    - urgencia medio: sin palabras de urgencia: urgencia base media
    - matriz impacto bajo x urgencia medio -> P4
    - sin criterios de escalación: se atiende en nivel 1
```

## Cómo reproducir

```bash
cd projects/it-05-ticket-triage
pip install pytest
python -m pytest -v
python -m ticket_triage summary
python -m ticket_triage triage --explain
```
