# Editor de shorts

Sistema que edita videos cortos verticales (TikTok, Reels, Shorts) a partir de material crudo, un brief y, opcionalmente, un video de referencia. Opus decide la edición; ffmpeg renderiza; un modelo barato de video hace de "ojos" cuando hace falta.

## Mapa del repo

| Ruta | Qué es | Quién escribe |
|---|---|---|
| `videos/<id>.yaml` | **Manifiesto**: la ficha del video (cliente, estado, brief, ajustes, material, historial) | solo `./shorts` |
| `videos/<id>.timeline.json` | **Timeline**: la edición (clips, textos, música) | agente `editor` |
| `estilos/<preset>/style.yaml` | Presets de estilo | humanos o `./shorts guardar-estilo` |
| `estilos/_base/` | Estilo base y checklist de calidad | humanos |
| `salidas/` | Renders aprobados | solo `./shorts aprobar` |
| `.cache/media/<hash>/` | Análisis de cada archivo (transcript, escenas, silencios, beats, hoja de contactos) | `./shorts analizar`, `style-analyst` |
| `.cache/jobs/<id>/` | Estilo resuelto, renders de prueba, reportes de QA | `./shorts` |
| `motor/` | Código Python del CLI | desarrolladores |
| `prompts/` | Prompts del modelo de visión (`./shorts ojos`) | desarrolladores |
| `material/` | Crudos. **No está en git**; en producción es un disco o Drive montado (`config.yaml`) | humanos |

`.cache/` es regenerable: se puede borrar entero sin perder nada.

## Reglas (obligatorias)

1. **El manifiesto solo se cambia con `./shorts`** (`nuevo`, `fijar`, `feedback`, `aprobar`, `entregado`). Nunca con Edit/Write. Está bloqueado en `.claude/settings.json`.
2. **Los agentes solo escriben** en `videos/<id>.timeline.json` y dentro de `.cache/`.
3. **Nunca borres material** ni archivos de `salidas/`.
4. **Cada feedback abre versión nueva** (`./shorts feedback`) antes de tocar el timeline. El historial del manifiesto es la memoria del video: no deshagas cambios que pidió una entrada anterior.
5. **Opus no mira videos completos.** Usa el análisis cacheado, las hojas de contactos (`contacto.jpg`) y, si hace falta, `./shorts ojos` (Gemini Flash-Lite).
6. Se guardan solo las últimas 2 versiones de renders de prueba (`renders_a_conservar`).

## Estilo en capas

`_base` → preset (`estilo`) → referencia (`estilo_ref.yaml`, si hay) → `ajustes` del manifiesto. Gana la última. El resultado queda en `.cache/jobs/<id>/style.json` y lo regenera cada render. Si `estilo` es `null`, el `director` elige preset.

## Flujo

```
/nuevo-video ─► ./shorts nuevo ─► analizar ─► director ─► (style-analyst) ─► editor ─► render --preview ─► qa-reviewer
/iterar      ─► ./shorts feedback ─► director y/o editor ─► render --preview ─► qa-reviewer
/aprobar     ─► render (final) ─► qa ─► ./shorts aprobar ─► salidas/
```

## Subagentes (`.claude/agents/`)

- `director`: elige preset y traduce el brief a `ajustes`.
- `style-analyst`: extrae estilo de la referencia (solo si hay).
- `editor`: escribe/parchea el timeline. Usa la skill `formato-timeline`.
- `qa-reviewer`: revisa el render y dice APROBABLE o CORREGIR.

## Convenciones

- **id**: `AAAA-MM-DD_cliente_titulo` (lo genera `./shorts nuevo`). Los comandos aceptan un pedazo único del id: `acme_lanz`.
- **Material**: rutas relativas a `material_raiz`. En el timeline cada archivo se nombra sin extensión.
- **Estados**: `borrador` → `en-revision` → `aprobado` → `entregado`.
- Usa `./shorts --json <comando>` cuando necesites leer la salida.

## CLI

`./shorts --help` lista todo. Los más usados:
`nuevo`, `analizar`, `estilo`, `fijar`, `feedback`, `validar`, `render [--preview]`, `qa`, `aprobar`, `buscar`, `ver`, `guardar-estilo`, `ojos`, `limpiar`.
