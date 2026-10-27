# Revisar el código antes de ejecutarlo

La distribución pública es texto legible. Puede inspeccionarse sin ejecutar Python. No incluye instaladores, macros, ejecutables compilados, bibliotecas empaquetadas ni descargas automáticas.

| Archivo | Función y efectos |
|---|---|
| `pse/__main__.py` | Comandos y escritura de informes cuando se solicita. |
| `pse/engine.py` | Planes, fuentes locales, expedientes, bloqueos, registro y transiciones. |
| `pse/adapters.py` | Lectura de fuentes y cálculo de las cinco comprobaciones. |
| `pse/claims.py` | Validación de propuestas y revisiones, generación de resultados y escape del texto declarado. |
| `scripts/run_examples.py` | Crea seis expedientes e informes de desarrollo en una carpeta nueva. |
| `tests/` | Entradas, presupuesto, integridad, transiciones, regresiones y ataques al cierre. |

El runtime usa la biblioteca estándar. No llama a modelos, no usa claves de API ni incorpora operaciones de red. Las expresiones aritméticas se analizan con operadores admitidos y no se ejecutan con `eval`. Python y cualquier asistente que lo utilice son componentes externos.

El motor crea y modifica archivos de sus expedientes. Las pruebas gestionan temporales. Revisa las operaciones de archivo aunque la entrega no tenga instalador. No ejecutes modificaciones de origen desconocido solo porque un expediente pase `verify`.

El manifiesto SHA-256 identifica los bytes distribuidos; los hashes del expediente detectan discrepancias respecto a sus recibos locales. No acreditan autoría, verdad, fecha externa ni custodia independiente.

La revisión estática y los tests tienen un alcance acotado, detallado en [QA_RESULT.md](QA_RESULT.md). No equivalen a un análisis antivirus o una certificación absoluta de seguridad.
