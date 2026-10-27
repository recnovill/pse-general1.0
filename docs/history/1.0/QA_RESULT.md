# Resultado de QA técnico - PSE General 1.0

Fecha: 26/10/2026. Aceptación del runtime y de sus ejemplos de desarrollo dentro de la matriz prevista. No queda un fallo material conocido en el alcance comprobado. Esta revisión no acredita superioridad científica, independencia estadística entre agentes ni validación externa.

## Resultado ejecutado

- **87 pruebas pasan**, sin fallos, errores ni omisiones: 34 de adaptadores, 29 del motor y 24 adversariales de revisión independiente.
- Cuatro ejemplos completos desde una copia aislada: cálculo, comparación de datos, comparación adversa y lectura documental con revisión declarada.
- **11 invocaciones** de comandos en la prueba portable, con tres rechazos esperados: cierre antes de ejecutar, sobrescritura de informe y sobrescritura de caso.
- Los bytes del runtime en la copia coinciden con la raíz final al terminar las pruebas. Esta copia para GitHub conserva esos bytes del programa y presenta la documentación como texto. El PDF y el ZIP de la entrega original no forman parte de esta copia.

| Ejemplo | Resultado observado | Tipo de respaldo |
|---|---|---|
| calculo | CLOSED_SUPPORTED; valor 14, contraejemplo -6 y abstención con error amplio | COMPUTED |
| datos | CLOSED_SUPPORTED; MAE de referencia 2, candidato 1; mejora absoluta 1 y relativa 0.5 | COMPUTED |
| datos_sin_mejora | CLOSED_UNRESOLVED; MAE del candidato 3, mejora -1; cierre favorable rechazado | COMPUTED |
| documentos | CLOSED_SUPPORTED dentro del alcance documental | DECLARED_REVIEW |

`CLOSED_UNRESOLVED` impide atribuir la ventaja solicitada al candidato adverso. No borra el resultado negativo conocido.

## Comandos y evidencia

Entorno observado: Windows, Python **3.12.14**, biblioteca estándar. No se instaló un paquete para ejecutar el PSE.

Desde la raíz del paquete:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/run_examples.py --out runs/demo_001
```

La ejecución final de los tests se realizó en esta copia local aislada:

```text
_build/qa_portability/ad11615396764892a7b1b1c9e512836c/
```

Se copiaron solamente `pse/`, `examples/`, `scripts/run_examples.py` y los tests. No se copiaron PSE histórico, PSE-R, bases de datos externas ni dependencias de esos árboles. Es una reubicación dentro de la nueva raíz; no es una prueba en otro ordenador ni otro sistema operativo.

Intérprete utilizado por la ejecución local:

```text
Python 3.12.14, entorno local de comprobación
```

En la copia se ejecutaron estos comandos; los señalados con “rechazo esperado” devolvieron código 2 y todos los restantes código 0:

```powershell
python -B scripts/run_examples.py --out runs/examples
python -B -m pse init examples/calculo/plan.json --out runs/cli_case
python -B -m pse branch runs/cli_case base
python -B -m pse close runs/cli_case --decision examples/calculo/decision.json
# Rechazo esperado arriba: todavía no se han ejecutado los controles.
python -B -m pse run runs/cli_case
python -B -m pse close runs/cli_case --decision examples/calculo/decision.json
python -B -m pse verify runs/cli_case
python -B -m pse status runs/cli_case
python -B -m pse report runs/cli_case --out runs/cli_report.md
python -B -m pse report runs/cli_case --out runs/cli_report.md
# Rechazo esperado arriba: informe existente, bytes preservados.
python -B -m pse init examples/calculo/plan.json --out runs/cli_case
# Rechazo esperado arriba: caso existente.
python -B -m unittest discover -s tests -v
```

El último comando produjo `Ran 87 tests in 13.001s / OK`. Las 11 invocaciones cuentan el runner y los diez comandos CLI anteriores; la suite se registra aparte.

Trazas locales de construcción, excluidas del paquete compartible: `QA_PORTABLE_RESULT.json` y `QA_UNITTEST_LOG.txt` dentro de la copia indicada. El recibo local conserva salidas, códigos, versiones y SHA-256 de código y tests. El log de la suite se incluye aquí en `TEST_RESULTS.txt`. Los resultados completos de los ejemplos están en `runs/examples/RESULTADOS_EJEMPLOS.json` de esa copia.

SHA-256 del motor comprobado:

```text
pse/engine.py
3be87357f24c96671b158132e2fce20f441bf4475b92a10bf8d3ee4401cf0423
```

## Dos rondas y correcciones

1. Primera ronda: 14 pruebas adversariales y los cuatro ejemplos completos. Se detectó que el README omitía `--out` en el comando del runner; quedó corregido a una carpeta nueva explícita. No se detectó un fallo funcional del motor en esa batería.
2. Segunda ronda: ampliación hasta 24 adversariales para completar las cuotas de checks/unidades, preservación de cierre anterior, integridad de fuentes y registros, y respaldo documental falso. Se ejecutó la suite conjunta y el recorrido portable. Tras los últimos ajustes del autor del motor, se fijó el resultado final de 87 pruebas en la copia cuyos bytes se compararon con la raíz.

Los ajustes finales del motor rechazan preguntas con textos literalmente duplicados tras normalizar espacios y mayúsculas, rechazan `selected_branch_id` en un cierre inconcluso incluso si es null y conservan el tipo del método cuando un intento falla o se interrumpe. Un error aritmético no se etiqueta como revisión humana. La ejecución final registrada arriba ocurrió después de congelar estos cambios.

El diseño conserva todos los controles críticos anteriores: una comprobación nueva que pasa no borra un fallo crítico histórico. Los umbrales de comparación de datos no pueden ser ambos cero para presentar una igualdad como ventaja. Estas reglas forman parte de la entrega comprobada.

No se abre una tercera búsqueda de defectos por inercia. Una discrepancia material nueva exige registrarla y resolverla antes de atribuir aceptación a los bytes afectados.

## Qué se ha comprobado

- Cierre prematuro, fallo crítico, fallo de una rama seleccionada y ausencia de razones para descartar ramas.
- Una sugerencia material invalida el cierre anterior y exige revisión enlazada; presentación u otro objetivo no reabren el caso.
- Las revisiones no cambian objetivo, criterios, controles anteriores ni presupuesto; conservan fallos y consumo.
- Se cobran intentos fallidos e interrumpidos, sin repetición automática ni devolución de coste.
- Cuotas de checks, unidades, rondas y vida del caso; agotarlas no autoriza un cierre favorable.
- Plan, fuente y registro alterados; rutas que escapan de la raíz y enlaces simbólicos. El test de symlinks se ejecutó, sin omisión, en este entorno.
- Los cambios posteriores en una fuente original no cambian la copia sellada.
- Una revisión que declara pass no rescata una cita inexistente. Lo declarado conserva su etiqueta en el cierre e informe.
- El formato admite la distinción entre un resultado numérico, una coincidencia documental y un juicio aportado.

## Límites observados

- Los ejemplos son pequeños, artificiales y conocidos durante desarrollo. La revisión independiente es otra revisión técnica dentro de esta misma sesión de implementación, no una evaluación externa ni un ensayo ciego.
- Las ramas pueden cumplir la estructura y aun ser pobres o equivalentes. El programa no demuestra que la pregunta, hipótesis, método, cita, revisión o conclusión sean pertinentes.
- El ejecutor clasifica las sugerencias. Una etiqueta “material” o un vínculo a un control no prueba su relevancia sustantiva.
- Un sello local detecta discrepancias respecto al recibo conservado; no proporciona identidad, fecha externa, custodia inviolable o prospectividad científica.
- El tiempo se comprueba entre adaptadores y al cerrar; no interrumpe una llamada síncrona ya iniciada. Las unidades son costes declarados, no facturación ni medida del trabajo humano o de IA externo.
- No se evaluaron búsquedas de bibliografía, laboratorios, participantes, utilidad investigadora, ahorro real, novedad o eficacia universal. Esas pruebas siguen pendientes y no se sustituyen por contar tests.
