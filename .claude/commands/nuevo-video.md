---
description: Crea un video nuevo y saca el primer corte (análisis, estilo, edición, render y QA)
argument-hint: "[cliente] [título] [material...] [brief]"
---

Crea un video nuevo con lo que dio el editor: $ARGUMENTS

## 1. Datos mínimos
Necesitas: **cliente**, **título corto**, **material** (rutas relativas a `material/`) y, opcional, **brief**, **preset** y **referencia**.
Si falta cliente, título o material, pregúntalo en una sola pregunta. Para ayudar a elegir el material, lista lo que hay con `ls material/<cliente>/`.

## 2. Crear el manifiesto
```bash
./shorts nuevo --cliente "<cliente>" --titulo "<título>" --material <ruta1> <ruta2> \
  [--estilo <preset>] [--referencia <ruta>] --brief "<brief>"
```
Usa el id que devuelve en todos los pasos siguientes.

## 3. Analizar
```bash
./shorts --json analizar <id>
```

## 4. Estilo
- Usa el subagente **director** (elige preset si no hay, y traduce el brief a ajustes).
- Si hay referencia, usa después el subagente **style-analyst**.

## 5. Primer corte
Usa el subagente **editor** para escribir el timeline.

## 6. Render y revisión
```bash
./shorts render <id> --preview
```
Después usa el subagente **qa-reviewer**. Si dice CORREGIR, pásale los puntos al editor o al director según corresponda, vuelve a renderizar y revisa. **Máximo 2 vueltas**; si sigue fallando, para y explícale al usuario qué falta.

## 7. Respuesta al usuario
Corta: id del video, preset elegido (y por qué, si lo eligió el director), ruta del render de prueba, resultado del QA y cómo seguir:
`/iterar <id> "feedback"` o `/aprobar <id>`.
