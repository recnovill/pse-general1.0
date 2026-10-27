# Migración desde 1.0

2.0 cambia deliberadamente el contrato de cierre. Los planes nuevos requieren `"version": 2`. No acepta `requested_status`, un texto libre `conclusion` ni `CLOSED_SUPPORTED` como cierre nuevo.

## Expedientes existentes

Conserva intactos los casos 1.0, sus datos, recibos y runtime. Verifícalos con esa versión. No edites un plan sellado ni recomputes su cadena para presentarlo como 2.0. El rechazo de versión por el nuevo motor no implica que los datos históricos sean falsos.

Para un trabajo nuevo, crea otra carpeta y adapta una copia del plan fuente. Si reutilizas datos de evaluación ya vistos, declara que ya eran conocidos; no los presentes como evaluación nueva y reservada.

## Decisiones nuevas

- Observaciones: `{"mode":"results_only"}`.
- Sin resolución: `{"mode":"unresolved","reason":"...","limitations":["..."]}`.
- Interpretación: primero `propose`, después `review-packet` y `review`, finalmente `{"mode":"reviewed","proposal_id":"proposal_1"}`.

Una revisión manual incluida como adaptador no sustituye la revisión de la propuesta exacta. El presupuesto debe reservar unidades para propuestas y revisiones, además de controles.

Los consumidores de JSON deben reconocer los estados nuevos y no tratar `CLOSED_RESULTS` como «todas las pruebas pasan». Un estado cerrado puede conservar fallos. Tampoco deben traducir `CLOSED_REVIEWED_DECLARED` como verdad certificada.

Consulta [el contrato del motor](README_ENGINE.md), [el contrato de cierre](CONTRATO_CIERRE.md) y los [ejemplos](../examples/LEEME.md).
