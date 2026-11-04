---
description: Guarda el estilo de un video que gustó como preset reutilizable
argument-hint: "<id> <nombre-del-preset>"
---

Guardar estilo: $ARGUMENTS

1. Si el usuario no dio nombre, propón uno corto en minúsculas con guiones (p. ej. `acme-rapido`).
2. Escribe una línea de **cuándo usarlo** (la lee el director para elegir presets): tipo de material y de cliente.
3. Guarda:
   ```bash
   ./shorts guardar-estilo <id> <nombre> --cuando "<cuándo usarlo>"
   ```
4. Responde con la ruta del preset y recuerda que se puede usar con `--estilo <nombre>` en `/nuevo-video`.
