# QA técnica de PSE General 2.0

Fecha: 26 de octubre de 2026. Entorno observado: Windows, Python 3.12.14, biblioteca estándar. Edición evaluada: 2.0.0.

**Aceptación técnica: 175 pruebas pasan, seis ejemplos terminan en los estados previstos y se ejercitan las 12 operaciones CLI en una copia aislada.** Esto comprueba los contratos ensayados; no acredita perfección, identidad de revisores ni ventaja científica.

## Qué se ejecutó

| Grupo | Pruebas que pasan |
|---|---:|
| Adaptadores | 39 |
| Contratos de afirmaciones y resultados generados | 34 |
| Motor y persistencia | 47 |
| Escenarios adversariales originales migrados | 24 |
| Aceptación adversarial adicional 2.0 | 31 |
| Total | 175 |

La suite completa en la copia terminó con `OK`, 175 pruebas, en 19,232 segundos. El tiempo es una observación local, no un benchmark de rendimiento.

Se probaron `init`, `branch`, `run`, `status`, `verify`, `close`, `propose`, `review-packet`, `review`, `tip`, `revise` y `report`. La prueba CLI rechazó C12 con código 2; las operaciones legítimas terminaron con código 0. Incluyó reapertura por una objeción material, revisión del plan y nuevo cierre, además del flujo de propuesta y revisión declarada.

| Ejemplo conocido de desarrollo | Estado observado | Integridad local |
|---|---|---|
| calculo | CLOSED_RESULTS | Verificada |
| datos | CLOSED_RESULTS | Verificada |
| datos_sin_mejora | CLOSED_UNRESOLVED | Verificada |
| documentos | CLOSED_RESULTS | Verificada |
| techo | CLOSED_RESULTS | Verificada |
| revision_declarada | CLOSED_REVIEWED_DECLARED | Verificada |

El ejemplo de techo conserva un resultado `inconclusive` dentro de su cierre de resultados: no declara una ventaja. La revisión del sexto ejemplo es un registro sintético de desarrollo, expresamente rotulado; no es una revisión humana independiente.

## Corrección de C12 y límites demostrados

- El contrato antiguo con `requested_status`/`conclusion` se rechaza. `results_only` no admite una conclusión libre ni una rama ganadora.
- Los resúmenes factuales se generan a partir de datos tipados. Los juicios de `manual_review`, etiquetas de regiones, objetivos y afirmaciones se conservan como entradas declaradas. Texto adversarial no crea encabezados ni HTML ejecutable en el informe: se escapa o queda en bloques JSON literales.
- Una interpretación necesita una propuesta y una revisión vinculadas al contenido y contexto exactos. Se prueban referencias desconocidas, cobertura incompleta, rechazo, digest ajeno, otro caso, contexto obsoleto y autor/revisor equivalentes tras normalización Unicode.
- Los checks críticos fallidos, tips materiales pendientes y recursos agotados bloquean el respaldo correspondiente. Propuestas y revisiones consumen unidades y conservan sus cupos tras una revisión del plan.
- La verificación histórica usa los tiempos registrados: un cierre válido sigue verificándose después de vencer su plazo. El plazo actual sí impide nuevos cierres tardíos.
- Se rechazan secuencias ilegales y resultados mal tipados incluso cuando el atacante recalcula la cadena hash. Esto no demuestra resistencia frente a una reescritura total coherente ni custodia externa.
- **Límite explícitamente probado:** una persona que figura como revisor puede aprobar una afirmación falsa. El motor registra `CLOSED_REVIEWED_DECLARED`; la mentira no pasa a los hechos calculados. El software no verifica automáticamente la verdad de una interpretación ni autentica la identidad o independencia del revisor.
- Un umbral absoluto superior al MAE de referencia genera `inconclusive` sin rebajar el criterio. La igualdad admite una mejora perfecta y un mínimo relativo mayor que 1 se rechaza.

## Trazabilidad de las rondas

La matriz se fijó antes de ejecutar en `_build/qa_v2/PLAN_QA.md`. La primera ronda ejecutó las 175 pruebas: 174 pasaron y una aserción nueva de QA esperaba una cadena donde el contrato numérico devuelve un objeto con campos `exact` y `decimal_approximation`. Se corrigió la aserción para comparar el valor exacto; el caso dirigido pasó. No se modificó el producto para acomodar ese resultado. El log adverso se conserva.

La segunda ronda fue la aceptación completa en una carpeta nueva, con los módulos, pruebas, ejemplos y documentación congelados durante su ejecución. El recibo confirma igualdad de bytes antes de ejecutar y que los archivos de entrada de la copia y del origen permanecieron sin cambios durante esa aceptación. Este documento de resultados se redactó después; no forma parte de los bytes iniciales de esa ejecución.

Evidencia local conservada:

- `_build/qa_v2/ROUND1_TESTS.txt` — primera ronda, incluido el fallo de aserción.
- `_build/qa_v2/CORRECCION_ASERCION.txt` — comprobación dirigida tras corregir la aserción.
- `_build/qa_v2/acceptance_20261026T153849316846Z/RECEIPT.json` — comandos, códigos, entorno, huellas de entradas y logs, conteo y estados.
- `_build/qa_v2/acceptance_20261026T153849316846Z/logs/` — stdout y stderr de la suite, ejemplos y CLI.
- `_build/qa_v2/acceptance_20261026T153849316846Z/checkout/` — copia ejecutada y expedientes sintéticos generados.

SHA-256 del recibo: `e7c300b9a7f2b8226412a272e463a253af95ab1a29b785ea3cb017fac9f12f3b`.

Los archivos de `_build` son evidencia local de construcción y no se incluyen necesariamente en la distribución pública. La entrega puede adjuntar un recibo resumido y el log final sin los expedientes temporales.

## Alcance de la aceptación

Las pruebas fueron escritas y ejecutadas durante el desarrollo. La separación de autores de implementación y QA mejora la revisión, pero no constituye validación externa, independencia estadística, auditoría de seguridad certificada ni estudio de usuarios. No se midió utilidad investigadora frente al mismo modelo, datos, herramientas y presupuesto. Tampoco se ensayaron todas las plataformas ni todas las entradas posibles.

No se publicó el código durante esta aceptación y no se modificó la edición 1.0. Los resultados anteriores se conservan como historial separado.
