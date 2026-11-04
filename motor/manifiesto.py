"""El manifiesto (videos/<id>.yaml) es la ficha del video. Solo este módulo lo escribe."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from . import config as cfg
from .util import ErrorShorts, escribir_json, escribir_yaml, leer_yaml, slug

ESTADOS = ["borrador", "en-revision", "aprobado", "entregado"]


def ruta(video_id: str) -> Path:
    return cfg.VIDEOS / f"{video_id}.yaml"


def ruta_timeline(video_id: str) -> Path:
    return cfg.VIDEOS / f"{video_id}.timeline.json"


def cargar(video_id: str) -> dict:
    p = ruta(video_id)
    if not p.exists():
        parecidos = [m["id"] for m in listar() if video_id.lower() in m["id"]]
        pista = f" ¿Quisiste decir: {', '.join(parecidos[:5])}?" if parecidos else ""
        raise ErrorShorts(f"No existe el video '{video_id}'.{pista}")
    return leer_yaml(p)


def guardar(m: dict) -> None:
    if m.get("estado") not in ESTADOS:
        raise ErrorShorts(f"Estado inválido: {m.get('estado')}. Usa uno de {ESTADOS}")
    escribir_yaml(ruta(m["id"]), m)


def listar() -> list[dict]:
    return [leer_yaml(p) for p in sorted(cfg.VIDEOS.glob("*.yaml"))]


def alias_material(m: dict) -> dict[str, Path]:
    """Cada archivo de material se referencia en el timeline por su nombre sin extensión."""
    res: dict[str, Path] = {}
    for rel in m.get("material", []):
        alias = Path(rel).stem
        if alias in res:
            raise ErrorShorts(f"Dos archivos de material se llaman '{alias}'. Renombra uno.")
        res[alias] = cfg.ruta_material(rel)
    return res


def crear(cliente: str, titulo: str, material: list[str], estilo: str | None,
          brief: str, referencia: str | None, fecha: str | None = None) -> dict:
    fecha = fecha or dt.date.today().isoformat()
    video_id = f"{fecha}_{slug(cliente)}_{slug(titulo)}"
    if ruta(video_id).exists():
        raise ErrorShorts(f"Ya existe {video_id}. Usa otro título o /iterar sobre ese.")
    faltan = [r for r in material if not cfg.ruta_material(r).exists()]
    if faltan:
        raise ErrorShorts(f"No encuentro este material (relativo a {cfg.material_raiz()}): {faltan}")
    if estilo and not (cfg.ESTILOS / estilo / "style.yaml").exists():
        raise ErrorShorts(f"No existe el preset '{estilo}'. Presets: {presets()}")
    m = {
        "id": video_id,
        "cliente": slug(cliente),
        "titulo": titulo,
        "estado": "borrador",
        "estilo": estilo,          # null = el director elige
        "referencia": referencia,  # opcional
        "brief": brief,
        "ajustes": {},             # overrides estructurados que salen del brief
        "material": material,
        "version": 0,              # 0 = todavía no hay timeline
        "historial": [],
        "creado": fecha,
    }
    guardar(m)
    # timeline vacío para que el editor tenga dónde escribir
    escribir_json(ruta_timeline(video_id), {"clips": [], "textos": [], "musica": None})
    return m


def presets() -> list[str]:
    return sorted(p.name for p in cfg.ESTILOS.iterdir()
                  if (p / "style.yaml").exists() and not p.name.startswith("_"))


def agregar_feedback(video_id: str, nota: str, autor: str = "editor") -> dict:
    """Abre una versión nueva: sube el número y deja anotado por qué."""
    m = cargar(video_id)
    m["version"] += 1
    m["historial"].append({
        "v": m["version"],
        "nota": nota,
        "autor": autor,
        "fecha": dt.datetime.now().isoformat(timespec="minutes"),
    })
    if m["estado"] in ("aprobado", "entregado"):
        m["estado"] = "en-revision"
    guardar(m)
    return m


def fijar(video_id: str, **campos) -> dict:
    """Cambia campos puntuales (estilo elegido por el director, ajustes, estado)."""
    m = cargar(video_id)
    for k, v in campos.items():
        if k not in ("estilo", "ajustes", "estado", "nota_director"):
            raise ErrorShorts(f"El campo '{k}' no se cambia desde aquí.")
        m[k] = v
    guardar(m)
    return m
