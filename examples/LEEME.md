# Seis ejemplos de desarrollo — 2.0

Desde la raíz, con Python 3.11 o superior:

```powershell
python -B scripts/run_examples.py --out runs/demo_001
```

La salida debe ser una carpeta nueva. El runner ejecuta, cierra y verifica cada caso, escribe su `INFORME.md` y un resumen JSON.

| Carpeta | Qué enseña | Cierre esperado |
|---|---|---|
| calculo | Precedencia exacta, contraejemplo y abstención de intervalo. | CLOSED_RESULTS |
| datos | Comparación MAE en cuatro filas conocidas. | CLOSED_RESULTS |
| datos_sin_mejora | Empeoramiento conservado sin ajustar el criterio. | CLOSED_UNRESOLVED |
| documentos | Cita encontrada y revisión documental declarada. | CLOSED_RESULTS |
| techo | Mínimo absoluto 0.5 frente a MAE de referencia 0.25: criterio inalcanzable. | CLOSED_RESULTS, con comparación inconclusa |
| revision_declarada | Propuesta, paquete de revisión, revisión vinculada y cierre. | CLOSED_REVIEWED_DECLARED |

Todos son pequeños, sintéticos y conocidos durante desarrollo. No son una prueba reservada de eficacia.

El último ejemplo usa autor, revisor y juicio ficticios. El runner completa los identificadores y hashes de su plantilla únicamente para mostrar el contrato. **No copies esa aprobación a un caso real.** Un revisor debe leer la propuesta exacta y elaborar su propio juicio.

En documentos, un adaptador `manual_review` registra una revisión de una fuente. Eso no aprueba ninguna propuesta final: el cierre de ese ejemplo conserva solo resultados.
