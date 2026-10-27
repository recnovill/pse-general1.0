# PSE: primera lectura

Esta entrega contiene **PSE General 2.0**, un protocolo de trabajo y un programa Python para organizar alternativas, conservar evidencia y controlar revisiones y límites. El código se puede consultar, probar y adaptar conforme a PolyForm Noncommercial 1.0.0.

## Qué recibirás

- Código Python legible, documentación, tests y seis ejemplos.
- [PolyForm Noncommercial 1.0.0](LICENSE), con reconocimiento de autoría de Alberto en [NOTICE](NOTICE).
- Un registro claro de capacidades y límites. No requiere cuenta, claves de API ni paquetes adicionales para el motor y los ejemplos.

La persona o IA que usa PSE formula las preguntas y evalúa las interpretaciones. El programa comprueba contratos y ejecuta sus cinco adaptadores; **no incorpora un modelo de IA ni funciona como investigador autónomo**. Las revisiones semánticas permanecen identificadas como juicios declarados.

## Primera prueba

1. Lee [el README](README.md) y [las capacidades implementadas](docs/ADAPTADORES.md).
2. Con Python 3.11 o superior, desde la raíz de esta carpeta:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/run_examples.py --out runs/primera_prueba
```

El segundo comando necesita una carpeta de salida nueva. Los ejemplos son sintéticos: permiten inspeccionar el funcionamiento, no demuestran eficacia investigadora.

3. Para trabajar con un asistente, lee [USAR_PSE.txt](USAR_PSE.txt). El registro automático se realiza mediante los comandos documentados; pegar esas instrucciones no conecta por sí mismo el asistente al programa.

## Qué está demostrado

La base 2.0 tiene verificación técnica y ejemplos reproducibles. La [comprobación de esta copia](docs/VERIFICACION_ESTA_COPIA.json) identifica la ejecución de entrega. Los [resultados recientes](docs/RESULTADOS_RECIENTES.md) conservan tanto mejoras parciales como ausencia de ventaja demostrada.

No se ha establecido superioridad general frente a una IA competente con los mismos recursos. Tampoco existe certificación externa de seguridad o de validez científica. Los hashes sirven para comprobar coherencia de archivos locales, no para autenticar a sus autores.

## Alcance de este repositorio

El motor entregado es General 2.0. Los resúmenes de pilotos describen investigaciones asistidas coordinadas fuera de este motor; no deben interpretarse como ensayos ejecutados automáticamente por él. Incluimos sus resultados JSON para hacer visibles las cifras y límites, no los datasets ni todos sus materiales necesarios para reproducirlos.

Las ideas posteriores de diagnóstico siguen en evaluación y no forman parte de las capacidades implementadas de esta entrega. Los recibos en `docs/history/1.0` son históricos; no son la versión que se ejecuta aquí.

La documentación permite revisar el contenido antes de ejecutar nada. El paquete solo contiene texto; esto facilita la inspección, pero no garantiza por sí solo que un código sea seguro.
