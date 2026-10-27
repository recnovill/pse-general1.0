# PSE General 2.0

Para esta entrega, comienza por [la primera lectura](00_EMPEZAR_AQUI.md). Incluye instrucciones de prueba y los [resultados y límites recientes](docs/RESULTADOS_RECIENTES.md).

**Explorar alternativas, comprobarlas y cerrar dentro de límites explícitos.**

PSE combina un protocolo de investigación asistida y un programa Python local. Una persona o IA plantea preguntas, desarrolla ramas y revisa interpretaciones. El programa ejecuta cinco métodos concretos, conserva evidencia y aplica controles de presupuesto, integridad y cierre.

La versión 2.0 corrige un fallo demostrado en 1.0: varios controles correctos podían acompañar una conclusión arbitraria y producir un cierre llamado respaldado. Ahora el resultado automático se genera a partir de datos tipados. Las interpretaciones pasan por una propuesta y una revisión vinculadas a su texto y evidencia exactos; conservan la etiqueta **juicio revisado declarado**.

## Empieza aquí

- [Guía de capacidades y uso](docs/GUIA.md).
- [Protocolo](PROTOCOLO.md) y [texto para usar con un asistente](USAR_PSE.txt).
- [Seis ejemplos de desarrollo](examples/LEEME.md).
- [Contrato del motor](docs/README_ENGINE.md), [contrato de cierre](docs/CONTRATO_CIERRE.md) y [adaptadores](docs/ADAPTADORES.md).
- [Límites](docs/ALCANCE.md), [revisión del código](docs/REVISION_DEL_CODIGO.md) y [migración desde 1.0](docs/MIGRACION_2_0.md).

## Qué controla

- Preguntas y tres funciones: referencia, alternativa y rama crítica.
- Aritmética exacta, intervalos, comparación de CSV, citas locales y revisiones documentadas.
- Planes, fuentes, intentos y resultados; conserva fallos y abstenciones.
- Presupuesto compartido de controles, unidades, tiempo y rondas.
- Propuestas con afirmaciones, alcance, supuestos, límites y referencias a controles ejecutados.
- Una revisión por propuesta, sobre el mismo texto y evidencia; máximo tres propuestas y tres revisiones por caso.
- Bloqueo de interpretación revisada si faltan controles o falla un control requerido.
- Detección del mínimo de mejora absoluta que supera el máximo posible del comparador observado.

## Tres cierres distintos

| Estado | Significado |
|---|---|
| `CLOSED_RESULTS` | Comprobaciones completadas. El informe muestra resultados concretos, incluidos fallos o incertidumbre. No elige una interpretación. |
| `CLOSED_REVIEWED_DECLARED` | Propuesta revisada bajo el contrato. El juicio y las identidades son declarados, sin autenticación ni garantía semántica. |
| `CLOSED_UNRESOLVED` | Se conserva el motivo de falta de resolución o de recursos. |

El programa no contiene una IA ni produce por sí solo preguntas excelentes, revisores independientes o descubrimientos. La revisión de pertinencia continúa siendo trabajo del investigador o asistente.

## Ejecutar localmente

Python 3.11 o superior. Biblioteca estándar; sin dependencias adicionales, cuentas o claves de API. Desde esta carpeta:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/run_examples.py --out runs/demo_001
python -B -m pse --help
```

El directorio de salida debe ser nuevo. El ejemplo de revisión usa personajes y un juicio sintéticos para mostrar el contrato; no equivale a una revisión externa.

## Verificación y límites

Los resultados de esta edición están en [QA](docs/QA_RESULT.md) y en el [recibo de entrega](docs/VALIDACION_ENTREGA.json). Los recibos de 1.0 se conservan en `docs/history/1.0/` y no validan esta edición. El manifiesto SHA-256 identifica los archivos de la entrega.

Las pruebas comprueban funcionamiento técnico y ataques específicos al contrato. No demuestran superioridad científica frente a una buena revisión con la misma IA, datos, herramientas y presupuesto, ni certifican seguridad absoluta.

## Licencia y publicación

[PolyForm Noncommercial 1.0.0](LICENSE), con el aviso de autoría en [NOTICE](NOTICE). Código disponible para consultar, usar, modificar y compartir conforme a los fines permitidos por esa licencia. Los usos que no estén cubiertos requieren un permiso separado del titular. [Procedencia y estado de los recibos anteriores](docs/PROCEDENCIA_Y_USO.md).

Esta distribución contiene código y documentación legibles. El repositorio previsto para compartirla es [recnovill/pse-general1.0](https://github.com/recnovill/pse-general1.0); el nombre elegido para el repositorio no cambia la versión del programa, que es **2.0.0**. Los recibos de preparación describen el estado local anterior a la publicación. [Guía de publicación](PUBLICAR_EN_GITHUB.md).
