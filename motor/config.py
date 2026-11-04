"""Rutas del repo y lectura de config.yaml. Todo lo demás importa rutas desde aquí."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from .util import leer_yaml

RAIZ = Path(__file__).resolve().parent.parent
VIDEOS = RAIZ / "videos"
ESTILOS = RAIZ / "estilos"
PROMPTS = RAIZ / "prompts"


@lru_cache
def config() -> dict:
    return leer_yaml(RAIZ / "config.yaml")


def _ruta_config(clave: str, defecto: str) -> Path:
    p = Path(config().get(clave, defecto)).expanduser()
    return p if p.is_absolute() else (RAIZ / p).resolve()


def material_raiz() -> Path:
    return _ruta_config("material_raiz", "./material")


def salidas() -> Path:
    return _ruta_config("salidas", "./salidas")


def cache() -> Path:
    return _ruta_config("cache", "./.cache")


def cache_media() -> Path:
    return cache() / "media"


def cache_job(video_id: str) -> Path:
    return cache() / "jobs" / video_id


def ruta_material(relativa: str) -> Path:
    """Resuelve una ruta del manifiesto (relativa a material_raiz)."""
    p = Path(relativa).expanduser()
    return p if p.is_absolute() else material_raiz() / p
