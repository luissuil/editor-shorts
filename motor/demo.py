"""Genera material de prueba sintético (sin descargar nada) para probar el flujo completo:
  material/acme/crudos/entrevista-01.mp4   40 s, horizontal, "voz" con pausas
  material/acme/crudos/producto-02.mp4     20 s, horizontal, sin audio, cambios de plano
  material/musica/beat-120.wav             30 s, bombo a 120 BPM
  material/referencias/ref-acme.mp4        20 s, vertical, cortes rápidos (la "referencia")
"""
from __future__ import annotations

from . import config as cfg
from .util import correr

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _texto(t: str, y: str = "(h-text_h)/2", tam: int = 110, color: str = "white") -> str:
    return (f"drawtext=fontfile={FUENTE}:text='{t}':x=(w-text_w)/2:y={y}:"
            f"fontsize={tam}:fontcolor={color}:box=1:boxcolor=black@0.5:boxborderw=20")


def _planos(colores: list[str], seg: float, tam: str, extra_vf: str) -> list[str]:
    """Video hecho de planos de colores distintos (cortes secos que el detector encuentra)."""
    fuentes = ";".join(f"color=c={c}:s={tam}:r=30:d={seg}[c{i}]" for i, c in enumerate(colores))
    concat = "".join(f"[c{i}]" for i in range(len(colores)))
    return ["-filter_complex",
            f"{fuentes};{concat}concat=n={len(colores)}:v=1:a=0,{extra_vf}[v]", "-map", "[v]"]


COLORES = ["0x2C3E50", "0xF1C40F", "0x8E44AD", "0xECF0F1", "0xC0392B", "0x7FDBFF", "0x16A085", "0xF39C12"]  # alterna oscuro/claro


def generar() -> list[str]:
    raiz = cfg.material_raiz()
    hechos = []
    trabajos = {
        "acme/crudos/entrevista-01.mp4": [
            "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=40",
            "-f", "lavfi", "-i",
            # tono que imita voz: 6 s hablando, 2 s de pausa
            "aevalsrc='0.4*sin(2*PI*180*t)*(0.6+0.4*sin(2*PI*4*t))*lt(mod(t\\,8)\\,6)':s=48000:d=40",
            "-vf", _texto("ENTREVISTA") + "," + _texto("%{pts\\:hms}", "h-200", 70),
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest"],
        "acme/crudos/producto-02.mp4": [
            *_planos((COLORES * 2)[:8], 2.5, "1920x1080", _texto("PRODUCTO")),
            "-c:v", "libx264", "-preset", "ultrafast", "-an"],
        "musica/beat-120.wav": [
            "-f", "lavfi", "-i",
            "aevalsrc='0.8*sin(2*PI*55*t)*exp(-18*mod(t\\,0.5))+0.1*sin(2*PI*880*t)*exp(-60*mod(t+0.25\\,0.5))':s=48000:d=30"],
        "referencias/ref-acme.mp4": [
            "-f", "lavfi", "-i", "aevalsrc='0.5*sin(2*PI*55*t)*exp(-18*mod(t\\,0.5))':s=48000:d=20",
            *_planos((COLORES * 3)[:20], 1.0, "1080x1920",
                     _texto("REFERENCIA", "300", 100) + ","
                     + _texto("subtitulos amarillos", "h*0.70-text_h", 72, "0xFFD400")),
            "-map", "0:a", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest"],
    }
    for rel, args in trabajos.items():
        destino = raiz / rel
        if destino.exists():
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        correr(["ffmpeg", "-hide_banner", "-y", *args, str(destino)])
        hechos.append(rel)
    return hechos
