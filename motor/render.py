"""Timeline -> mp4 con un solo comando de ffmpeg (filter_complex).

Salida: .cache/jobs/<id>/renders/v<N>.mp4 (o v<N>-preview.mp4) + hoja de contactos.
Solo se conservan las últimas `renders_a_conservar` versiones.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import cache
from . import config as cfg
from . import estilo as est
from . import manifiesto
from . import timeline as tlmod
from .util import ErrorShorts, correr, escribir_atomico, hex_a_ass, leer_json


def _par(n: float) -> int:
    return int(round(n / 2)) * 2


def _tc(seg: float) -> str:
    cs = int(round(seg * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# ---------- subtítulos (ASS) ----------

def _texto_ass(texto: str, mayus: bool, resaltado: str) -> str:
    t = texto.replace("{", "").replace("}", "").replace("\n", "\\N")
    if mayus:
        t = t.upper()
    # *palabra* -> palabra en color de resaltado
    return re.sub(r"\*(.+?)\*", lambda mt: f"{{\\c{resaltado}}}{mt.group(1)}{{\\r}}", t)


def generar_ass(textos: list[dict], e: dict) -> str:
    W, H = e["formato"]["ancho"], e["formato"]["alto"]
    s, ti = e["subtitulos"], e["titulo"]
    # En los "override tags" de ASS el color va sin alfa: &HBBGGRR&
    resaltado = "&H" + hex_a_ass(s.get("color_resaltado", "#FFD400"))[4:] + "&"
    estilos = [
        # Nombre, fuente, tamaño, color, color2, borde, fondo, negrita..., BorderStyle, Outline, Shadow, Alineación, MargenL, MargenR, MargenV
        f"Style: Subtitulo,{s['fuente']},{s['tamano']},{hex_a_ass(s['color'])},&H000000FF,"
        f"{hex_a_ass(s.get('color_borde', '#000000'))},&H96000000,1,0,0,0,100,100,0,0,1,"
        f"{s['borde']},{s.get('sombra', 0)},2,80,80,{int(H * (1 - s['posicion_y']))},1",
        f"Style: Titulo,{ti.get('fuente', s['fuente'])},{ti['tamano']},{hex_a_ass(ti['color'])},&H000000FF,"
        f"{hex_a_ass(ti.get('fondo', '#000000CC'))},{hex_a_ass(ti.get('fondo', '#000000CC'))},1,0,0,0,100,100,0,0,3,"
        f"18,0,8,80,80,{int(H * ti['posicion_y'])},1",
    ]
    eventos = []
    for t in sorted(textos, key=lambda x: x["inicio"]):
        tipo = t.get("tipo", "subtitulo")
        if tipo == "nota":
            continue  # las notas son para humanos, no se queman en el video
        nombre = "Titulo" if tipo == "titulo" else "Subtitulo"
        mayus = (ti if tipo == "titulo" else s).get("mayusculas", False)
        eventos.append(f"Dialogue: 0,{_tc(t['inicio'])},{_tc(t['fin'])},{nombre},,0,0,0,,"
                       f"{_texto_ass(t['texto'], mayus, resaltado)}")
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *estilos, "",
        "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *eventos, "",
    ])


# ---------- render ----------

def _info(ruta: Path) -> dict:
    p = cache.dir_media(ruta) / "info.json"
    if not p.exists():
        cache.analizar(ruta)
    return leer_json(p)


def render(video_id: str, preview: bool = False) -> dict:
    m = manifiesto.cargar(video_id)
    tl = tlmod.cargar(video_id)
    errores, avisos = tlmod.validar(video_id, tl)
    if errores:
        raise ErrorShorts("El timeline tiene errores, no se renderiza:\n- " + "\n- ".join(errores))
    if m["version"] == 0:
        m = manifiesto.agregar_feedback(video_id, "primer corte", autor="sistema")
    e = est.resolver(video_id)

    W, H, fps = e["formato"]["ancho"], e["formato"]["alto"], e["formato"]["fps"]
    escala_salida = 0.5 if preview else 1.0
    fuentes = manifiesto.alias_material(m)
    job = cfg.cache_job(video_id)
    renders = job / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    nombre = f"v{m['version']}{'-preview' if preview else ''}"
    salida = renders / f"{nombre}.mp4"

    # Entradas: cada archivo fuente una sola vez
    usados = list(dict.fromkeys(c["fuente"] for c in tl["clips"]))
    entradas: list[str] = []
    idx = {}
    for i, alias in enumerate(usados):
        entradas += ["-i", str(fuentes[alias])]
        idx[alias] = i

    filtros = []
    pares = []
    for k, c in enumerate(tl["clips"]):
        info = _info(fuentes[c["fuente"]])
        s = idx[c["fuente"]]
        a, b = c["entrada"], c["salida"]
        d = b - a
        zoom = c.get("zoom", e["encuadre"].get("zoom", 1.0))
        factor = max(W / info["ancho"], H / info["alto"]) * zoom
        sw, sh = _par(info["ancho"] * factor), _par(info["alto"] * factor)
        cx = int((sw - W) * c.get("encuadre_x", 0.5))
        cy = int((sh - H) * c.get("encuadre_y", 0.5))
        filtros.append(
            f"[{s}:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,"
            f"scale={sw}:{sh},crop={W}:{H}:{cx}:{cy},fps={fps},setsar=1,format=yuv420p[v{k}]")
        if info["tiene_audio"]:
            filtros.append(
                f"[{s}:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=channel_layouts=stereo,afade=t=in:d=0.01,"
                f"afade=t=out:st={max(d - 0.015, 0):.3f}:d=0.015[a{k}]")
        else:
            filtros.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[a{k}]")
        pares.append(f"[v{k}][a{k}]")
    n = len(tl["clips"])
    filtros.append(f"{''.join(pares)}concat=n={n}:v=1:a=1[vc][ac]")

    # Subtítulos y títulos
    textos = list(tl.get("textos", []))
    auto = tl.get("subtitulos_auto", e["subtitulos"].get("auto", True))
    if auto and not any(t.get("tipo", "subtitulo") == "subtitulo" for t in textos):
        textos += tlmod.subtitulos_auto(video_id, tl, e["subtitulos"].get("palabras_por_linea", 3))
    v_final = "vc"
    if any(t.get("tipo") != "nota" for t in textos):
        ass = job / f"{nombre}.ass"
        escribir_atomico(ass, generar_ass(textos, e))
        filtros.append(f"[vc]ass=f='{ass}'[vs]")
        v_final = "vs"
    if preview:
        filtros.append(f"[{v_final}]scale={_par(W * escala_salida)}:{_par(H * escala_salida)}[vp]")
        v_final = "vp"

    # Música (el timeline gana sobre el estilo; null en ambos = sin música)
    total = tlmod.duracion_total(tl)
    mus = tl.get("musica") or (
        {"fuente": e["audio"]["musica"], "volumen_db": e["audio"].get("musica_db", -20)}
        if e["audio"].get("musica") else None)
    a_final = "ac"
    if mus:
        entradas += ["-stream_loop", "-1", "-i", str(cfg.ruta_material(mus["fuente"]))]
        mi = len(usados)
        filtros.append(
            f"[{mi}:a]atrim=start={mus.get('entrada', 0)},asetpts=PTS-STARTPTS,"
            f"atrim=duration={total:.3f},aresample=48000,aformat=channel_layouts=stereo,"
            f"volume={mus.get('volumen_db', -20)}dB,afade=t=out:st={max(total - 1, 0):.3f}:d=1[mus]")
        if e["audio"].get("ducking", True):
            filtros.append("[ac]asplit=2[voz][sc]")
            filtros.append("[mus][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[musd]")
            filtros.append("[voz][musd]amix=inputs=2:duration=first:normalize=0[am]")
        else:
            filtros.append("[ac][mus]amix=inputs=2:duration=first:normalize=0[am]")
        a_final = "am"

    # Loudness objetivo de redes (−14 LUFS). Una pasada: suficiente; el QA lo mide.
    au = e["audio"]
    filtros.append(f"[{a_final}]loudnorm=I={au['loudness_lufs']}:TP={au['true_peak']}:LRA=11,"
                   f"aresample=48000[aout]")

    cmd = ["ffmpeg", "-hide_banner", "-y", *entradas,
           "-filter_complex", ";".join(filtros),
           "-map", f"[{v_final}]", "-map", "[aout]",
           "-c:v", "libx264", "-preset", "ultrafast" if preview else "veryfast",
           "-crf", "30" if preview else "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(salida)]
    with cache.candado(job):
        correr(cmd)
    contacto = cache.hoja_contactos(salida, renders / f"{nombre}-contacto.jpg")
    _limpiar_viejos(renders, m["version"])

    if m["estado"] == "borrador":
        manifiesto.fijar(video_id, estado="en-revision")
    return {"render": str(salida), "contacto": str(contacto), "version": m["version"],
            "duracion": total, "capas_estilo": e["_capas"], "avisos": avisos}


def _limpiar_viejos(renders: Path, version_actual: int) -> None:
    conservar = cfg.config().get("renders_a_conservar", 2)
    limite = version_actual - conservar
    for f in renders.iterdir():
        mt = re.match(r"v(\d+)", f.name)
        if mt and int(mt.group(1)) <= limite:
            f.unlink()
