# Comprobaciones disponibles

PSE General 2.0 incorpora cinco adaptadores locales. El ejecutor suministra la pregunta, los datos y criterios; el programa aplica las comprobaciones descritas aquí. Ningún adaptador llama a una IA, accede a Internet, instala software o ejecuta comandos arbitrarios.

Un resultado `pass` significa que se cumple **el criterio registrado de ese check**, no que se haya demostrado una teoría. `fail` conserva un resultado adverso y `inconclusive` declara una limitación. Errores de entrada o lectura se registran por el motor como intentos fallidos que consumen presupuesto.

## Contrato común

Cada check incluye `method` y `params`, además de los metadatos del plan. Se rechazan campos desconocidos dentro de `params`. Los números admiten números JSON o cadenas decimales, incluidos exponentes; se rechazan booleanos, NaN, infinito y representaciones demasiado grandes. Para conservar exactamente los decimales originales se recomiendan cadenas.

Los resultados distinguen `kind: computed` (cálculo), `documentary` (correspondencia literal) y `declared` (juicio aportado). Esa distinción debe conservarse en el informe final.

La proyección de resultados de 2.0 deriva el tipo del método, usa plantillas cerradas y hechos tipados, y agrupa las etiquetas, citas, nombres, parámetros y dictámenes en `declared_inputs`. El campo `summary` de un adaptador nunca se convierte en conclusión. Los valores numéricos se vuelven a representar a partir del racional exacto. Los nombres de región se muestran como entradas; el hecho calculado identifica la región por su posición en la lista. Una cita localizada o una revisión registrada no autentican su contenido. El [contrato de cierre](CONTRATO_CIERRE.md) explica la revisión de afirmaciones.

API para el motor: `validate(check)` valida el contrato; `source_paths(check)` enumera todos los archivos que el check consumirá; `execute(check, root)` devuelve `status`, `kind`, `summary` y `details`. Los archivos consumidos deben copiarse y sellarse antes de ejecutar, preservando sus rutas relativas. Estas funciones no escriben archivos.

## 1. arithmetic - aritmética exacta

```json
{"method":"arithmetic","params":{"expression":"0.1 + 0.2","expected":"0.3","tolerance":"0"}}
```

Admite `+`, `-`, `*`, `/`, `**`, paréntesis y variables declaradas en `variables`, por ejemplo `{"x":"2"}`. Compara la diferencia absoluta contra `tolerance` (por defecto cero), mediante fracciones racionales exactas. No usa `eval` ni admite llamadas, atributos, importaciones o instrucciones de Python.

Límites: expresión de hasta 2.048 caracteres y 160 nodos, profundidad 32, hasta 32 variables; exponentes enteros entre -12 y 12; racionales de hasta 4.096 bits. El valor cero elevado a cero o a un exponente negativo se rechaza. Resultado `computed`; comprueba la expresión aportada, no su interpretación física ni una demostración general.

## 2. numeric_interval - un escalar con error acotado

```json
{"method":"numeric_interval","params":{"value":"5","error":"0.1","regions":[{"id":"H1","lower":"4","upper":"6"},{"id":"H2","lower":"8","upper":"10"}],"expected":"H1"}}
```

Construye `[value-error, value+error]` y busca una única región que lo contenga por completo. Las regiones son cerradas y no pueden solaparse ni compartir frontera. `expected` identifica la clasificación que se quiere comprobar; `null` comprueba que no haya discriminación. Se admiten hasta 32 regiones.

Resultado `computed`. El error acotado es un dato suministrado, no un intervalo de confianza estimado. No autentica la medición ni convierte unidades. Comparar un valor ya conocido es desarrollo o revisión, no prospectividad demostrada.

## 3. csv_compare - comparación pareada de error absoluto medio

```json
{"method":"csv_compare","params":{"path":"data/paired.csv","id_column":"id","truth_column":"truth","baseline_column":"baseline","candidate_column":"candidate","min_absolute_improvement":"0.2","min_relative_improvement":"0.1","metric":"mae"}}
```

CSV mínimo:

```csv
id,truth,baseline,candidate
a,0,2,1
b,4,6,4
```

Calcula MAE de la referencia y del candidato sobre las mismas filas. La mejora absoluta es `MAE_referencia - MAE_candidato`; la relativa divide esa diferencia por `MAE_referencia`. Deben cumplirse **ambos umbrales** previamente fijados. Ambos son no negativos y al menos uno debe ser positivo: una igualdad no se anuncia como ventaja. El mínimo relativo debe ser menor o igual que 1; 0.1 significa 10% y 1 significa 100%. Se rechaza un mínimo relativo mayor que 1 porque un MAE no negativo impide mejorarlo en más del 100%. `metric` es opcional y solo admite `mae`.

Se rechazan IDs vacíos, duplicados o con espacios laterales; cabeceras repetidas, filas incompletas/irregulares, valores no finitos y archivos sin filas. No se excluyen silenciosamente observaciones. Si la referencia tiene MAE cero, el resultado es `inconclusive`: la mejora relativa no está definida y no se declara ventaja. Un empeoramiento conserva su valor negativo. Máximo 10.000 filas y 2.000.000 bytes por archivo.

La mejora absoluta máxima posible en las filas suministradas es el MAE de la referencia: correspondería a un candidato con MAE cero. Si el mínimo absoluto fijado supera ese máximo, 2.0 devuelve `inconclusive` con `design_status: threshold_above_comparator_ceiling`. Conserva todas las métricas, los umbrales y `max_possible_absolute_improvement`; no relaja el criterio ni rescata el resultado. La igualdad sí puede satisfacerse con un candidato perfecto. Este techo dependiente de datos se conoce al leer esas filas, no por anticipación sin datos.

Si no hay un umbral absoluto por encima del techo pero el MAE de referencia es cero, `design_status` es `relative_improvement_undefined`. En el resto de casos es `feasible_on_supplied_rows`, que solo indica factibilidad aritmética de los umbrales en esas filas. No acredita un diseño científico adecuado. Por ejemplo, referencia MAE 0.4 y mínimo absoluto 0.5 producen techo aunque el candidato mejore; las métricas favorables o adversas se conservan.

Resultado `computed`, descriptivo y condicionado a la cohorte. No estima significación, dependencia, causalidad ni generalización fuera de los datos. La etiqueta `truth` nombra la columna suministrada, no acredita una verdad externa.

## 4. text_evidence - correspondencia documental

```json
{"method":"text_evidence","params":{"path":"sources/note.txt","quote":"frase literal","locator":"párrafo 2"}}
```

Busca una cita exacta, sensible a mayúsculas y espacios, dentro de un texto UTF-8 local. Puede incluir `sha256` de 64 caracteres hexadecimales y exigir coincidencia de bytes. Registra la huella real. Resultado `documentary`.

La página/párrafo/localizador es declarado: el programa no interpreta su numeración ni comprueba verdad, autoría, actualidad, exhaustividad o que la cita justifique una conclusión. Los PDF no se interpretan directamente; deben conservarse la extracción y su procedencia fuera de este check.

## 5. manual_review - juicio registrado, con evidencia localizable

```json
{"method":"manual_review","params":{"path":"review.json","evidence":[{"path":"sources/note.txt","quote":"frase literal","locator":"párrafo 2"}]}}
```

`review.json` debe contener exactamente:

```json
{"reviewer":"Identidad declarada del revisor","method":"Método aplicado","verdict":"pass","finding":"Conclusión de la revisión","limitations":["Límite pertinente"],"evidence_paths":["sources/note.txt"]}
```

`verdict` puede ser `pass`, `fail` o `inconclusive`. Se exige una lista de límites no vacía y correspondencia exacta entre `evidence_paths` y las fuentes de `params.evidence`. Todos los respaldos documentales deben encontrarse; si alguna cita o huella falla, el check queda `fail`, aunque el revisor haya escrito `pass`. La revisión no puede usarse como su propia fuente. Se admiten de 1 a 32 respaldos.

Resultado **siempre `declared`**. Se verifica presencia, estructura y correspondencia del registro; no identidad del revisor, independencia ni validez de su juicio. Una IA puede redactar una revisión, pero esa revisión no se convierte en evidencia empírica por registrarla. Una revisión humana o experimental futura necesita su propio plan; estos archivos sellados representan material ya aportado.

## Archivos y protección operativa

Solo rutas relativas dentro de la raíz, sin `..`, rutas absolutas, unidades, flujos alternativos de Windows ni nombres de dispositivos. Se rechazan enlaces simbólicos y puntos de reanálisis en la ruta suministrada. Las fuentes deben ser archivos regulares de hasta 2.000.000 bytes. No hay ejecución arbitraria ni acceso de red. Estos límites reducen errores de uso; no constituyen un entorno de seguridad contra un usuario con control del ordenador ni eliminan carreras externas de escritura.

## Procedencia y validación

La representación mediante `Fraction` retoma el principio usado en `PSE-R/domains/numeric_interval.py`: respetar los decimales registrados sin introducir tolerancias ocultas. La implementación de PSE General y sus adaptadores se escribió para esta entrega; no incorpora inventarios, correspondencia, datos privados ni el núcleo histórico de PSE-R.

`tests/test_adapters.py` comprueba fronteras decimales, soluciones erróneas, expresiones no admitidas, límites de cálculo, comparadores con techo, filas duplicadas, citas falsas, revisiones sin respaldo, tipos de evidencia y rutas inseguras. Son pruebas técnicas de desarrollo; no demuestran superioridad científica del PSE.
