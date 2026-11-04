---
name: formato-timeline
description: Formato exacto de videos/<id>.timeline.json y recetas de edición (hook, quitar silencios, punch-in, resaltar palabras, música). Úsala antes de escribir o modificar cualquier timeline.
---

# Formato del timeline

Un timeline describe el video final. `./shorts render` lo convierte en mp4 con ffmpeg.

```json
{
  "clips": [
    {"fuente": "entrevista-01", "entrada": 12.40, "salida": 14.10,
     "zoom": 1.0, "encuadre_x": 0.5, "encuadre_y": 0.5, "nota": "hook"}
  ],
  "textos": [
    {"texto": "3 errores al lanzar", "inicio": 0.0, "fin": 2.4, "tipo": "titulo"},
    {"texto": "casi nadie lo *sabe*", "inicio": 0.0, "fin": 1.4, "tipo": "subtitulo"},
    {"texto": "poner logo nuevo aquí", "inicio": 15.8, "fin": 17.1, "tipo": "nota"}
  ],
  "musica": {"fuente": "musica/beat-120.wav", "volumen_db": -18, "entrada": 0},
  "subtitulos_auto": true
}
```

## Clips
| Campo | Obligatorio | Qué es |
|---|---|---|
| `fuente` | sí | nombre del archivo de material **sin extensión** (`entrevista-01.mp4` → `entrevista-01`) |
| `entrada`, `salida` | sí | segundos **del archivo fuente** |
| `zoom` | no | ≥ 1.0. 1.0 = recorte vertical justo; 1.2 = más cerca (punch-in) |
| `encuadre_x` | no | 0 = izquierda, 0.5 = centro, 1 = derecha. Para seguir a alguien que no está centrado en un plano horizontal |
| `encuadre_y` | no | igual, en vertical |
| `nota` | no | para humanos; no se renderiza |

Los clips se pegan en orden con cortes secos. La duración del video = suma de `salida - entrada`.

## Textos
Tiempos **del video final** (no de la fuente).
- `titulo`: arriba, con fondo. Úsalo para el hook.
- `subtitulo`: abajo. Si pones al menos uno manual, se desactivan los automáticos.
- `nota`: comentario para editores; no se renderiza.
- `*palabra*` entre asteriscos sale en el `color_resaltado` del estilo.
- Máximo ~24 caracteres por subtítulo (el QA avisa).

## Subtítulos automáticos
Si `subtitulos_auto` es true (o el estilo tiene `subtitulos.auto: true`) y no hay subtítulos manuales, el render los arma desde `transcript.json` de cada fuente, con los tiempos ya ajustados a los cortes. Requiere `faster-whisper`.

## Música
`fuente` relativa a `material/`. `entrada` = segundo de la canción donde empieza. Se repite si es más corta que el video y hace fade-out el último segundo. Si el estilo tiene `audio.ducking: true`, baja sola cuando hay voz.
`"musica": null` = usa la del estilo (`audio.musica`), y si ahí también es null, no hay música.

---

# Recetas

**Convertir tiempos fuente → final.** El clip *k* empieza en el video final en la suma de las duraciones de los clips 0..k-1. Úsalo para poner textos sobre un clip concreto.

**Quitar silencios.** En `silencios.json` hay `{inicio, fin}` en tiempos de la fuente. Parte el tramo en dos clips: uno que termina en `inicio + 0.1` y otro que empieza en `fin - 0.1` (deja 0.1 s de aire para que no suene cortado).

**Hook.** Busca en el transcript la frase más fuerte (dato, promesa, pregunta) y ponla como primer clip, aunque en el material esté al final. Agrega un `titulo` de 2–3 s.

**Punch-in.** Dos clips seguidos de la misma toma, el segundo con `zoom: 1.2`. Disimula un corte en la misma toma (jump cut).

**B-roll.** Intercala clips de otra fuente sobre la voz: corta la voz, pon el b-roll y retoma la voz donde la dejaste. Si el b-roll no tiene audio y no hay música, el QA marcará silencio; pon música o planos de b-roll más cortos que `checklist.silencio_max`.

**Cortes al beat.** Con `beats.json` de la música: cada corte (suma acumulada de duraciones) debería caer a menos de `ritmo.tolerancia_beat` de un beat, restando `musica.entrada`.

**Quitar una parte que pidió el cliente.** Busca la frase en el transcript, ubica qué clip(s) la contienen y recórtalos o elimínalos. No toques el resto.

---

# Errores típicos (los atrapa `./shorts validar` y el hook)
- `fuente` con extensión o mal escrita
- `salida` más allá del final del archivo
- `zoom` < 1 (deja bordes negros)
- textos con `fin <= inicio`
