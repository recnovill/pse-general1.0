# Contrato de resultados y cierre 2.0

Un cálculo correcto no demuestra que una interpretación ajena a ese cálculo sea verdadera. PSE 2.0 separa los resultados del programa de las afirmaciones aportadas y de su revisión declarada. Este contrato corrige la posibilidad de asociar una conclusión libre a controles triviales y presentarla como cierre respaldado automáticamente.

## Tres cierres explícitos

| Entrada exacta | Estado | Significado |
|---|---|---|
| `{"mode":"results_only"}` | `CLOSED_RESULTS` | Registra los resultados de todos los checks, incluidos negativos e inconclusos, sin seleccionar una interpretación. Exige controles terminados y ninguna objeción material pendiente. |
| `{"mode":"unresolved","reason":"Motivo declarado","limitations":["Límite declarado"]}` | `CLOSED_UNRESOLVED` | Cierra sin conclusión respaldada. Puede usarse con recursos agotados. |
| `{"mode":"reviewed","proposal_id":"proposal_1"}` | `CLOSED_REVIEWED_DECLARED` | Registra una propuesta revisada y aprobada de forma declarada, vinculada al mismo contexto y dentro de presupuesto. |

Los campos de 1.0 `requested_status`, `supported` y `conclusion` no forman parte del contrato de cierre 2.0. Los expedientes 1.0 se conservan con su runtime original; no se transforma su historia en una revisión 2.0.

## Qué genera el programa

`pse.claims.generated_results(plan, results)` devuelve un registro por check con `method`, `status`, `kind`, `statement`, `facts`, `limitations` y `declared_inputs`. El estado pendiente se conserva si todavía no hay ejecución. El método determina el tipo de evidencia; un resultado con tipo incompatible se rechaza.

`statement` y `limitations` proceden de plantillas cerradas. `facts` contiene valores racionales normalizados, booleanos de coincidencia documental, huellas, cantidades y estados enumerados. La representación decimal se calcula a partir del racional, sin reutilizar texto libre. No se usa `summary` como conclusión.

La proyección rechaza campos tipados ausentes o incoherentes: diferencias y tolerancias aritméticas incompatibles, intervalos que no corresponden a las entradas, mejoras MAE que no cuadran con los errores, umbrales distintos del plan, estados de techo incorrectos o un `pass` que contradice esas métricas. También exige coherencia de coincidencias documentales y dictámenes declarados con el estado. Es una validación local de estructura y aritmética; no relee las fuentes ni autentica su contenido.

`declared_inputs` contiene los identificadores, parámetros, etiquetas, localizadores y textos aportados. Un nombre de región como «teoría demostrada» no se convierte en un hecho calculado: el resultado numérico refiere su posición en la lista, desde 1. La cita que aparece en una fuente sigue siendo texto aportado; solo se comprueba su presencia literal. El nombre del revisor, su método, su hallazgo y sus límites siguen siendo declaraciones incluso cuando sus respaldos documentales están presentes.

Los errores e interrupciones no aportan hechos favorables. Se conserva un estado inconcluso y se separa el diagnóstico como texto del intento. Los informes deben usar `escape_markdown` para texto ajeno: neutraliza marcado, HTML, caracteres de control y cambios de dirección invisibles. La serialización por sí sola no concede valor probatorio.

## Propuesta declarada

El candidato tiene exactamente esta estructura:

```json
{
  "author": "Autor declarado",
  "selected_branch_id": "b1",
  "claims": [{
    "id": "claim_1",
    "text": "Afirmación acotada",
    "check_ids": ["c1"],
    "scope": "Alcance de esta afirmación",
    "assumptions": [],
    "limitations": ["Límite de esta afirmación"]
  }],
  "reasons_by_branch": {"b1": "Razón", "b2": "Razón", "b3": "Razón"},
  "limitations": ["Límite global"]
}
```

Se admiten de 1 a 32 afirmaciones con IDs únicos y referencias no repetidas a checks ejecutados en el caso. Se exige una razón para cada rama; no se admiten campos extra. Los textos no pueden estar vacíos ni tener espacios laterales. `assumptions` admite entre 0 y 32 entradas; los límites de cada afirmación y globales, entre 1 y 32. El validador puro devuelve una copia sin modificar la entrada.

El motor comprueba además que todos los controles están completos, que pasan los críticos y los de la rama seleccionada, que no hay objeciones pendientes y que queda presupuesto. Estos requisitos estructurales no prueban que un check sea pertinente para el texto de una afirmación.

## Revisión vinculada

La propuesta registrada incluye `proposal_id`, `proposal_sha256`, `context_sha256` y `draft`. El motor calcula la huella de la propuesta sobre el candidato completo y su contexto. El contexto incluye planes, snapshots, runtime, intentos, resultados y sugerencias. Una lectura de estado no cambia la huella; una sugerencia nueva sí cambia el contexto y deja obsoleta una propuesta pendiente.

El paquete de revisión muestra la propuesta, sus huellas, resultados y límites; no propone aprobar. La revisión tiene exactamente:

```json
{
  "proposal_id": "proposal_1",
  "proposal_sha256": "64 caracteres hexadecimales de la propuesta",
  "reviewer": "Revisor declarado",
  "verdict": "approve",
  "claims": [{
    "claim_id": "claim_1",
    "verdict": "supported",
    "reason": "Razón específica",
    "check_ids": ["c1"]
  }],
  "challenge": {
    "check_id": "c3",
    "finding": "Qué mostró el control crítico",
    "alternative_explanation": "Explicación alternativa considerada"
  },
  "scope_assessment": "Evaluación declarada del alcance",
  "uncertainties": ["Incertidumbre restante"]
}
```

Se cubren exactamente todas las afirmaciones y todos los checks citados por cada una. El desafío referencia un check marcado simultáneamente `critical: true` y `challenge: true`. Los veredictos de afirmación son `supported`, `unsupported` o `uncertain`. `approve` requiere que todas estén `supported`. `reject` se conserva como rechazo incluso si alguna o todas las afirmaciones aparecen como `supported`; nunca habilita el cierre revisado.

Autor y revisor deben tener etiquetas diferentes tras normalización Unicode NFKC, mayúsculas/minúsculas y espacios. Esto impide duplicados triviales; no autentica a nadie, no impide que una persona use dos alias y no demuestra independencia. La revisión puede mentir o equivocarse. Una falsedad aprobada por un revisor solo puede quedar registrada como juicio declarado, nunca como verdad automática. El adaptador `manual_review` tampoco sustituye esta revisión de una propuesta concreta.

El motor permite una revisión por propuesta, hasta tres propuestas y tres revisiones por caso. Cada propuesta o revisión aceptada consume una unidad global adicional a los checks. Una propuesta idéntica en el mismo contexto se rechaza; reenviarla no borra un rechazo. El cierre revisado vuelve a comprobar contexto, controles, objeciones y presupuesto. El replay del registro valida los mismos contratos; los tiempos históricos se evalúan en la fecha registrada del evento.

## Alcance de la garantía técnica

Las pruebas comprueban contratos, referencias, presupuestos, transiciones y separación de declaraciones; no demuestran una mejora universal de investigación. SHA-256 permite detectar incoherencias frente al registro local, pero no autentica autoría ni protege contra quien pueda reescribir el expediente completo y sus huellas.

`pse.claims` es un módulo puro: no lee fuentes, no escribe, no consulta el reloj, no llama a modelos ni accede a la red. La persistencia y los sellos pertenecen al motor. El programa puede exigir una revisión y hacer visible su alcance, pero la calidad semántica requiere juicio y evidencia adecuados al problema.
