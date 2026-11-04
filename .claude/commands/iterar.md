---
description: Aplica feedback a un video, renderiza la versión nueva y la revisa
argument-hint: "<id o parte del id> \"<feedback>\""
---

Feedback para un video: $ARGUMENTS

El primer argumento es el id (sirve un pedazo único, p. ej. `acme_lanz`). El resto es el feedback.

## 1. Registrar el feedback
```bash
./shorts feedback <id> "<feedback tal cual lo dijo el usuario>"
```
Esto abre una versión nueva y deja el feedback en el historial del manifiesto.

## 2. Aplicarlo
Separa el feedback en dos tipos y llama a quien corresponda (pueden ser los dos):
- **Estilo** (colores, tamaños, mayúsculas, música, ritmo general) → subagente **director**.
- **Contenido** (quitar/agregar partes, orden, textos, hook, duración de una parte) → subagente **editor**.

## 3. Render y revisión
```bash
./shorts render <id> --preview
```
Luego el subagente **qa-reviewer**. Si dice CORREGIR, una vuelta más como máximo.

## 4. Respuesta
Qué cambió (en timecodes), ruta del render y resultado del QA. Si el usuario queda conforme: `/aprobar <id>`.
