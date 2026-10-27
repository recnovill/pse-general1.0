# Motor local PSE General 2.0

Python 3.11 o posterior; biblioteca estándar, sin red, cuentas, modelos ni ejecución de instrucciones arbitrarias del plan. El programa ejecuta comprobaciones concretas y mantiene un expediente con contratos, límites y trazabilidad. La formulación, pertinencia de las pruebas y evaluación semántica pertenecen al ejecutor y al revisor.

La versión 2 elimina el cierre libre `supported`. Hay tres cierres distintos: resultados tipados, inconcluso o interpretación con revisión declarada vinculada a una propuesta. Ninguno promete verdad universal ni eficacia investigadora demostrada.

## Uso básico

Desde la carpeta que contiene `pse/`:

```powershell
python -B -m unittest discover -s tests -v
python -B -m pse init examples/calculo/plan.json --out casos/mi_calculo
python -B -m pse branch casos/mi_calculo base
python -B -m pse run casos/mi_calculo
python -B -m pse status casos/mi_calculo
python -B -m pse verify casos/mi_calculo
python -B -m pse close casos/mi_calculo --decision examples/calculo/decision.json
python -B -m pse report casos/mi_calculo --out informes/mi_calculo.md
```

Los ID se leen en el plan. `init` y `report` no sobrescriben destinos. Los comandos devuelven JSON; los errores controlados salen por stderr con código 2. La revisión `reject` registrada correctamente devuelve código 0: significa que se guardó, no que la propuesta haya sido aprobada.

Para una interpretación revisada se preparan archivos JSON conforme a [CONTRATO_CIERRE.md](CONTRATO_CIERRE.md):

```powershell
python -B -m pse propose casos/mi_caso --draft borrador.json
python -B -m pse review-packet casos/mi_caso proposal_1
python -B -m pse review casos/mi_caso --review revision.json
python -B -m pse close casos/mi_caso --decision cierre_revisado.json
```

El paquete de revisión no rellena ni sugiere un veredicto. El revisor debe aportar su evaluación y copiar el ID y SHA-256 exactos de la propuesta. El motor no produce aprobaciones automáticamente.

## Plan de versión 2

Los campos exactos son `version`, `case_id`, `objective`, `scope`, `success_criteria`, `limitations`, `budget`, `questions`, `branches` y `checks`. `version` es el entero 2. [El ejemplo de cálculo](../examples/calculo/plan.json) proporciona un plan completo.

- `budget`: enteros positivos `max_checks`, `max_units`, `max_rounds`, `max_seconds`.
- `questions`: al menos dos objetos con `id`, `text`, `purpose`.
- `branches`: al menos tres, con `id`, `question_id`, `role`, `hypothesis`, `approach`, `falsifier`. Deben existir los roles `baseline`, `alternative`, `critical`.
- `checks`: objetos con `id`, `branch_ids`, `method`, `params`, `decision_link`, `critical`, `challenge`, `cost_units`; `revises` solo para nuevos controles de una ronda posterior.

Todos los ID son únicos entre preguntas, ramas y controles: una letra inicial y hasta 64 letras ASCII, dígitos, `_` o `-`. Cada rama tiene control y debe existir un control crítico marcado como `challenge`. Las preguntas y enfoques no pueden ser literalmente idénticos tras normalizar mayúsculas y espacios. Esta comprobación no certifica diversidad semántica. Los textos obligatorios no pueden estar vacíos ni tener espacios laterales. JSON con claves repetidas o números no finitos se rechaza; booleanos no cuentan como enteros.

Los métodos admitidos son `arithmetic`, `numeric_interval`, `csv_compare`, `text_evidence` y `manual_review`; sus parámetros están cerrados y se describen en [ADAPTADORES.md](ADAPTADORES.md). El tipo de resultado debe corresponder al método: calculado `computed`, documental `documentary` o declarado `declared`. El verificador comprueba hechos tipados antes de admitir un resultado en el historial. Una excepción o interrupción solo puede producir `inconclusive`.

Las fuentes son rutas relativas a la carpeta del plan, con `/`, sin `..`, enlaces, junctions ni salida de la raíz. Se copian en snapshots; cambiar el original después no cambia los datos usados. Máximo 10 MiB por fuente y 50 MiB por ronda en el motor; los adaptadores aplican su límite más estricto de 2.000.000 bytes al consumir archivos.

Los planes de versión 1 se rechazan con indicación de migración. Conservar la versión original del programa para auditar expedientes 1.0; migrar una copia del plan crea un caso nuevo, sin reescribir su historia.

## Cierres y estados

| Entrada exacta de cierre | Estado | Efecto |
|---|---|---|
| `{"mode":"results_only"}` | `CLOSED_RESULTS` | Conserva resultados generados, incluidos fail e inconclusive; no selecciona rama ni acepta conclusión libre. |
| `{"mode":"unresolved","reason":"Motivo declarado","limitations":["Límite"]}` | `CLOSED_UNRESOLVED` | Cierra sin respaldo, incluso con controles pendientes, objeciones o recursos agotados. |
| `{"mode":"reviewed","proposal_id":"proposal_1"}` | `CLOSED_REVIEWED_DECLARED` | Conserva la interpretación y revisión declaradas vinculadas al contexto exacto. |

`results_only` exige todos los controles ejecutados, ninguna sugerencia material pendiente y presupuesto temporal vigente. `reviewed` añade las puertas de propuesta y aprobación que se describen abajo. `unresolved` no admite rama seleccionada. Campos antiguos `requested_status`, `supported` y `conclusion` no forman parte de ninguna entrada de cierre.

Los estados previos son `READY`, `RUNNING`, `CHECKED`, `BUDGET_EXHAUSTED`, `REVIEW_REQUIRED`, `PROPOSED_DECLARED`, `REVIEW_APPROVED_DECLARED` y `REVIEW_REJECTED_DECLARED`. `CHECKED` significa que terminaron las comprobaciones; puede haber resultados negativos. La aprobación revisada sigue siendo una declaración, no certificación semántica.

Cada cierre conserva `state`, `mode`, `superseded`, `exploratory_revision`, `evidence_mode` y `result_evidence_mode`. El modo de evidencia de un cierre revisado siempre es `DECLARED_REVIEW`; `result_evidence_mode` describe por separado los tipos de controles. Los cierres de resultados y revisados incluyen `generated_results`; el revisado conserva borrador, revisión, hashes y `assurance: REVIEW_DECLARED_NOT_SEMANTICALLY_VERIFIED`.

## Propuestas, revisión y vinculación

El borrador identifica autor declarado, rama seleccionada, entre 1 y 32 afirmaciones con ID, texto, referencias a controles, alcance, supuestos y límites; explica todas las ramas y declara límites generales. Antes de registrarlo deben haberse ejecutado todos los controles; todos los críticos históricos y los de la rama seleccionada deben dar `pass`. Una alternativa no crítica puede fallar sin impedir proponer otra rama.

La revisión cubre exactamente todas las afirmaciones y sus referencias, examina un control marcado `critical` y `challenge`, registra una explicación alternativa, evalúa alcance y declara incertidumbres. `approve` exige que todas las afirmaciones reciban `supported`; `reject` no habilita cierre. Un `manual_review` del plan no sustituye esta revisión de la propuesta.

Autor y revisor deben tener etiquetas distintas tras NFKC, casefold y normalización de espacios. Esto evita una autoidentificación evidente; **no autentica personas, independencia ni honestidad**. Un revisor que mienta puede aprobar una afirmación falsa. Esa afirmación queda declarada en `CLOSED_REVIEWED_DECLARED`, nunca como hecho calculado. Las pruebas incluyen deliberadamente ese límite.

El contexto SHA-256 incluye caso, planes, snapshots y sello del runtime, resultados, intentos, rondas y todas las sugerencias. Excluye el reloj dinámico, lecturas y los eventos de propuesta/revisión. El SHA de propuesta incluye versión, caso, contexto y borrador completo. Una revisión apunta al hash exacto; no basta reutilizar un ID.

Cualquier sugerencia nueva, incluso de presentación, invalida propuestas pendientes por cambiar su contexto. Leer `status`, `verify` o `review-packet` no las invalida. El paquete puede mostrar una propuesta antigua con `context_current: false`; ni revisarla ni usarla para cerrar queda permitido. Cada propuesta acepta una sola revisión. Un borrador idéntico en el mismo contexto no puede reenviarse tras un rechazo. Una variante consume recursos y queda en el historial.

## Presupuesto global y tiempo

Cada intento de control consume su `cost_units` antes de ejecutarse, aunque falle o se interrumpa. Cada propuesta persistida y cada revisión persistida consumen 1 unidad adicional. Máximo 3 propuestas y 3 revisiones por caso, compartidos por todas las rondas y reaperturas. Una entrada rechazada antes de persistir no consume unidades. El estado expone `checks_used`, `proposals_used`, `reviews_used`, `units_used`, `rounds_used`, `elapsed_seconds` y `limits`.

`max_checks` cuenta solo intentos de adaptadores; `max_units` suma también propuestas y revisiones. Las unidades son costes declarados del protocolo: no son facturación, tokens ni medición de todo el trabajo externo. Leer, registrar una sugerencia, generar un informe o cerrar no consume unidades.

El reloj cuenta vida civil del caso, incluido tiempo inactivo. Se comprueba antes de comenzar controles, registrar propuestas/revisiones, incorporar rondas y cerrar resultados/revisión. Si el plazo vence, queda el cierre inconcluso. Un intento síncrono iniciado dentro de plazo puede terminar después; se conserva su resultado sin permitir nuevas operaciones que requieran tiempo vigente. No hay interrupción dura de llamadas ni control del trabajo externo. Un retroceso del reloj observado al escribir se rechaza antes de cambiar el journal.

La verificación histórica evalúa las puertas de cada evento con su timestamp registrado. Un cierre correcto no caduca retroactivamente cuando se vuelve a leer semanas después. Esto no certifica la fecha ante terceros ni protege frente a manipulación completa del reloj y expediente.

## Sugerencias y rondas

Una sugerencia tiene exactamente `type`, `affected_check_ids`, `reason`, `decision_impact`. `presentation` se registra como `KEEP_SCOPE`; `new_objective`, como `OUT_OF_SCOPE`; ambas admiten afectados vacíos. `material_evidence` exige controles existentes afectados, produce `REVIEW_REQUIRED` y marca cierres previos como `superseded`. La relevancia de esta clasificación es declarada. Una sugerencia idéntica se rechaza.

```powershell
python -B -m pse tip casos/mi_caso tip.json
python -B -m pse revise casos/mi_caso plan_revision.json
python -B -m pse run casos/mi_caso
```

Una ronda requiere objeciones materiales pendientes y presupuesto original suficiente. Mantiene exactamente versión, caso, objetivo, alcance, criterios, límites y presupuesto; solo añade preguntas, ramas y controles. Cada control nuevo incluye `revises` con afectados pendientes, conserva cobertura y marcas crítico/desafío. Todos los afectados necesitan control nuevo. El vínculo acredita estructura, no pertinencia.

Los negativos históricos permanecen. Un crítico fallido no queda borrado por un control nuevo favorable. La ronda se marca exploratoria y conserva los contadores globales. Cambiar la pregunta o criterio original exige caso nuevo con antecedente explícito; no crea independencia estadística.

## Integridad, transiciones y recuperación

El caso guarda `journal.json` encadenado por SHA-256 y `rounds/r001/plan.json`, `sources/`, etc. El sello incluye los cinco módulos: `__init__.py`, `__main__.py`, `engine.py`, `adapters.py`, `claims.py`. Se comprueban planes, inventario, fuentes, tipos de resultados, costes, orden de intentos y contratos de eventos. Replay vuelve a aplicar las mismas puertas de propuesta, revisión, ronda y cierre. Recalcular la cadena no legitima una transición contradictoria.

La coherencia local no es firma, custodia inviolable ni defensa frente a alguien capaz de reemplazar todo el expediente. Conservar versión del runtime y copias externas cuando se necesite custodia. Una modificación de módulos invalida casos sellados con su versión anterior; no hay migración automática.

Las escrituras usan sustitución atómica y bloqueo exclusivo `.pse.lock`. No hay varios escritores simultáneos. `run` nunca repite controles terminados. Si encuentra un intento sin resultado por interrupción, lo registra inconcluso, conserva su coste y sigue con los demás controles permitidos. No se recupera el éxito mediante un reintento oculto.

Tras un cierre forzoso puede quedar el bloqueo: comprobar que no existe ningún escritor, conservar copia y retirar solo el bloqueo obsoleto. Ejecutar `verify`. No editar planes, resultados o hashes para hacer pasar auditoría. Ante fallo de disco o snapshot parcial, conservar caso y error; no existe reparación automática ni garantía frente a pérdida de alimentación.

## Informes

`render_report` muestra resultados mediante plantillas y hechos tipados. Todo texto externo se presenta como entrada o declaración: objetivos, etiquetas, parámetros, citas, motivos, juicios y revisiones. El `summary` libre del adaptador no se promociona a conclusión. Markdown/HTML se escapa en texto y los registros JSON se presentan en bloques literales indentados, sin cierres de fence controlados por el usuario. La integridad y el escape no convierten una afirmación aportada en verdadera.

## API Python

```python
from pse import engine
engine.init_case(plan_path, out)                 # crea carpeta nueva y devuelve estado
engine.branch_view(case, branch_id)             # vista inicial de una rama
engine.run_case(case)                           # ejecuta pendientes una vez
engine.propose_case(case, draft)                # proposal_id, SHA, contexto, draft
engine.review_packet(case, proposal_id)         # lectura sin aprobar
engine.review_case(case, review)                # revisión persistida
engine.close_case(case, decision)               # devuelve estado
engine.add_tip(case, tip)                       # {tip, status}
engine.revise_case(case, plan_path)              # ronda append-only
engine.status(case)                            # estado validado
engine.verify_case(case)                        # resumen de integridad local
engine.render_report(case)                      # Markdown; no escribe
engine.read_json(path)                          # lectura JSON estricta
engine.validate_plan(plan)                      # copia validada
```

Rutas aceptan `str` o `pathlib.Path`. Violaciones de contrato levantan `EngineError`, subclase de `ValueError`; errores de escritura pueden levantar `OSError`. La salida de estado incluye caso, estado, ronda, presupuesto, resultados, propuestas, revisiones, sugerencias pendientes, cierres, marca exploratoria e integridad verificada.

`branch_view` solo opera antes del primer intento y expone objetivo, alcance, criterio, su pregunta, su rama, fuentes y límites. No muestra otras hipótesis ni resultados; tampoco impide leer el plan completo a quien tenga acceso a archivos. La separación de contextos de trabajo debe organizarla el ejecutor.

Las funciones puras de `claims.py` validan contratos de borrador/revisión, generan proyecciones de hechos tipados y escapan texto. No leen archivos, reloj ni modelos. `adapters.validate`, `source_paths` y `execute` conservan su interfaz cerrada. Ampliar métodos requiere cambiar y comprobar el código.
