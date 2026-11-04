---
description: Renderiza en calidad final, pasa QA y deja el video en salidas/
argument-hint: "<id o parte del id>"
---

Aprobar: $ARGUMENTS

1. Render final (resolución completa, no preview):
   ```bash
   ./shorts render <id>
   ```
2. QA:
   ```bash
   ./shorts qa <id>
   ```
   Si el resultado es `falla`, **no apruebes**: muestra qué falló y sugiere `/iterar`.
3. Aprobar:
   ```bash
   ./shorts aprobar <id>
   ```
   Copia el mp4 a `salidas/`, marca el video como `aprobado` y borra los renders de prueba.
4. Responde con la ruta del archivo final. Si el video gustó, sugiere `/guardar-estilo <id> <nombre>`.
