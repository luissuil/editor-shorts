"""Resolver el estilo de un video en capas.

  1. estilos/_base/style.yaml           siempre
  2. estilos/<preset>/style.yaml        el que eligió el editor o el director
  3. <cache de la referencia>/estilo_ref.yaml   solo si hay referencia
  4. manifiesto.ajustes                 lo que pidió el usuario en el brief (gana siempre)

El resultado va a .cache/jobs/<id>/style.json. Es derivado: se regenera en cada render.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from . import cache
from . import config as cfg
from . import manifiesto
from .util import ErrorShorts, escribir_json, escribir_yaml, fusionar, leer_json, leer_yaml


def ruta_resuelto(video_id: str) -> Path:
    return cfg.cache_job(video_id) / "style.json"


def ruta_estilo_ref(m: dict) -> Path | None:
    if not m.get("referencia"):
        return None
    return cache.dir_media(cfg.ruta_material(m["referencia"])) / "estilo_ref.yaml"


def resolver(video_id: str) -> dict:
    m = manifiesto.cargar(video_id)
    capas = ["_base"]
    estilo = leer_yaml(cfg.ESTILOS / "_base" / "style.yaml")
    if m.get("estilo"):
        p = cfg.ESTILOS / m["estilo"] / "style.yaml"
        if not p.exists():
            raise ErrorShorts(f"El preset '{m['estilo']}' no existe. Presets: {manifiesto.presets()}")
        estilo = fusionar(estilo, leer_yaml(p))
        capas.append(m["estilo"])
    ref = ruta_estilo_ref(m)
    if ref and ref.exists():
        estilo = fusionar(estilo, leer_yaml(ref))
        capas.append(f"referencia:{Path(m['referencia']).name}")
    if m.get("ajustes"):
        estilo = fusionar(estilo, m["ajustes"])
        capas.append("ajustes")
    estilo["_capas"] = capas
    escribir_json(ruta_resuelto(video_id), estilo)
    return estilo


def cargar_resuelto(video_id: str) -> dict:
    p = ruta_resuelto(video_id)
    return leer_json(p) if p.exists() else resolver(video_id)


def medir_referencia(video_id: str) -> dict:
    """Saca de la referencia SOLO lo que se puede medir con números.
    Lo subjetivo (colores, tipo de subtítulos) lo agrega el style-analyst
    después de mirar la hoja de contactos o de preguntarle al modelo de visión."""
    m = manifiesto.cargar(video_id)
    if not m.get("referencia"):
        raise ErrorShorts("Este video no tiene referencia.")
    ruta = cfg.ruta_material(m["referencia"])
    cache.analizar(ruta)
    d = cache.dir_media(ruta)
    info = leer_json(d / "info.json")
    cortes = leer_json(d / "escenas.json")
    limites = [0.0, *cortes, info["duracion"]]
    planos = [round(b - a, 3) for a, b in zip(limites, limites[1:]) if b - a > 0.05]

    parcial: dict = {"_medido_de": ruta.name}
    if len(planos) >= 3:
        orden = sorted(planos)
        parcial["ritmo"] = {
            "plano_objetivo": round(statistics.median(planos), 2),
            # margen alrededor de p10/p90: la referencia marca el ritmo, no una regla exacta
            "plano_min": round(orden[max(0, len(orden) // 10)] * 0.7, 2),
            "plano_max": round(orden[min(len(orden) - 1, len(orden) * 9 // 10)] * 1.5, 2),
        }
    parcial["duracion"] = {"min": round(info["duracion"] * 0.8), "max": round(info["duracion"] * 1.2)}

    beats_p = d / "beats.json"
    if beats_p.exists() and cortes:
        beats = leer_json(beats_p)["beats"]
        en_beat = sum(1 for c in cortes if beats and min(abs(c - b) for b in beats) < 0.08)
        parcial.setdefault("ritmo", {})["cortes_al_beat"] = en_beat / len(cortes) > 0.6

    escribir_yaml(d / "estilo_ref.yaml", parcial)
    return {"estilo_ref": str(d / "estilo_ref.yaml"), "planos": len(planos), **parcial}


def guardar_preset(video_id: str, nombre: str, forzar: bool = False,
                   cuando: str | None = None) -> Path:
    destino = cfg.ESTILOS / nombre / "style.yaml"
    if destino.exists() and not forzar:
        raise ErrorShorts(f"Ya existe el preset '{nombre}'. Usa --forzar para sobreescribirlo.")
    estilo = resolver(video_id)
    capas = estilo.pop("_capas")
    estilo.pop("_medido_de", None)
    for k in ("nombre", "descripcion", "cuando_usarlo"):
        estilo.pop(k, None)
    cabecera = {"nombre": nombre,
                "descripcion": f"Creado desde {video_id} (capas: {', '.join(capas)})"}
    if cuando:
        cabecera["cuando_usarlo"] = cuando
    escribir_yaml(destino, {**cabecera, **estilo})
    return destino
