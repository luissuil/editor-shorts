"""El timeline (videos/<id>.timeline.json) es la edición en sí. Lo escribe el agente editor.

Formato (ver .claude/skills/formato-timeline/SKILL.md):
{
  "clips":  [{"fuente": "entrevista-01", "entrada": 3.2, "salida": 6.0,
              "zoom": 1.0, "encuadre_x": 0.5, "nota": "hook"}],
  "textos": [{"texto": "...", "inicio": 0.0, "fin": 2.0, "tipo": "titulo"}],
  "musica": {"fuente": "musica/beat.wav", "volumen_db": -20, "entrada": 0} | null,
  "subtitulos_auto": true
}
Los tiempos de "clips" son del archivo fuente; los de "textos", del video final.
"""
from __future__ import annotations

from pathlib import Path

from . import cache
from . import config as cfg
from . import manifiesto
from .util import ErrorShorts, ffprobe, leer_json

TIPOS_TEXTO = {"titulo", "subtitulo", "nota"}


def cargar(video_id: str) -> dict:
    p = manifiesto.ruta_timeline(video_id)
    if not p.exists():
        raise ErrorShorts(f"No hay timeline para {video_id}")
    return leer_json(p)


def duracion_total(tl: dict) -> float:
    return round(sum(c["salida"] - c["entrada"] for c in tl.get("clips", [])), 3)


def _duracion_fuente(ruta: Path) -> float:
    p = cache.dir_media(ruta) / "info.json"
    return leer_json(p)["duracion"] if p.exists() else ffprobe(ruta)["duracion"]


def validar(video_id: str, tl: dict | None = None) -> tuple[list[str], list[str]]:
    """Devuelve (errores, advertencias). Con errores no se renderiza."""
    m = manifiesto.cargar(video_id)
    tl = tl if tl is not None else cargar(video_id)
    errores: list[str] = []
    avisos: list[str] = []
    fuentes = manifiesto.alias_material(m)
    clips = tl.get("clips", [])
    if not clips:
        errores.append("El timeline no tiene clips.")

    for n, c in enumerate(clips):
        donde = f"clips[{n}]"
        if c.get("fuente") not in fuentes:
            errores.append(f"{donde}: fuente '{c.get('fuente')}' no está en el material. "
                           f"Opciones: {sorted(fuentes)}")
            continue
        ini, fin = c.get("entrada"), c.get("salida")
        if not isinstance(ini, (int, float)) or not isinstance(fin, (int, float)) or fin <= ini:
            errores.append(f"{donde}: entrada/salida inválidas ({ini} → {fin})")
            continue
        if ini < 0:
            errores.append(f"{donde}: entrada negativa")
        dur = _duracion_fuente(fuentes[c["fuente"]])
        if fin > dur + 0.05:
            errores.append(f"{donde}: salida {fin}s pasa del final de '{c['fuente']}' ({dur:.2f}s)")
        if c.get("zoom", 1.0) < 1.0:
            errores.append(f"{donde}: zoom < 1 dejaría bordes negros")
        if not 0 <= c.get("encuadre_x", 0.5) <= 1:
            errores.append(f"{donde}: encuadre_x va de 0 (izquierda) a 1 (derecha)")

    total = duracion_total(tl)
    for n, t in enumerate(tl.get("textos", [])):
        donde = f"textos[{n}]"
        if not t.get("texto", "").strip():
            errores.append(f"{donde}: texto vacío")
        if t.get("tipo", "subtitulo") not in TIPOS_TEXTO:
            errores.append(f"{donde}: tipo debe ser uno de {sorted(TIPOS_TEXTO)}")
        if t.get("fin", 0) <= t.get("inicio", 0):
            errores.append(f"{donde}: fin debe ser mayor que inicio")
        elif t["inicio"] >= total:
            avisos.append(f"{donde}: empieza después de que termina el video ({total}s)")

    mus = tl.get("musica")
    if mus and not cfg.ruta_material(mus["fuente"]).exists():
        errores.append(f"musica: no existe {mus['fuente']}")
    return errores, avisos


def subtitulos_auto(video_id: str, tl: dict, palabras_por_linea: int = 3) -> list[dict]:
    """Convierte el transcript de cada clip en subtítulos con tiempos del video final."""
    m = manifiesto.cargar(video_id)
    fuentes = manifiesto.alias_material(m)
    palabras_finales: list[dict] = []
    t_salida = 0.0
    for c in tl.get("clips", []):
        p = cache.dir_media(fuentes[c["fuente"]]) / "transcript.json"
        if p.exists():
            for w in leer_json(p)["palabras"]:
                centro = (w["i"] + w["f"]) / 2
                if c["entrada"] <= centro < c["salida"]:
                    desfase = t_salida - c["entrada"]
                    palabras_finales.append({
                        "p": w["p"],
                        "i": max(t_salida, w["i"] + desfase),
                        "f": min(t_salida + c["salida"] - c["entrada"], w["f"] + desfase),
                    })
        t_salida += c["salida"] - c["entrada"]

    textos: list[dict] = []
    grupo: list[dict] = []
    for w in palabras_finales:
        if grupo and (len(grupo) >= palabras_por_linea or w["i"] - grupo[-1]["f"] > 0.5):
            textos.append(_cerrar(grupo))
            grupo = []
        grupo.append(w)
    if grupo:
        textos.append(_cerrar(grupo))
    return textos


def _cerrar(grupo: list[dict]) -> dict:
    return {"texto": " ".join(w["p"] for w in grupo), "inicio": round(grupo[0]["i"], 3),
            "fin": round(grupo[-1]["f"], 3), "tipo": "subtitulo"}
