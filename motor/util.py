"""Utilidades compartidas: ffmpeg, JSON/YAML atómico, merge de dicts, slugs."""
from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml


class ErrorShorts(Exception):
    """Error esperado (mensaje legible para el editor, sin traceback)."""


# ---------- ffmpeg / ffprobe ----------

def correr(cmd: list[str], capturar: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=capturar, text=True)
    if res.returncode != 0:
        cola = (res.stderr or "")[-2000:]
        raise ErrorShorts(f"Falló: {' '.join(cmd[:4])} ...\n{cola}")
    return res


def ffprobe(ruta: Path) -> dict:
    res = correr([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(ruta),
    ])
    datos = json.loads(res.stdout)
    video = next((s for s in datos["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in datos["streams"] if s["codec_type"] == "audio"), None)
    info = {"duracion": float(datos["format"]["duration"]), "tiene_audio": audio is not None}
    if video:
        num, den = video.get("r_frame_rate", "30/1").split("/")
        info.update(ancho=int(video["width"]), alto=int(video["height"]),
                    fps=round(float(num) / float(den or 1), 3))
    return info


# ---------- archivos ----------

def escribir_atomico(ruta: Path, texto: str) -> None:
    """Escribe a un temporal y renombra: nunca deja un archivo a medias
    aunque dos editores corran comandos a la vez."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=ruta.parent, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(texto)
    os.replace(tmp, ruta)


def leer_json(ruta: Path) -> Any:
    return json.loads(ruta.read_text(encoding="utf-8"))


def escribir_json(ruta: Path, datos: Any) -> None:
    escribir_atomico(ruta, json.dumps(datos, ensure_ascii=False, indent=2) + "\n")


def leer_yaml(ruta: Path) -> Any:
    return yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}


def escribir_yaml(ruta: Path, datos: Any) -> None:
    escribir_atomico(ruta, yaml.safe_dump(datos, allow_unicode=True, sort_keys=False, width=100))


# ---------- varios ----------

def fusionar(base: dict, encima: dict | None) -> dict:
    """Merge profundo: `encima` gana. Las listas se reemplazan, no se suman."""
    res = copy.deepcopy(base)
    for k, v in (encima or {}).items():
        if isinstance(v, dict) and isinstance(res.get(k), dict):
            res[k] = fusionar(res[k], v)
        else:
            res[k] = copy.deepcopy(v)
    return res


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t or "video"


def hex_a_ass(color: str) -> str:
    """'#RRGGBB' o '#RRGGBBAA' -> '&HAABBGGRR' (formato de color de ASS)."""
    c = color.lstrip("#")
    r, g, b = c[0:2], c[2:4], c[4:6]
    alfa = c[6:8] if len(c) == 8 else "FF"
    # En ASS 00 = opaco, FF = transparente (al revés que en CSS)
    alfa_ass = f"{255 - int(alfa, 16):02X}"
    return f"&H{alfa_ass}{b}{g}{r}".upper()
