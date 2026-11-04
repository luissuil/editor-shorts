# editor-shorts

Repo de prueba de un editor automático de shorts verticales con Claude Code (Opus 5.5) + ffmpeg.

El editor humano ve **un archivo por video** en `videos/` y **los entregables** en `salidas/`. Todo lo demás (análisis, renders de prueba, QA) vive en `.cache/`, que está oculto y se puede borrar cuando quieras.

---

## 1. Instalación (una vez)

```bash
# Requisitos: Python 3.10+, ffmpeg 6+ con libass, Claude Code
pip install pyyaml

# Opcionales (funciona sin ellos, con menos funciones):
pip install faster-whisper      # transcripción → subtítulos automáticos
pip install librosa             # beats → cortes al beat
pip install "scenedetect[opencv]"  # detección de cortes más precisa
pip install google-genai        # "ojos": Gemini analiza video + audio
export GEMINI_API_KEY=...       # solo si instalaste google-genai
```

En `config.yaml` pon `material_raiz` apuntando a donde están los crudos (disco compartido, Drive montado…). Para la prueba deja `./material`.

## 2. Probarlo en 2 minutos (sin Claude, solo el CLI)

```bash
./shorts demo                       # genera material sintético en material/
./shorts buscar                     # ya hay un video de ejemplo
./shorts analizar acme_lanz         # analiza crudos + referencia (queda cacheado)
./shorts render acme_lanz --preview # render rápido a media resolución
./shorts qa acme_lanz               # QA automático
```

El render queda en `.cache/jobs/2026-11-04_acme_lanzamiento/renders/` junto con su hoja de contactos (`-contacto.jpg`).

> El ejemplo viene en estado `aprobado`. Para volver a iterarlo: `./shorts feedback acme_lanz "lo que sea"`.

## 3. Uso diario (editores, dentro de Claude Code)

Abre `claude` en la carpeta del repo y usa los comandos:

| Comando | Para qué |
|---|---|
| `/nuevo-video acme "Lanzamiento" acme/crudos/entrevista-01.mp4 brief: cortes rápidos, subtítulos amarillos` | Crea el video y saca el primer corte |
| `/iterar acme_lanz "quita la parte del precio y sube los subtítulos"` | Aplica feedback → nueva versión → render → QA |
| `/ver acme_lanz` | Estado, historial y cómo se ve el último render |
| `/buscar acme` · `/buscar --estado en-revision` | Encontrar videos |
| `/aprobar acme_lanz` | Render final + QA + copia a `salidas/` |
| `/guardar-estilo acme_lanz acme-rapido` | Convierte el estilo de un video que gustó en preset |

No hace falta escribir el id completo: basta un pedazo único (`acme_lanz`).

### Qué pasa por dentro en `/nuevo-video`

1. `./shorts nuevo` crea `videos/<id>.yaml` y un timeline vacío.
2. `./shorts analizar` transcribe, detecta escenas, silencios y beats (una sola vez por archivo, por hash).
3. **director** elige preset (si no lo diste) y traduce el brief a `ajustes`.
4. **style-analyst** (solo si hay referencia) mide su ritmo y estima colores/posiciones.
5. **editor** (Opus) escribe el timeline. Un hook valida el JSON cada vez que lo guarda.
6. `./shorts render --preview` y **qa-reviewer** revisa. Hasta 2 vueltas de corrección.

## 4. Los dos archivos de cada video

**`videos/<id>.yaml`: la ficha.** Se lee a mano, pero se cambia solo con comandos.

```yaml
id: 2026-11-04_acme_lanzamiento
cliente: acme
estado: aprobado            # borrador | en-revision | aprobado | entregado
estilo: talking-head        # null = lo elige el director
referencia: referencias/ref-acme.mp4
brief: Cortes rápidos, subtítulos amarillos, sin música.
ajustes:                    # lo que salió del brief, gana sobre el preset
  subtitulos: {color: '#FFD400'}
material:
- acme/crudos/entrevista-01.mp4
- acme/crudos/producto-02.mp4
version: 2
historial:
- {v: 1, nota: primer corte, ...}
- {v: 2, nota: agregar música de fondo baja..., ...}
```

**`videos/<id>.timeline.json`: la edición.** Clips (tiempos de la fuente), textos (tiempos del video final) y música. El formato completo está en `.claude/skills/formato-timeline/SKILL.md`.

Como los dos van en git, `git log -p videos/<id>.timeline.json` muestra exactamente qué cambió entre versiones.

## 5. Estilos

```
_base  →  preset  →  referencia (si hay)  →  ajustes del brief
```

Cada capa pisa a la anterior. Presets incluidos: `talking-head`, `tutorial`, `podcast`, `producto`, y `acme-rapido` (creado con `guardar-estilo` desde el video de ejemplo). Para crear uno a mano, copia una carpeta de `estilos/` y cambia solo lo que necesites: lo demás se hereda de `_base`.

`./shorts estilo <id>` muestra el estilo final y qué capas se usaron.

## 6. Estructura

```
editor-shorts/
├── AGENTS.md / CLAUDE.md     reglas para los agentes
├── config.yaml               rutas y opciones
├── shorts                    atajo del CLI (./shorts --help)
├── .claude/
│   ├── settings.json         permisos (manifiestos y estilos bloqueados) + hook de validación
│   ├── agents/               director, style-analyst, editor, qa-reviewer
│   ├── commands/             /nuevo-video /iterar /ver /buscar /aprobar /guardar-estilo
│   └── skills/formato-timeline/
├── estilos/                  presets en YAML + _base/checklist.yaml
├── videos/                   <id>.yaml + <id>.timeline.json   ← lo único por video
├── salidas/                  mp4 aprobados
├── prompts/                  prompts del modelo de visión
├── motor/                    código (análisis, estilo, render, QA, CLI)
├── tests/                    python3 -m pytest -q
├── material/                 crudos (fuera de git)
└── .cache/                   regenerable (fuera de git)
```

## 7. Mantenimiento

- `./shorts limpiar` borra el caché de los videos `entregado`. `./shorts limpiar --todo` borra todo `.cache/` (se regenera solo).
- Renders de prueba: se guardan las últimas 2 versiones por video.
- Varios editores a la vez: las escrituras son atómicas y el análisis/render usa candados por archivo, así que dos personas no pisan el mismo job.
- Las zonas seguras de cada app en `estilos/_base/checklist.yaml` son aproximadas: ajústalas con capturas reales.
- Para cambiar de modelo de visión, edita `ojos.modelo` en `config.yaml` (verifica el id exacto en la doc de Gemini).

## 8. Limitaciones del prototipo

- Solo cortes secos (sin transiciones animadas ni subtítulos palabra por palabra).
- Loudness en una pasada (`loudnorm`): queda dentro de ±1.5 LU; el QA lo mide.
- Sin `faster-whisper` no hay subtítulos automáticos: el editor los escribe a mano en el timeline.
- `ojos` solo implementa Gemini; para otro proveedor (OpenRouter, Nemotron local) hay que agregarlo en `motor/ojos.py`.
