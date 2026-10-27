# Alcance y límites — 2.0

## Implementado

Motor local con planes versionados, cinco adaptadores, preservación de fuentes y resultados, presupuesto global, registro de sugerencias, revisiones de plan, propuestas, revisión de afirmaciones y tres formas distintas de cierre. El reporte de resultados se genera desde campos tipados; los textos aportados se identifican como declarados.

La versión 2.0 impide adjuntar una conclusión arbitraria al cierre automático de resultados. Para una interpretación exige afirmaciones con referencias y revisión vinculada al texto y contexto. También detecta el umbral absoluto de mejora imposible frente al error observado del comparador.

## Lo que sigue necesitando criterio

La pertinencia de una prueba para una afirmación, la calidad de una pregunta, la veracidad de las fuentes, los supuestos científicos y la fuerza de una explicación no se resuelven validando un esquema JSON.

Un revisor falso o equivocado puede declarar apoyo a una afirmación falsa. El motor verifica la estructura y la continuidad de esa revisión; su estado permanece `CLOSED_REVIEWED_DECLARED`. No autentica personas, garantiza independencia ni mide la calidad semántica de sus razones.

La separación entre ramas no demuestra independencia. Las pruebas de desarrollo y QA no miden utilidad incremental en investigación, creatividad, decisiones, comprensión ni resultados comerciales. Hace falta un comparador competente con los mismos recursos y una evaluación fijada de antemano.

## Integridad y ejecución

Los hashes locales detectan discrepancias con los recibos que se conservan. El replay comprueba transiciones y contratos del registro. Quien controla todos los archivos y el runtime puede fabricar un expediente completo: no hay firma externa, reloj de confianza ni custodia independiente.

El presupuesto se aplica a las operaciones del motor. No mide todo el trabajo de una persona o un modelo fuera del programa. El tiempo se comprueba entre operaciones; no cancela por fuerza un adaptador en ejecución.

No hay red ni llamadas a modelos incorporadas. El runtime no es una zona aislada para ejecutar código externo. La distribución legible y los tests facilitan revisión; no son certificación de seguridad.

## Versiones y evidencia

Los casos sellados de 1.0 se conservan con su runtime original; no se reetiquetan como 2.0. Los resultados adversos de la prueba integral anterior siguen siendo adversos. La corrección del software no demuestra retrospectivamente una mejora que aquella prueba no encontró.

El estado de pruebas de esta edición se documenta en [QA_RESULT.md](QA_RESULT.md) y [VALIDACION_ENTREGA.json](VALIDACION_ENTREGA.json). Los documentos de `history/1.0` son únicamente históricos.
