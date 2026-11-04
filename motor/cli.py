"""CLI `./shorts`. Los editores (y los comandos de Claude) solo usan esto.

  ./shorts --help              lista de comandos
  ./shorts <comando> --help    ayuda de cada uno
  ./shorts --json <comando>    salida en JSON (la usan los agentes)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import cache, demo, estilo, manifiesto, ojos, qa, render, timeline
from . import config as cfg
from .util import ErrorShorts, leer_json

SALIDA_JSON = False


def mostrar(datos) -> None:
    if SALIDA_JSON or not isinstance(datos, (dict, list)):
        print(json.dumps(datos, ensure_ascii=False, indent=2) if SALIDA_JSON else datos)
        return
    if isinstance(datos, list):
        for d in datos:
            mostrar(d)
            print()
        return
    ancho = max((len(str(k)) for k in datos), default=0)
    for k, v in datos.items():
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        print(f"{str(k).ljust(ancho)}  {v}")


def resolver_id(texto: str) -> str:
    """Acepta el id completo o un pedazo único: `acme_lanz` -> 2026-11-04_acme_lanzamiento."""
    if manifiesto.ruta(texto).exists():
        return texto
    cand = [m["id"] for m in manifiesto.listar() if texto.lower() in m["id"]]
    if len(cand) == 1:
        return cand[0]
    if not cand:
        raise ErrorShorts(f"No hay ningún video que coincida con '{texto}'. Prueba ./shorts buscar")
    raise ErrorShorts(f"'{texto}' coincide con varios: {', '.join(cand)}")


# ---------- comandos ----------

def c_nuevo(a):
    m = manifiesto.crear(a.cliente, a.titulo, a.material, a.estilo, a.brief or "", a.referencia, a.fecha)
    mostrar({"creado": m["id"], "manifiesto": f"videos/{m['id']}.yaml",
             "timeline": f"videos/{m['id']}.timeline.json",
             "siguiente": f"./shorts analizar {m['id']}"})


def c_buscar(a):
    filas = []
    for m in manifiesto.listar():
        texto = " ".join(str(m.get(k, "")) for k in ("id", "cliente", "titulo", "brief")).lower()
        if a.texto and a.texto.lower() not in texto:
            continue
        if a.estado and m["estado"] != a.estado:
            continue
        filas.append({"id": m["id"], "estado": m["estado"], "version": m["version"],
                      "estilo": m.get("estilo") or "(director)",
                      "ultimo_cambio": m["historial"][-1]["nota"] if m["historial"] else "-"})
    if SALIDA_JSON:
        return mostrar(filas)
    if not filas:
        return print("Sin resultados.")
    print(f"{'ID':42} {'ESTADO':12} {'V':>3}  {'ESTILO':14} ÚLTIMO CAMBIO")
    for f in filas:
        print(f"{f['id']:42} {f['estado']:12} {f['version']:>3}  {f['estilo']:14} {f['ultimo_cambio'][:50]}")


def c_ver(a):
    vid = resolver_id(a.id)
    m = manifiesto.cargar(vid)
    tl = timeline.cargar(vid)
    qa_p = cfg.cache_job(vid) / f"qa-v{m['version']}.json"
    renders = cfg.cache_job(vid) / "renders"
    mostrar({
        **{k: m.get(k) for k in ("id", "estado", "version", "estilo", "referencia", "brief", "ajustes")},
        "clips": len(tl.get("clips", [])), "duracion": timeline.duracion_total(tl),
        "historial": [f"v{h['v']}: {h['nota']}" for h in m["historial"]],
        "renders": sorted(p.name for p in renders.glob("*.mp4")) if renders.exists() else [],
        "qa": leer_json(qa_p)["resultado"] if qa_p.exists() else "sin QA",
    })


def c_analizar(a):
    vid = resolver_id(a.id)
    m = manifiesto.cargar(vid)
    archivos = list(manifiesto.alias_material(m).values())
    if m.get("referencia"):
        archivos.append(cfg.ruta_material(m["referencia"]))
    tl = timeline.cargar(vid)
    if tl.get("musica"):
        archivos.append(cfg.ruta_material(tl["musica"]["fuente"]))
    mostrar([cache.analizar(p, a.forzar) for p in archivos])


def c_analizar_archivo(a):
    mostrar(cache.analizar(cfg.ruta_material(a.ruta), a.forzar))


def c_estilo(a):
    mostrar(estilo.resolver(resolver_id(a.id)))


def c_medir_referencia(a):
    mostrar(estilo.medir_referencia(resolver_id(a.id)))


def c_fijar(a):
    vid = resolver_id(a.id)
    campos = {}
    if a.estilo:
        if a.estilo not in manifiesto.presets():
            raise ErrorShorts(f"Preset desconocido. Opciones: {manifiesto.presets()}")
        campos["estilo"] = a.estilo
    if a.ajustes is not None:
        campos["ajustes"] = json.loads(a.ajustes)
    if a.estado:
        campos["estado"] = a.estado
    if a.nota_director:
        campos["nota_director"] = a.nota_director
    m = manifiesto.fijar(vid, **campos)
    mostrar({k: m.get(k) for k in ("id", "estilo", "ajustes", "estado", "nota_director")})


def c_feedback(a):
    m = manifiesto.agregar_feedback(resolver_id(a.id), a.nota, a.autor)
    mostrar({"id": m["id"], "nueva_version": m["version"], "nota": a.nota})


def c_validar(a):
    vid = resolver_id(a.id)
    errores, avisos = timeline.validar(vid)
    mostrar({"valido": not errores, "errores": errores, "avisos": avisos})
    if errores:
        sys.exit(1)


def c_render(a):
    mostrar(render.render(resolver_id(a.id), a.preview))


def c_qa(a):
    r = qa.revisar(resolver_id(a.id))
    if SALIDA_JSON:
        return mostrar(r)
    print(f"QA {r['video']} v{r['version']}: {r['resultado'].upper()}")
    for i in r["checks"]:
        marca = {"ok": "✔", "aviso": "!", "error": "✘"}[i["nivel"]]
        print(f"  {marca} {i['check']:15} {i['detalle']}")
    print(f"  hoja de contactos: {r['contacto_render']}")


def c_aprobar(a):
    vid = resolver_id(a.id)
    m = manifiesto.cargar(vid)
    final = cfg.cache_job(vid) / "renders" / f"v{m['version']}.mp4"
    if not final.exists():
        raise ErrorShorts(f"No hay render final de la v{m['version']} (solo preview). "
                          f"Corre: ./shorts render {vid}")
    qa_p = cfg.cache_job(vid) / f"qa-v{m['version']}.json"
    if not a.forzar:
        if not qa_p.exists():
            raise ErrorShorts(f"Falta el QA de la v{m['version']}. Corre: ./shorts qa {vid}")
        if leer_json(qa_p)["resultado"] == "falla":
            raise ErrorShorts("El QA falló. Corrige o aprueba igual con --forzar.")
    destino = cfg.salidas() / f"{vid}_v{m['version']}.mp4"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(final, destino)
    manifiesto.fijar(vid, estado="aprobado")
    shutil.rmtree(cfg.cache_job(vid) / "renders", ignore_errors=True)
    mostrar({"aprobado": vid, "archivo": str(destino.relative_to(cfg.RAIZ))
             if destino.is_relative_to(cfg.RAIZ) else str(destino)})


def c_entregado(a):
    m = manifiesto.fijar(resolver_id(a.id), estado="entregado")
    mostrar({"id": m["id"], "estado": m["estado"]})


def c_guardar_estilo(a):
    p = estilo.guardar_preset(resolver_id(a.id), a.nombre, a.forzar, a.cuando)
    mostrar({"preset": a.nombre, "archivo": str(p.relative_to(cfg.RAIZ))})


def c_ojos(a):
    mostrar(ojos.mirar(cfg.ruta_material(a.ruta), a.prompt, a.forzar))


def c_contacto(a):
    origen = Path(a.video)
    mostrar({"contacto": str(cache.hoja_contactos(origen, origen.with_suffix(".contacto.jpg")))})


def c_limpiar(a):
    if a.todo:
        shutil.rmtree(cfg.cache(), ignore_errors=True)
        return mostrar({"borrado": str(cfg.cache())})
    borrados = []
    for m in manifiesto.listar():
        if m["estado"] == "entregado" and cfg.cache_job(m["id"]).exists():
            shutil.rmtree(cfg.cache_job(m["id"]))
            borrados.append(m["id"])
    mostrar({"jobs_borrados": borrados})


def c_presets(a):
    mostrar(manifiesto.presets())


def c_demo(a):
    hechos = demo.generar()
    mostrar({"material_generado": hechos or "ya existía", "en": str(cfg.material_raiz())})


def c_hook_validar(a):
    """Hook de Claude Code: valida el timeline cada vez que un agente lo edita.
    Exit code 2 = Claude ve el error y lo corrige."""
    try:
        evento = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    ruta = (evento.get("tool_input") or {}).get("file_path", "")
    if not ruta.endswith(".timeline.json"):
        return
    vid = Path(ruta).name.removesuffix(".timeline.json")
    try:
        tl = json.loads(Path(ruta).read_text(encoding="utf-8"))
        errores, _ = timeline.validar(vid, tl)
    except (json.JSONDecodeError, ErrorShorts) as exc:
        errores = [str(exc)]
    if errores:
        print("Timeline inválido:\n- " + "\n- ".join(errores), file=sys.stderr)
        sys.exit(2)


# ---------- parser ----------

def main(argv=None) -> None:
    global SALIDA_JSON
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["hook-validar"]:  # comando oculto, lo llama el hook de Claude Code
        return c_hook_validar(None)
    p = argparse.ArgumentParser(prog="shorts", description="Editor de shorts: CLI del repo.")
    p.add_argument("--json", action="store_true", help="salida en JSON")
    sub = p.add_subparsers(dest="cmd", required=True, metavar="comando")

    def cmd(nombre, fn, ayuda):
        s = sub.add_parser(nombre, help=ayuda, description=ayuda)
        s.set_defaults(fn=fn)
        return s

    s = cmd("nuevo", c_nuevo, "crea el manifiesto de un video nuevo")
    s.add_argument("--cliente", required=True)
    s.add_argument("--titulo", required=True)
    s.add_argument("--material", nargs="+", required=True, help="rutas relativas a material_raiz")
    s.add_argument("--estilo", help="preset; si no se da, lo elige el director")
    s.add_argument("--referencia", help="video de referencia (opcional)")
    s.add_argument("--brief", help="instrucciones en texto")
    s.add_argument("--fecha", help="YYYY-MM-DD (por defecto hoy)")

    s = cmd("buscar", c_buscar, "lista videos (filtra por texto o estado)")
    s.add_argument("texto", nargs="?")
    s.add_argument("--estado", choices=manifiesto.ESTADOS)

    cmd("ver", c_ver, "resumen de un video").add_argument("id")

    s = cmd("analizar", c_analizar, "analiza todo el material de un video (cacheado)")
    s.add_argument("id")
    s.add_argument("--forzar", action="store_true")

    s = cmd("analizar-archivo", c_analizar_archivo, "analiza un archivo suelto")
    s.add_argument("ruta")
    s.add_argument("--forzar", action="store_true")

    cmd("estilo", c_estilo, "resuelve y muestra el estilo final").add_argument("id")
    cmd("medir-referencia", c_medir_referencia, "mide ritmo y duración de la referencia").add_argument("id")

    s = cmd("fijar", c_fijar, "cambia estilo/ajustes/estado (lo usan director y comandos)")
    s.add_argument("id")
    s.add_argument("--estilo")
    s.add_argument("--ajustes", help='JSON, p. ej. \'{"subtitulos": {"color": "#FFD400"}}\'')
    s.add_argument("--estado", choices=manifiesto.ESTADOS)
    s.add_argument("--nota-director")

    s = cmd("feedback", c_feedback, "abre una versión nueva con el feedback en el historial")
    s.add_argument("id")
    s.add_argument("nota")
    s.add_argument("--autor", default="editor")

    cmd("validar", c_validar, "valida el timeline").add_argument("id")

    s = cmd("render", c_render, "renderiza la versión actual")
    s.add_argument("id")
    s.add_argument("--preview", action="store_true", help="mitad de resolución, rápido")

    cmd("qa", c_qa, "QA automático del último render").add_argument("id")

    s = cmd("aprobar", c_aprobar, "copia el render a salidas/ y marca aprobado")
    s.add_argument("id")
    s.add_argument("--forzar", action="store_true")

    cmd("entregado", c_entregado, "marca un video como entregado al cliente").add_argument("id")

    s = cmd("guardar-estilo", c_guardar_estilo, "guarda el estilo de un video como preset")
    s.add_argument("id")
    s.add_argument("nombre")
    s.add_argument("--cuando", help="cuándo usar este preset (lo lee el director)")
    s.add_argument("--forzar", action="store_true")

    s = cmd("ojos", c_ojos, "describe un video con el modelo de visión (Gemini)")
    s.add_argument("ruta")
    s.add_argument("--prompt", default="referencia")
    s.add_argument("--forzar", action="store_true")

    cmd("contacto", c_contacto, "hoja de contactos de cualquier video").add_argument("video")

    s = cmd("limpiar", c_limpiar, "borra caché de videos entregados (--todo: todo el caché)")
    s.add_argument("--todo", action="store_true")

    cmd("presets", c_presets, "lista los presets de estilo")
    cmd("demo", c_demo, "genera material de prueba en material/")
    a = p.parse_args(argv)
    SALIDA_JSON = a.json
    try:
        a.fn(a)
    except ErrorShorts as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
