"""Tests rápidos (sin ffmpeg pesado). Correr con: python3 -m pytest -q"""
from motor.render import _tc, generar_ass
from motor.util import fusionar, hex_a_ass, slug


def test_fusionar_gana_la_capa_de_arriba():
    base = {"subtitulos": {"color": "#FFF", "tamano": 76}, "ritmo": {"plano_min": 0.8}}
    encima = {"subtitulos": {"color": "#FFD400"}}
    res = fusionar(base, encima)
    assert res["subtitulos"] == {"color": "#FFD400", "tamano": 76}
    assert base["subtitulos"]["color"] == "#FFF"  # no muta la base


def test_fusionar_null_borra_valor():
    assert fusionar({"audio": {"musica": "a.wav"}}, {"audio": {"musica": None}})["audio"]["musica"] is None


def test_slug():
    assert slug("Lanzamiento Ñandú 2026!") == "lanzamiento-nandu-2026"


def test_color_ass():
    assert hex_a_ass("#FFD400") == "&H0000D4FF"          # opaco
    assert hex_a_ass("#000000CC") == "&H33000000"        # 80 % opaco


def test_timecode_ass():
    assert _tc(0) == "0:00:00.00"
    assert _tc(61.256) == "0:01:01.26"


def test_ass_ignora_notas_y_resalta():
    estilo = {
        "formato": {"ancho": 1080, "alto": 1920},
        "subtitulos": {"fuente": "Inter", "tamano": 76, "color": "#FFFFFF", "borde": 4,
                       "posicion_y": 0.72, "color_resaltado": "#FFD400"},
        "titulo": {"tamano": 84, "color": "#FFFFFF", "posicion_y": 0.16},
    }
    ass = generar_ass([
        {"texto": "hola *mundo*", "inicio": 0, "fin": 1},
        {"texto": "solo para humanos", "inicio": 0, "fin": 1, "tipo": "nota"},
    ], estilo)
    assert "{\\c&H00D4FF&}mundo{\\r}" in ass
    assert "solo para humanos" not in ass
