"""QA automático del último render. Revisa contra:
  - las reglas del style.json resuelto (ritmo, duración, cortes al beat)
  - el checklist base de cualquier short (estilos/_base/checklist.yaml)
Lo visual contra la referencia lo hace el agente qa-reviewer mirando las hojas de contactos.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import cache
from . import config as cfg
from . import estilo as est
from . import manifiesto
from . import timeline as tlmod
from .util import ErrorShorts, correr, escribir_json, ffprobe, leer_json, leer_yaml


def _ultimo_render(video_id: str, version: int) -> Path:
    r = cfg.cache_job(video_id) / "renders"
    for nombre in (f"v{version}.mp4", f"v{version}-preview.mp4"):
        if (r / nombre).exists():
            return r / nombre
    raise ErrorShorts(f"No hay render de la v{version}. Corre primero: ./shorts render {video_id}")


def _loudness(ruta: Path) -> tuple[float, float]:
    res = correr(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-vn",
                  "-af", "ebur128=peak=true", "-f", "null", "-"])
    integrado = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", res.stderr)[-1])
    pico = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", res.stderr)[-1])
    return integrado, pico


def revisar(video_id: str) -> dict:
    m = manifiesto.cargar(video_id)
    tl = tlmod.cargar(video_id)
    e = est.cargar_resuelto(video_id)
    ck = leer_yaml(cfg.ESTILOS / "_base" / "checklist.yaml")
    ruta = _ultimo_render(video_id, m["version"])
    info = ffprobe(ruta)
    items: list[dict] = []

    def item(clave, ok, detalle, nivel="error"):
        items.append({"check": clave, "ok": bool(ok), "nivel": "ok" if ok else nivel, "detalle": detalle})

    # 1. Formato
    W, H = e["formato"]["ancho"], e["formato"]["alto"]
    es_preview = "preview" in ruta.name
    esperado = (W // 2, H // 2) if es_preview else (W, H)
    item("formato", (info["ancho"], info["alto"]) == esperado,
         f"{info['ancho']}x{info['alto']} (esperado {esperado[0]}x{esperado[1]})")

    # 2. Duración
    d = info["duracion"]
    rango = e["duracion"]
    item("duracion", rango["min"] <= d <= rango["max"],
         f"{d:.1f}s (rango del estilo {rango['min']}–{rango['max']}s)", "aviso")

    # 3. Ritmo: duración de cada plano
    r = e["ritmo"]
    fuera = [f"#{i} {c['salida'] - c['entrada']:.2f}s" for i, c in enumerate(tl["clips"])
             if not r["plano_min"] <= c["salida"] - c["entrada"] <= r["plano_max"]]
    item("planos", not fuera,
         f"todos entre {r['plano_min']} y {r['plano_max']}s" if not fuera
         else f"fuera de rango: {', '.join(fuera)}", "aviso")

    # 4. Hook
    seg = ck.get("hook_segundos", 3)
    hook = any(t.get("tipo") == "titulo" and t["inicio"] < seg for t in tl.get("textos", [])) \
        or "hook" in (tl["clips"][0].get("nota", "") if tl["clips"] else "")
    item("hook", hook, f"título o clip marcado 'hook' en los primeros {seg}s" if hook
         else f"no hay título ni clip marcado como hook en los primeros {seg}s", "aviso")

    # 5. Silencios largos (si no hay música que los tape)
    if info["tiene_audio"]:
        lim = ck.get("silencio_max", 1.0)
        res = correr(["ffmpeg", "-hide_banner", "-i", str(ruta), "-vn", "-af",
                      f"silencedetect=noise=-40dB:d={lim}", "-f", "null", "-"])
        silencios = [round(float(x), 1) for x in re.findall(r"silence_start: ([\d.]+)", res.stderr)
                     if float(x) < d - 0.5]
        item("silencios", not silencios,
             f"sin silencios de más de {lim}s" if not silencios
             else f"silencios de más de {lim}s en: {silencios}", "aviso")

        # 6. Loudness
        integrado, pico = _loudness(ruta)
        obj, tol = e["audio"]["loudness_lufs"], ck.get("loudness_tolerancia", 1.5)
        item("loudness", abs(integrado - obj) <= tol and pico <= e["audio"]["true_peak"] + 0.5,
             f"{integrado} LUFS, pico {pico} dBFS (objetivo {obj}±{tol} LUFS, pico ≤ {e['audio']['true_peak']})")

    # 7. Zonas seguras de la interfaz de cada app
    s, ti = e["subtitulos"], e["titulo"]
    problemas = []
    for plat in e.get("plataformas", ck.get("plataformas", [])):
        z = ck["zonas_seguras"][plat]
        if s["posicion_y"] > 1 - z["abajo"]:
            problemas.append(f"subtítulos tapados por la interfaz de {plat}")
        if ti["posicion_y"] < z["arriba"]:
            problemas.append(f"título tapado por la interfaz de {plat}")
    item("zonas_seguras", not problemas, "; ".join(problemas) or "subtítulos y títulos fuera de la interfaz")

    # 8. Legibilidad
    largos = [t["texto"] for t in tl.get("textos", [])
              if t.get("tipo", "subtitulo") == "subtitulo"
              and len(t["texto"]) > ck.get("caracteres_por_linea_max", 24)]
    item("legibilidad", s["tamano"] >= ck.get("subtitulos_tamano_min", 56) and not largos,
         f"tamaño {s['tamano']}px" + (f"; subtítulos muy largos: {largos[:3]}" if largos else ""), "aviso")

    # 9. Cortes al beat (solo si el estilo lo pide y hay beats analizados)
    mus = tl.get("musica")
    if r.get("cortes_al_beat") and mus:
        p = cache.dir_media(cfg.ruta_material(mus["fuente"])) / "beats.json"
        if p.exists():
            beats = [b - mus.get("entrada", 0) for b in leer_json(p)["beats"]]
            cortes, t = [], 0.0
            for c in tl["clips"][:-1]:
                t += c["salida"] - c["entrada"]
                cortes.append(t)
            tolb = r.get("tolerancia_beat", 0.08)
            mal = [round(c, 2) for c in cortes if min(abs(c - b) for b in beats) > tolb]
            item("cortes_al_beat", not mal, "todos los cortes caen en beat" if not mal
                 else f"cortes fuera de beat (>{tolb}s): {mal}", "aviso")
        else:
            item("cortes_al_beat", True, "no se pudo medir: instala librosa", "aviso")

    errores = [i for i in items if i["nivel"] == "error"]
    avisos = [i for i in items if i["nivel"] == "aviso"]
    resultado = "falla" if errores else ("avisos" if avisos else "ok")
    reporte = {
        "video": video_id, "version": m["version"], "render": str(ruta),
        "resultado": resultado, "checks": items,
        "contacto_render": str(ruta.with_name(ruta.stem + "-contacto.jpg")),
    }
    if m.get("referencia"):
        ref = cache.dir_media(cfg.ruta_material(m["referencia"])) / "contacto.jpg"
        reporte["contacto_referencia"] = str(ref) if ref.exists() else None
    escribir_json(cfg.cache_job(video_id) / f"qa-v{m['version']}.json", reporte)
    return reporte
