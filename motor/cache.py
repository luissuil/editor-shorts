"""Análisis de material crudo, cacheado por hash del contenido.

Cada archivo se analiza UNA vez y queda en .cache/media/<hash>/:
  info.json        duración, resolución, fps, si tiene audio
  escenas.json     cortes detectados (PySceneDetect si está, si no ffmpeg)
  silencios.json   tramos de silencio (para quitar pausas)
  beats.json       tempo y beats (solo si librosa está instalado)
  transcript.json  palabras con tiempos (solo si faster-whisper está instalado)
  contacto.jpg     hoja de contactos con timecodes, para que un modelo "vea" el clip

Si el mismo clip se usa en tres videos, se reutiliza. Borrar .cache/ es seguro.
"""
from __future__ import annotations

import fcntl
import hashlib
import re
from contextlib import contextmanager
from pathlib import Path

from . import config as cfg
from .util import ErrorShorts, correr, escribir_json, ffprobe, leer_json

FUENTE_TC = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def hash_archivo(ruta: Path, bloque: int = 4 * 1024 * 1024) -> str:
    """Hash rápido: tamaño + primeros 4 MB + últimos 4 MB.
    Leer un crudo de 5 GB entero cada vez sería lentísimo, y esto basta
    para distinguir archivos distintos en la práctica."""
    tam = ruta.stat().st_size
    h = hashlib.sha256(str(tam).encode())
    with ruta.open("rb") as f:
        h.update(f.read(bloque))
        if tam > bloque:
            f.seek(max(tam - bloque, bloque))
            h.update(f.read(bloque))
    return h.hexdigest()[:16]


def dir_media(ruta: Path) -> Path:
    return cfg.cache_media() / hash_archivo(ruta)


@contextmanager
def candado(directorio: Path):
    """Evita que dos procesos analicen el mismo archivo a la vez."""
    directorio.mkdir(parents=True, exist_ok=True)
    with (directorio / ".lock").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


# ---------- pasos de análisis ----------

def _escenas(ruta: Path, umbral: float) -> list[float]:
    try:
        from scenedetect import ContentDetector, detect  # type: ignore
        escenas = detect(str(ruta), ContentDetector())
        return [round(ini.get_seconds(), 3) for ini, _ in escenas[1:]]
    except ImportError:
        res = correr(["ffmpeg", "-hide_banner", "-i", str(ruta), "-an",
                      "-vf", f"scale=320:-2,select='gt(scene,{umbral})',showinfo",
                      "-f", "null", "-"])
        return [round(float(t), 3) for t in re.findall(r"pts_time:([\d.]+)", res.stderr)]


def _silencios(ruta: Path, db: int, minimo: float) -> list[dict]:
    res = correr(["ffmpeg", "-hide_banner", "-i", str(ruta), "-vn",
                  "-af", f"silencedetect=noise={db}dB:d={minimo}", "-f", "null", "-"])
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", res.stderr)]
    fines = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", res.stderr)]
    return [{"inicio": round(i, 3), "fin": round(f, 3)} for i, f in zip(inicios, fines)]


def _beats(ruta: Path) -> dict | None:
    try:
        import librosa  # type: ignore
    except ImportError:
        return None
    y, sr = librosa.load(str(ruta), sr=22050, mono=True)
    tempo, cuadros = librosa.beat.beat_track(y=y, sr=sr)
    tiempos = librosa.frames_to_time(cuadros, sr=sr)
    return {"tempo": round(float(tempo), 1), "beats": [round(float(t), 3) for t in tiempos]}


def _transcript(ruta: Path) -> dict | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return None
    conf = cfg.config().get("transcripcion", {})
    modelo = WhisperModel(conf.get("modelo", "small"), compute_type="int8")
    segmentos, info = modelo.transcribe(str(ruta), language=conf.get("idioma"),
                                        word_timestamps=True, vad_filter=True)
    palabras = [{"p": w.word.strip(), "i": round(w.start, 3), "f": round(w.end, 3)}
                for s in segmentos for w in (s.words or [])]
    return {"idioma": info.language, "palabras": palabras}


def hoja_contactos(video: Path, salida: Path, cuadros: int = 12) -> Path:
    """Mosaico 4x3 con el timecode encima de cada cuadro."""
    dur = ffprobe(video)["duracion"]
    paso = max(dur / cuadros, 0.1)
    filtro = (f"fps=1/{paso:.3f},"
              "scale='if(gt(iw,ih),480,-2)':'if(gt(iw,ih),-2,480)',"
              f"drawtext=fontfile={FUENTE_TC}:text='%{{pts\\:hms}}':x=10:y=10:"
              "fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6,"
              "tile=4x3:padding=6:color=black")
    salida.parent.mkdir(parents=True, exist_ok=True)
    correr(["ffmpeg", "-hide_banner", "-y", "-i", str(video), "-vf", filtro,
            "-frames:v", "1", "-q:v", "3", str(salida)])
    return salida


# ---------- entrada principal ----------

def analizar(ruta: Path, forzar: bool = False) -> dict:
    if not ruta.exists():
        raise ErrorShorts(f"No existe el archivo {ruta}")
    d = dir_media(ruta)
    conf = cfg.config().get("analisis", {})
    with candado(d):
        def paso(nombre: str, fn):
            p = d / nombre
            if forzar or not p.exists():
                datos = fn()
                if datos is not None:
                    escribir_json(p, datos)
            return leer_json(p) if p.exists() else None

        info = paso("info.json", lambda: {**ffprobe(ruta), "archivo": ruta.name})
        paso("escenas.json", lambda: _escenas(ruta, conf.get("umbral_escena", 0.3)))
        if info["tiene_audio"]:
            paso("silencios.json", lambda: _silencios(
                ruta, conf.get("silencio_db", -35), conf.get("silencio_min", 0.4)))
            paso("beats.json", lambda: _beats(ruta))
            paso("transcript.json", lambda: _transcript(ruta))
        if info.get("ancho") and (forzar or not (d / "contacto.jpg").exists()):
            hoja_contactos(ruta, d / "contacto.jpg")
    return resumen(ruta)


def resumen(ruta: Path) -> dict:
    """Lo que el agente necesita saber de un clip, en pocas líneas."""
    d = dir_media(ruta)
    def cargar(n):
        p = d / n
        return leer_json(p) if p.exists() else None
    info = cargar("info.json") or {}
    escenas = cargar("escenas.json") or []
    silencios = cargar("silencios.json") or []
    beats = cargar("beats.json")
    tr = cargar("transcript.json")
    return {
        "archivo": ruta.name,
        "cache": str(d.relative_to(cfg.RAIZ)) if d.is_relative_to(cfg.RAIZ) else str(d),
        "duracion": info.get("duracion"),
        "resolucion": f"{info.get('ancho')}x{info.get('alto')}" if info.get("ancho") else None,
        "cortes_detectados": len(escenas),
        "silencios": len(silencios),
        "tempo": beats["tempo"] if beats else None,
        "transcript": f"{len(tr['palabras'])} palabras" if tr else "no (instala faster-whisper)",
    }
