Eres un editor de video profesional. Analiza este video vertical (imagen y audio) y describe su ESTILO de edición, no su contenido. Devuelve SOLO JSON válido con esta forma:

{
  "subtitulos": {
    "hay": true,
    "color": "#RRGGBB",
    "color_resaltado": "#RRGGBB o null",
    "mayusculas": true,
    "palabras_por_linea": 3,
    "posicion_y": 0.70,
    "tamano_relativo": "pequeño | medio | grande",
    "animacion": "ninguna | pop | palabra-por-palabra | otra"
  },
  "titulo": {"hay": true, "posicion_y": 0.15, "mayusculas": true, "con_fondo": true},
  "ritmo": {
    "descripcion": "una frase",
    "cortes_al_beat": false,
    "jump_cuts": true
  },
  "encuadre": {"zoom": "normal | cerrado", "punch_in": true, "movimiento": "fijo | zoom-lento | sacudidas"},
  "transiciones": ["corte seco"],
  "musica": {"hay": true, "genero": "...", "energia": "baja | media | alta", "volumen": "fondo | protagonista"},
  "voz": {"hay": true, "personas": 1},
  "hook": "qué pasa en los primeros 3 segundos, en una frase",
  "estructura": [
    {"desde": "00:00", "hasta": "00:03", "que_pasa": "..."}
  ]
}

Reglas:
- posicion_y es la fracción del alto de la pantalla (0 = arriba, 1 = abajo) donde está la línea de base del texto.
- Los colores en hexadecimal. Si no estás seguro de un valor, pon null.
- No transcribas el texto del video ni describas personas: solo el estilo.
