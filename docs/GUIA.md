# Guía de capacidades y uso — 2.0

PSE organiza el paso de una necesidad a un resultado revisable. El protocolo guía al investigador o asistente; el programa ejecuta métodos concretos y registra las decisiones.

## Cómo se trabaja

1. Aclarar qué se quiere decidir y mejorar la formulación de la pregunta.
2. Preparar una referencia competente, una alternativa distinta y una crítica.
3. Fijar pruebas y presupuesto antes de ver los resultados.
4. Ejecutar y conservar lo favorable, lo adverso y lo inconcluso.
5. Registrar observaciones o proponer una interpretación limitada.
6. Revisar esa propuesta exacta, verificar el expediente y cerrar.

Las ramas no votan. Una revisión puede rechazar todas las alternativas; agotar recursos no demuestra ninguna.

## Comprobaciones incluidas

| Método | Qué comprueba | Límite |
|---|---|---|
| Aritmética | Operadores admitidos mediante fracciones exactas frente a un valor esperado. | No demuestra cualquier teorema ni adecuación física. |
| Intervalos | Un escalar con error frente a regiones declaradas. | No valida la medición, el error ni el significado de la región. |
| CSV | MAE pareado y mínimos absoluto y relativo fijados. | No prueba causalidad, significación ni generalización. |
| Citas | Presencia exacta en una fuente local. | No acredita verdad, actualidad o interpretación. |
| Revisión documental | Juicio registrado y evidencia local requerida. | No autentica identidad ni independencia. |

El control CSV identifica cuando el mínimo absoluto supera el MAE observado de referencia: ni un candidato perfecto podría cumplirlo. Conserva métricas y criterio; no reajusta el experimento.

## Cómo se cierra

**Solo resultados:** completar controles y cerrar con `{"mode":"results_only"}`. El informe muestra hechos del cálculo y entradas declaradas separadas. Puede incluir fallos; no equivale a aprobar una hipótesis.

**Interpretación revisada:** registrar un borrador estructurado con `propose`, obtener su paquete con `review-packet`, registrar la revisión con `review` y cerrar con `reviewed`. Cada afirmación referencia controles reales. La revisión cubre todas, examina un contraste crítico y se vincula al digest del texto y contexto. Un cambio de evidencia invalida su reutilización. Un fallo crítico impide esta vía.

**Sin resolución:** usar `unresolved` con razón y límites. Permite terminar cuando faltan pruebas o se agotan recursos.

El nuevo estado `CLOSED_REVIEWED_DECLARED` dice exactamente qué hay: una interpretación revisada y declarada. Un revisor puede equivocarse o mentir; ese juicio no se convierte en verdad calculada.

## Foco y presupuesto

Controles, unidades, tiempo y rondas tienen límites comunes. Las propuestas y revisiones aceptadas consumen una unidad cada una, con un máximo global de tres de cada tipo. Los fallos no reinician el presupuesto.

Una sugerencia material identifica la decisión afectada. Una mejora de presentación no reabre un caso ya cerrado; una nueva sugerencia sí invalida una propuesta pendiente para que se revise su contexto actual. El tiempo se comprueba entre llamadas y al cerrar, sin interrumpir por fuerza un cálculo iniciado. Un cierre válido sigue siendo verificable después de vencer el tiempo.

## Uso general

Puede organizar decisiones técnicas, análisis de documentos, diseño, planificación o investigación. La cobertura automática sigue siendo la de los cinco métodos incluidos. El asistente necesita herramientas y criterio externos para bibliografía, modelos especializados, ensayos físicos o evaluación humana.

Ejemplo de encargo: «Compara dos maneras de estimar tiempos de entrega, con una referencia competente y una mejora mínima útil fijada antes de la evaluación». El sistema conserva un resultado negativo si no se cumple el criterio.

La calidad de las preguntas, la relevancia de los controles y la superioridad frente a otro método siguen necesitando evaluación. Los seis ejemplos del repositorio son conocidos durante desarrollo. Consulta [QA](QA_RESULT.md), [límites](ALCANCE.md) y [contrato técnico](README_ENGINE.md).
