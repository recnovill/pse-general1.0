# Publicar esta copia posteriormente

Esta copia se preparó localmente. Repositorio elegido por el titular: [recnovill/pse-general1.0](https://github.com/recnovill/pse-general1.0), público. El programa incluido sigue siendo PSE General 2.0.0. Los recibos anteriores documentan la preparación previa, no el estado actual del remoto.

Revisa el [README](README.md), la [licencia PolyForm Noncommercial 1.0.0](LICENSE), el [QA](docs/QA_RESULT.md) y los [límites](docs/ALCANCE.md). Conserva [NOTICE](NOTICE) y el texto completo de la licencia. No añadas expedientes privados, `runs/`, `_build/`, entornos, credenciales o correspondencia.

Desde esta carpeta, cuando decidas publicar:

```powershell
git init -b main
git status --short
git add .
git diff --cached --stat
git commit -m "Publicar PSE General 2.0"
```

Si el repositorio ya está inicializado, omite `git init`. Configura tu identidad de Git si se solicita. La autenticación de GitHub es un paso separado; no guardes tokens ni contraseñas en los archivos.

Crea en GitHub un repositorio público vacío, sin generar README o licencia. Sustituye la URL por la que te facilite GitHub:

```powershell
git remote add origin URL_DEL_REPOSITORIO
git push -u origin main
```

Comprueba la página publicada y comparte su enlace. El destinatario podrá leer código, contrato y tests sin ejecutar nada. Esta guía no ejecuta esas operaciones.

Si cambias archivos, actualiza el manifiesto y repite las verificaciones afectadas antes de atribuirles el recibo de esta entrega.
