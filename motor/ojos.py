"""Los "ojos" de Opus: un modelo barato de video que describe un clip (imagen + audio)
y devuelve JSON. Opus nunca ve el video completo, solo esta descripción.

Por defecto usa Gemini Flash-Lite (entiende el audio junto con la imagen).
Requiere: pip install google-genai  y  la variable GEMINI_API_KEY.
El resultado se cachea junto al análisis del archivo: ojos-<prompt>.json
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import cache
from . import config as cfg
from .util import ErrorShorts, escribir_json, leer_json


def mirar(ruta: Path, prompt: str = "referencia", forzar: bool = False) -> dict:
    archivo_prompt = cfg.PROMPTS / f"{prompt}.md"
    if not archivo_prompt.exists():
        raise ErrorShorts(f"No existe el prompt prompts/{prompt}.md")
    destino = cache.dir_media(ruta) / f"ojos-{prompt}.json"
    if destino.exists() and not forzar:
        return leer_json(destino)

    conf = cfg.config().get("ojos", {})
    if conf.get("proveedor", "gemini") != "gemini":
        raise ErrorShorts("Por ahora solo está implementado el proveedor 'gemini'.")
    if not os.environ.get("GEMINI_API_KEY"):
        raise ErrorShorts("Falta GEMINI_API_KEY. Sin ella, el agente usa la hoja de contactos "
                          f"({cache.dir_media(ruta) / 'contacto.jpg'}) en vez del modelo de video.")
    try:
        from google import genai  # type: ignore
    except ImportError as exc:
        raise ErrorShorts("Instala el SDK: pip install google-genai") from exc

    cliente = genai.Client()
    subido = cliente.files.upload(file=str(ruta))
    while subido.state and subido.state.name == "PROCESSING":
        time.sleep(2)
        subido = cliente.files.get(name=subido.name)
    resp = cliente.models.generate_content(
        model=conf.get("modelo", "gemini-3.1-flash-lite"),
        contents=[subido, archivo_prompt.read_text(encoding="utf-8")],
        config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    try:
        datos = json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise ErrorShorts(f"El modelo no devolvió JSON válido:\n{resp.text[:500]}") from exc
    escribir_json(destino, datos)
    try:
        cliente.files.delete(name=subido.name)
    except Exception:
        pass  # Gemini los borra solo a las 48 h
    return datos
