# Resultados y límites de las pruebas asistidas

Actualización: 27 de octubre de 2026. Estos pilotos pertenecen al desarrollo de PSE asistido por IA. No son capacidades autónomas del motor General 2.0 ni una validación externa de su eficacia.

| Prueba | Resultado observado | Alcance |
|---|---|---|
| Piloto numérico sobre datos históricos | PSE redujo el error del modelo original un 11,16% y un 12,34% en dos regímenes. Frente a la IA control: 6,81% y 21,94%. | No alcanzó el umbral previo de mejora de al menos 10% frente al control en ambos regímenes. Una pareja de ejecuciones no acredita superioridad general. |
| Síntesis documental histórica de Venus | Un juez asignó 16/20 a ambos métodos; el otro 18/20 a ambos. No identificaron errores mayores o graves. | Ventaja no demostrada. Ocho fuentes condensadas, dos rondas y dos jueces internos de IA con etiquetas enmascaradas; sin comprobación física ni revisión experta externa. |

Se conservaron criterios, negativos y límites, sin retocar resultados para declarar éxito. Las métricas de las dos pruebas no se suman ni se comparan directamente entre sí.

Los dos métodos del piloto documental propusieron controles útiles y complementarios. Esas propuestas no se ejecutaron sobre espectros ni constituyen una mejora ya implementada en este código.

## Archivos de resultados

- [Resultado numérico](evidencia/numerico_resultado.json).
- [Resultado documental](evidencia/venus_resultado.json).

Son copias exactas de los resultados locales conservados. Este repositorio no incorpora los datos históricos, artículos completos, respuestas, jueces ni todos los materiales de custodia de los pilotos; por tanto, **estos dos JSON no bastan para reproducir las investigaciones**. Los ejemplos y tests del motor sí se suministran con el código.

La conclusión defendible es que existe infraestructura técnica comprobada y evidencia investigadora todavía limitada. La incertidumbre sobre la ventaja incremental permanece abierta.
