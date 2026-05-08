#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimizador de rampa de garaje  (Garage ramp shape optimiser).

Autor: Efren Rodriguez Rodriguez
Web:   https://efrenrodriguezrodriguez.com/

Uso
---
    python3 ramp_optimizer.py
        Sin argumentos -> abre la interfaz grafica (Tkinter).

    python3 ramp_optimizer.py 136 540
    python3 ramp_optimizer.py -d 136 -l 540
        Modo silencioso: hace los calculos y guarda los planos sin GUI.

    python3 ramp_optimizer.py --desnivel 136 --longitud 540 \\
        [--altura-libre 14] [--batalla 269] \\
        [--voladizo-delantero 87] [--voladizo-trasero 0]

Que hace
--------
Dado un desnivel (cm) y una longitud horizontal (cm) entre el suelo
del garaje y la calle, busca la forma optima de la rampa para que un
coche con esos parametros (altura libre, batalla, voladizos) no
roce ni con el bajo entre las ruedas (high-centering) ni con el
paragolpes / faldon delantero.

Optimiza cinco familias de perfiles:
  1. Rampa lineal (referencia).
  2. Dos arcos + tramo recto en el medio.
  3. Tres tramos rectos.
  4. Cuatro tramos rectos.            (busqueda paralela)
  5. Curva suave libre (spline PCHIP). (busqueda paralela)

Para cada familia mide:
  - la peor holgura del bajo entre las ruedas, y
  - la peor holgura del paragolpes delantero,
y maximiza el minimo de ambos.

Salidas
-------
Cada perfil se publica en 3 sistemas de coordenadas distintos para
facilitar la construccion sobre el terreno:

  * Referencia desde el inicio de la rampa  (ramp_blueprint*)
  * Referencia desde el muro / parte superior  (ramp_blueprint_top*)
  * Referencia desde una cuerda recta T -> B  (ramp_blueprint_chord*)

Por cada plano se generan PNG y PDF (vectorial, para ampliarlo sin
pixelacion). Tambien hay CSV con las cotas a marcar sobre el suelo.

Detalles completos en README.md y COMPILAR.md.

Problem
-------
A flat garage floor connects to a flat outside surface through a slope.
The slope has a fixed rise and run (here 136 cm rise over 540 cm run,
about a 25% / 14 deg grade).  A linear ramp at this grade scratches the
car in two places:

  1.  HIGH-CENTERING.  At the top of the slope, where the slope meets
      the upper flat, the road bumps up between the front and rear
      wheels.  If the bump rises above the chord between the wheel
      contact patches by more than the ground clearance, the chassis
      between the axles drags.

  2.  FRONT BUMPER.  At the bottom of the slope, where the lower flat
      meets the rising surface, the front overhang of the car (the
      part hanging out ahead of the front wheels) is over the slope
      while both wheels are still on the flat.  If the slope rises
      faster than the chassis tilts, the bumper drags.

Approach
--------
The slope is built from a *concave-up* circular arc at the bottom, an
optional straight middle section, and a *concave-down* circular arc at
the top, all joined tangentially.  The two free design parameters are

  * theta -- the slope angle of the straight middle section
             (= the angle at which the arcs meet the straight part).
             It is bounded by

                atan(rise/run)  <=  theta  <=  2 * atan(rise/run)

             At the lower bound the design degenerates to a straight
             linear ramp; at the upper bound the straight middle
             vanishes and the two arcs meet at an inflection point.

  * R_top / S -- the fraction of the total arc-radius budget given to
             the top (concave-down) arc.  Once theta is fixed, the sum
             S = R_bottom + R_top is determined by the rise/run, so we
             only choose the split.

For each candidate (theta, R_top/S) the script simulates a car driving
across the profile and computes the worst-case clearance under the
chassis (between wheels and at the overhangs).  It searches the design
space for the profile that maximises the smaller of the two clearances.

Run
---
    python ramp_optimizer.py

Outputs to the current directory:
    ramp_profile.png        plot comparing linear vs optimal ramp
    ramp_offsets.csv        x,y construction offsets for the optimal ramp
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

import numpy as np


# --------------------------------------------------------------------------- #
#  Localization
# --------------------------------------------------------------------------- #
# The application is written in English by default. A Spanish translation is
# available; activate it with one of:
#
#   * the CLI flag  --lang es
#   * the environment variable  RAMP_LANG=es
#   * a marker file  _lang_es.flag  bundled inside the .exe, which is what
#     the compiler does when invoked as  python build_exe.py --spanish

def _detect_initial_language() -> str:
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS",
                              os.path.dirname(os.path.abspath(sys.executable)))
        if os.path.exists(os.path.join(bundle_dir, "_lang_es.flag")):
            return "es"
    env = os.environ.get("RAMP_LANG", "").strip().lower()
    if env in ("en", "es"):
        return env
    return "en"


LANGUAGE = _detect_initial_language()


# Translation dictionary: every user-facing English string keys to its
# Spanish counterpart. Strings not in the dict pass through unchanged.
_TRANSLATIONS_ES: "dict[str, str]" = {
    # Console banner / summary.
    "GARAGE RAMP OPTIMIZER":
        "OPTIMIZADOR DE RAMPA DE GARAJE",
    "Author: Efren Rodriguez Rodriguez":
        "Autor: Efren Rodriguez Rodriguez",
    "Web:   https://efrenrodriguezrodriguez.com/":
        "Web:   https://efrenrodriguezrodriguez.com/",
    "Enter the dimensions of the ramp you want to build.":
        "Introduce las dimensiones de la rampa que quieres construir.",
    "Car data (press Enter to use the defaults for a Seat Leon FR 2025):":
        "Datos del coche (pulsa Enter para usar los valores por defecto del Seat Leon FR 2025):",
    "Total rise between the garage floor and the street (cm)":
        "Desnivel total entre el suelo del garaje y la calle (cm)",
    "Horizontal length of the ramp (cm)":
        "Longitud horizontal de la rampa (cm)",
    "Ground clearance of the lowest underbody point (cm)":
        "Altura libre del bajo del coche (cm)",
    "Wheelbase / distance between axles (cm)":
        "Batalla / distancia entre ejes (cm)",
    "Front overhang (axle to lowest front point, cm)":
        "Voladizo delantero (eje al frontal mas bajo, cm)",
    "Rear overhang (0 if it does not scrape, cm)":
        "Voladizo trasero (0 si no roza, cm)",
    "Ramp:  rise = {rise} cm,  run = {run} cm,  mean grade = {pct:.1f} % ({deg:.2f} degrees)":
        "Rampa: desnivel = {rise} cm,  longitud = {run} cm,  pendiente media = {pct:.1f} % ({deg:.2f} grados)",
    "Car:   ground clearance = {clearance} cm,  wheelbase = {wheelbase} cm,":
        "Coche: altura libre = {clearance} cm,  batalla = {wheelbase} cm,",
    "       front overhang = {fo} cm,  rear overhang = {ro} cm":
        "       voladizo delantero = {fo} cm,  voladizo trasero = {ro} cm",
    "I do not understand that number. Try again.":
        "No se entiende ese numero. Intenta de nuevo.",
    "The value must be greater than {minimum}. Try again.":
        "El valor debe ser mayor que {minimum}. Intenta de nuevo.",
    "Input cancelled.":
        "Entrada cancelada.",

    # Validation / error messages (CLI).
    "ERROR: rise and run must be positive.":
        "ERROR: el desnivel y la longitud deben ser positivos.",
    "WARNING: rise is greater than or equal to run. The mean grade would be >= 100 % (45 degrees or more), which is not realistic for a car.":
        "AVISO: el desnivel es mayor o igual que la longitud. La rampa tendria una pendiente media >= 100 % (45 grados o mas), que no es realista para un coche.",

    # Argparse description / help.
    "Garage ramp profile optimizer. Computes the optimal ramp shape to avoid scraping, using several methods (linear ramp, two arcs + straight, 3 segments, 4 segments and free-form smooth curve).":
        "Optimizador del perfil de una rampa de garaje. Calcula la forma optima para evitar que el coche roce, usando varios metodos (rampa lineal, dos arcos + recta, 3 tramos, 4 tramos y curva suave).",
    "Total rise between the garage floor and the street (cm). Can also be passed as the first positional argument.":
        "Desnivel total entre el suelo del garaje y la calle (cm). Tambien puede pasarse como primer argumento posicional.",
    "Horizontal length of the ramp (cm). Can also be passed as the second positional argument.":
        "Longitud horizontal de la rampa (cm). Tambien puede pasarse como segundo argumento posicional.",
    "Ground clearance of the lowest underbody point on flat ground (cm).":
        "Altura libre del bajo del coche sobre el suelo, en plano (cm).",
    "Distance between the front and rear axles (cm).":
        "Distancia entre el eje delantero y el trasero (cm).",
    "Distance from the front axle to the lowest front edge (bumper / lip, cm).":
        "Distancia desde el eje delantero al borde inferior del frontal (paragolpes / faldon, cm).",
    "Distance from the rear axle to the lowest rear edge (cm). Leave at 0 if the rear bumper sits higher than the underbody.":
        "Distancia desde el eje trasero al borde inferior trasero (cm). Dejar en 0 si el paragolpes trasero queda mas alto que el bajo.",
    "Shortcut: 'ramp_optimizer RISE RUN' is equivalent to -d RISE -l RUN.":
        "Atajo: 'ramp_optimizer DESNIVEL LONGITUD' equivalente a -d DESNIVEL -l LONGITUD.",
    "Output language for the GUI, the console messages and the blueprint plots ('en' = English, 'es' = Spanish). Default: 'en' (or 'es' if compiled with --spanish).":
        "Idioma de la GUI, los mensajes de consola y los planos ('en' = ingles, 'es' = espanol). Por defecto: 'en' (o 'es' si se compilo con --spanish).",

    # Linear / two-arc / three-slope reports (compute_and_save).
    "--- {name} ---":
        "--- {name} ---",
    "Linear ramp (current geometry)":
        "Rampa lineal (geometria actual)",
    "Optimal three-segment ramp (two arcs + straight)":
        "Rampa optima de 3 segmentos (2 arcos + recta)",
    "Optimal three-slope ramp":
        "Rampa optima de 3 tramos rectos",
    "Optimal four-slope ramp":
        "Rampa optima de 4 tramos rectos",
    "Optimal smooth ramp (PCHIP monotone spline)":
        "Rampa suave optima (spline monotono PCHIP)",
    "  worst chassis-between-wheels clearance:    {value}":
        "  peor holgura del bajo (entre ruedas):     {value}",
    "  worst overhang (bumper) clearance:         {value}":
        "  peor holgura del paragolpes (voladizo):   {value}",
    "      occurs at x = {at_x:6.1f} cm  (rear wheel at x = {at_rear:6.1f} cm)":
        "      ocurre en x = {at_x:6.1f} cm (rueda trasera en x = {at_rear:6.1f} cm)",
    "  (SCRATCHES)": "  (ROZA)",
    "  (touching)":  "  (justo)",

    "Searching the design space (two arcs + straight) ...":
        "Buscando en el espacio de diseno (2 arcos + recta) ...",
    "Best parameters:":
        "Mejores parametros:",
    "  theta (max slope of the straight middle)  = {deg:.2f} degrees   (tan = {pct:.1f} %)":
        "  theta (pendiente max. del tramo recto) = {deg:.2f} grados   (tan = {pct:.1f} %)",
    "  R_bottom (lower-arc radius)               = {value:7.1f} cm":
        "  R_inferior (radio del arco inferior)   = {value:7.1f} cm",
    "  R_top    (upper-arc radius)               = {value:7.1f} cm":
        "  R_superior (radio del arco superior)   = {value:7.1f} cm",
    "  Length of the straight middle (along ramp) = {value:7.1f} cm":
        "  Longitud del tramo recto (sobre rampa) = {value:7.1f} cm",
    "Segment endpoints (cm):":
        "Extremos de cada tramo (cm):",
    "  start of bottom arc      : x =   0.0,  y =   0.0":
        "  inicio arco inferior     : x =   0.0,  y =   0.0",
    "  bottom arc -> straight   : x = {x:5.1f},  y = {y:5.1f}":
        "  arco inferior -> recta   : x = {x:5.1f},  y = {y:5.1f}",
    "  straight -> top arc      : x = {x:5.1f},  y = {y:5.1f}":
        "  recta -> arco superior   : x = {x:5.1f},  y = {y:5.1f}",
    "  end of top arc           : x = {x:5.1f},  y = {y:5.1f}":
        "  fin del arco superior    : x = {x:5.1f},  y = {y:5.1f}",

    "Searching the best three-slope profile ...":
        "Buscando el mejor perfil de 3 tramos rectos ...",
    "Best parameters (3 slopes):":
        "Mejores parametros (3 tramos):",
    "  break point 1:  x1 = {x:5.1f} cm,  y1 = {y:5.2f} cm":
        "  punto de quiebre 1:  x1 = {x:5.1f} cm,  y1 = {y:5.2f} cm",
    "  break point 2:  x2 = {x:5.1f} cm,  y2 = {y:5.2f} cm":
        "  punto de quiebre 2:  x2 = {x:5.1f} cm,  y2 = {y:5.2f} cm",
    "  slope 1 (bottom):    {deg:5.2f} degrees ({pct:.1f} %)":
        "  tramo 1 (inferior):  {deg:5.2f} grados ({pct:.1f} %)",
    "  slope 2 (middle):    {deg:5.2f} degrees ({pct:.1f} %)":
        "  tramo 2 (medio):     {deg:5.2f} grados ({pct:.1f} %)",
    "  slope 3 (top):       {deg:5.2f} degrees ({pct:.1f} %)":
        "  tramo 3 (superior):  {deg:5.2f} grados ({pct:.1f} %)",
    "  fillet radius at every kink: {fillet:.0f} cm":
        "  radio de la curva en cada quiebre: {fillet:.0f} cm",

    "Searching in parallel: 4-slope ramp and free-form smooth curve ...":
        "Buscando en paralelo: 4 tramos rectos y curva suave libre ...",
    "Best parameters (4 slopes):":
        "Mejores parametros (4 tramos):",
    "  break point {k}:  x{k} = {x:5.1f} cm,  y{k} = {y:5.2f} cm":
        "  punto de quiebre {k}:  x{k} = {x:5.1f} cm,  y{k} = {y:5.2f} cm",
    "  slope {i}: {deg:5.2f} degrees ({pct:5.1f} %)   length {L:.1f} cm":
        "  tramo {i}: {deg:5.2f} grados ({pct:5.1f} %)   longitud {L:.1f} cm",

    "Best control points of the smooth curve:":
        "Mejores puntos de control de la curva suave:",
    "  {i:>2}  {x:8.1f}  {y:8.2f}  {tag}":
        "  {i:>2}  {x:8.1f}  {y:8.2f}  {tag}",
    "(endpoint)":
        "(extremo)",

    "Comparison summary (worst scrape, in cm; positive = no scrape):":
        "Resumen comparativo (peor roce, en cm; positivo = no roza):",
    "Linear ramp (current)":
        "Rampa lineal actual",
    "Two arcs + straight":
        "Dos arcos + recta",
    "Three slopes":
        "Tres tramos rectos",
    "Four slopes":
        "Cuatro tramos rectos",
    "Free-form smooth curve (PCHIP)":
        "Curva suave libre (PCHIP)",

    # Sensitivity table.
    "The current run length leaves some unavoidable scraping.":
        "Con la longitud actual, no se puede evitar del todo el roce.",
    "Sensitivity if the ramp is lengthened (rise stays at {rise:.0f} cm):":
        "Sensibilidad si se alarga la rampa (desnivel sigue siendo {rise:.0f} cm):",
    "  (chassis = worst between-wheels clearance;":
        "  (bajo     = peor holgura del bajo entre ruedas;",
    "   bumper  = worst front-overhang / bumper clearance;":
        "   paragol. = peor holgura del paragolpes / voladizo;",
    "   worst   = the smaller of the two; positive means no scraping.)":
        "   peor     = el menor de los dos; positivo = no roza.)",

    # Construction key points table.
    "Three-slope key points (mark these on the ground):":
        "Puntos clave de la rampa de 3 tramos (marcar sobre el suelo):",
    "corner":  "esquina",
    "fillet (R={r:.0f} cm)":  "curva (R={r:.0f} cm)",
    "smooth curve (R={r:.0f} cm)":  "curva suave (R={r:.0f} cm)",

    # write_offsets messages.
    "Construction offsets saved to {path}":
        "Cotas de construccion guardadas en {path}",
    "  x = horizontal distance from the start of the ramp":
        "  x = distancia horizontal desde el inicio de la rampa",
    "  y = height above the garage floor":
        "  y = altura sobre el suelo del garaje",

    # Blueprint save messages.
    "Construction blueprint saved to {path} (+ PDF: {pdf})":
        "Plano de construccion guardado en {path} (+ PDF: {pdf})",
    "Construction blueprint (top reference) saved to {path} (+ PDF: {pdf})":
        "Plano de construccion (referencia superior) guardado en {path} (+ PDF: {pdf})",
    "Construction blueprint (cord reference) saved to {path} (+ PDF: {pdf})":
        "Plano de construccion (cuerda) guardado en {path} (+ PDF: {pdf})",
    "Profile comparison plot saved to ramp_profile.png (+ PDF: {pdf})":
        "Grafica de perfiles guardada en ramp_profile.png (+ PDF: {pdf})",
    "Top-reference cord offsets ({label}) saved to {path}":
        "Cotas con referencia a cuerda ({label}) guardadas en {path}",
    "Top-reference offsets ({label}) saved to {path}":
        "Cotas con referencia superior ({label}) guardadas en {path}",
    "Top-reference offsets saved to {path}":
        "Cotas con referencia superior guardadas en {path}",
    "WARNING: PDF '{path}' could not be saved (continuing with the PNG only): {err}":
        "AVISO: no se pudo guardar el PDF '{path}' (continuamos con el PNG): {err}",

    # Sensitivity column headings.
    "    run":  "  long.",
    "chassis":  "    bajo",
    "bumper":   "paragol.",
    "score":    "    peor",

    # Key-points printed table headers.
    "  pt":    "  pt",
    "what":    "que es",
    "x (cm)":  "x (cm)",
    "y (cm)":  "y (cm)",
    "notes":   "notas",

    # Blueprint plot text (top reference, generic chrome).
    "True-scale view - garage on the left, street on the right":
        "Vista a escala real - garaje a la izquierda, calle a la derecha",
    "u (cm)":           "u (cm)",
    "d (cm)":           "d (cm)",
    "Side wall (chalk-line reference: {h:.0f} cm above the street)":
        "Muro lateral (a {h:.0f} cm sobre la calle)",
    "Ramp profile to build":
        "Perfil de la rampa a construir",
    "drop {drop:.1f} cm\nfrom wall to {label}":
        "bajada {drop:.1f} cm\ndesde el muro a {label}",
    "drop {drop:.1f} cm desde el muro al {label}":
        "bajada {drop:.1f} cm desde el muro al {label}",

    # Blueprint chord-reference labels.
    "Straight cord (T -> B) reference":
        "Cuerda recta de referencia (T -> B)",
    "Reference straight cord (length {L:.2f} cm)":
        "Cuerda recta de referencia (longitud {L:.2f} cm)",
    "Reference straight cord":
        "Cuerda recta de referencia",
    "T (street, top)\ns = 0 cm,  p = 0 cm":
        "T (calle / parte alta)\ns = 0 cm,  p = 0 cm",
    "B (garage, bottom)\ns = {L:.1f} cm,  p = 0 cm":
        "B (garaje / parte baja)\ns = {L:.1f} cm,  p = 0 cm",
    "Garage floor (flat)":  "Suelo del garaje (llano)",
    "Street / outside (flat)":  "Calle / exterior (llano)",
    "Side wall - use the chalk-line as reference":
        "Muro lateral (linea de tiza de referencia)",

    # Keypoint names used in tables and on the plots.
    "Start of the ramp (corner)":          "Inicio de la rampa (esquina)",
    "End of the ramp (corner)":            "Fin de la rampa (esquina)",
    "Start of the ramp (by the garage)":
        "Inicio de la rampa (junto al garaje)",
    "End of the ramp (by the street)":
        "Fin de la rampa (junto a la calle)",
    "End of the start fillet":             "Fin de la curva al inicio",
    "Start of fillet before kink 1":       "Inicio de la curva antes del quiebre 1",
    "Kink 1 (theoretical corner)":         "Quiebre 1 (esquina teorica)",
    "End of fillet after kink 1":          "Fin de la curva tras el quiebre 1",
    "Start of fillet before kink 2":       "Inicio de la curva antes del quiebre 2",
    "Kink 2 (theoretical corner)":         "Quiebre 2 (esquina teorica)",
    "End of fillet after kink 2":          "Fin de la curva tras el quiebre 2",
    "Start of fillet at the top":          "Inicio de la curva al final",
    "Kink {i} (corner)":                   "Quiebre {i} (esquina)",

    # Cord-reference blueprint specifics.
    "Reference straight cord (B -> T)":
        "Cuerda recta de referencia (B -> T)",
    "Ramp profile":   "Perfil de la rampa",
    "B (garage)":     "B (garaje)",
    "T (street)":     "T (calle)",
    "True-scale view - garage on the left, street on the right. The dashed line is the reference straight cord.":
        "Vista a escala real - garaje a la izquierda, calle a la derecha. La linea discontinua es la cuerda recta de referencia.",
    "Reference straight cord (length {L:.2f} cm)":
        "Cuerda recta de referencia (longitud {L:.2f} cm)",
    "Curve control points":
        "Puntos de control de la curva",
    "B (garage, bottom)\ns = {L:.1f} cm,  p = 0 cm":
        "B (garaje / parte baja)\ns = {L:.1f} cm,  p = 0 cm",
    "T (street, top)\ns = 0 cm,  p = 0 cm":
        "T (calle / parte alta)\ns = 0 cm,  p = 0 cm",
    "Stretch a tight straight cord between B (garage) and T (street). Total length = {L:.2f} cm.\ns = distance along the cord measured from T toward B.   p = perpendicular distance from the cord.\np > 0  =  profile ABOVE the cord.   p < 0  =  profile BELOW the cord.":
        "Tender una cuerda recta tensa entre B (garaje) y T (calle). Longitud total = {L:.2f} cm.\ns = distancia a lo largo de la cuerda medida desde T hacia B.   p = distancia perpendicular a la cuerda.\np positivo  =  perfil POR ENCIMA de la cuerda.   p negativo  =  perfil POR DEBAJO de la cuerda.",
    "x (cm) - horizontal distance (0 = start of the ramp at the garage)":
        "x (cm) - distancia horizontal (0 = inicio de la rampa en el garaje)",
    "y (cm) - height above the garage floor":
        "y (cm) - altura sobre el suelo del garaje",
    "s (cm)\nalong cord (from T)":
        "s (cm)\nalong cuerda (desde T)",
    "p (cm)\nperpendicular":
        "p (cm)\nperpendicular",
    "type":     "tipo",
    "upper station (at T, by the street)":
        "estacion superior (en T, junto a la calle)",
    "lower station (at B, by the garage)":
        "estacion inferior (en B, junto al garaje)",
    "intermediate station":
        "estacion intermedia",
    "pt":     "pt",
    "what":   "que es",
    "x (cm) original":   "x (cm) original",
    "y (cm) original":   "y (cm) original",
    "Construction blueprint (reference: straight cord T -> B) - {label}  (cord = {L:.2f} cm, rise {rise:.0f} cm, run {run:.0f} cm)":
        "Plano de construccion (referencia: cuerda recta T -> B) - {label}  (cuerda = {L:.2f} cm, desnivel {rise:.0f} cm, longitud {run:.0f} cm)",

    # Comparison plot.
    "Height (cm)":               "Altura (cm)",
    "Horizontal distance (cm)":  "Distancia horizontal (cm)",
    "Rear-wheel position (cm)":  "Posicion de la rueda trasera (cm)",
    "Minimum clearance (cm)\n(negative = scrape)":
        "Holgura minima (cm)\n(negativo = roza)",
    "worst scrape: {worst:+.2f} cm":
        "peor roce: {worst:+.2f} cm",
    "Ramp profile comparison  (rise {rise:.0f} cm, run {run:.0f} cm, ground clearance {clearance:.0f} cm, wheelbase {wheelbase:.0f} cm, front overhang {fo:.0f} cm)":
        "Perfiles de rampa  (desnivel {rise:.0f} cm, longitud {run:.0f} cm, altura libre {clearance:.0f} cm, batalla {wheelbase:.0f} cm, voladizo delantero {fo:.0f} cm)",

    # Blueprint labels passed as the 'label' argument to draw_*.
    "4-slope ramp":      "rampa de 4 tramos rectos",
    "free-form smooth curve (PCHIP)":
        "curva suave libre (PCHIP)",
    "Three-slope ramp":  "rampa de 3 tramos rectos",
    "smooth curve":      "curva suave libre",

    # GUI strings.
    "Garage Ramp Optimizer":
        "Optimizador de Rampa de Garaje",
    "Author: {name}":
        "Autor: {name}",
    "Ramp data":
        "Datos de la rampa",
    "Car data  (defaults: Seat Leon FR 2025)":
        "Datos del coche  (valores por defecto: Seat Leon FR 2025)",
    "Output folder for the blueprints and CSV files":
        "Carpeta donde se guardaran los planos y los CSV",
    "Total rise (garage to street):":
        "Desnivel total (garaje a calle):",
    "Horizontal length of the ramp:":
        "Longitud horizontal de la rampa:",
    "Ground clearance (on flat):":
        "Altura libre del bajo (en plano):",
    "Wheelbase (between axles):":
        "Batalla (distancia entre ejes):",
    "Front overhang (axle to front):":
        "Voladizo delantero (eje a frontal):",
    "Rear overhang (0 if it does not scrape):":
        "Voladizo trasero (0 si no roza):",
    "Browse...":
        "Examinar...",
    "Pick the output folder":
        "Elige la carpeta de salida",
    "Calculate and generate blueprints":
        "Calcular y generar planos",
    "Ready. Enter the data and click Calculate.":
        "Listo. Introduce los datos y pulsa Calcular.",
    "Calculation output":
        "Salida del calculo",
    "Open output folder":
        "Abrir carpeta de resultados",
    "Close":
        "Cerrar",
    "Origin (u=0, d=0)\nUpper corner of the ramp\n(where the street begins).\nMeasure u to the left (toward the garage).\nMeasure d downward.":
        "Origen (u=0, d=0)\nEsquina superior de la rampa\n(donde empieza la calle).\nMedir u hacia la izquierda (al garaje).\nMedir d hacia abajo.",
    "Calculating, please wait (usually 1 to 3 minutes)...":
        "Calculando, espera unos segundos (puede tardar 1-3 minutos)...",
    "Preparing the data and the linear reference ramp...":
        "Preparando los datos y la rampa lineal de referencia...",
    "Elapsed: 0 s   (usually takes between 1 and 3 minutes)":
        "Tiempo transcurrido: 0 s   (suele tardar entre 1 y 3 minutos)",
    "Elapsed: {elapsed}   (usually takes between 1 and 3 minutes)":
        "Tiempo transcurrido: {elapsed}   (suele tardar entre 1 y 3 minutos)",
    "Total time: {total}":
        "Tiempo total: {total}",
    "Done. Blueprints and CSV files generated.":
        "Listo. Planos y CSV generados.",
    "Calculation complete":
        "Calculo completado",
    "Blueprints (PNG and PDF) and CSV files saved to:\n\n{folder}":
        "Los planos (PNG y PDF) y los archivos CSV se han\nguardado en:\n\n{folder}",
    "Error during the calculation.":
        "Error durante el calculo.",
    "Error":
        "Error",
    "Invalid data":
        "Datos invalidos",
    "Rise and run must be greater than 0.":
        "El desnivel y la longitud deben ser mayores que 0.",
    "Ground clearance and wheelbase must be greater than 0.":
        "La altura libre y la batalla deben ser mayores que 0.",
    "'{name}' is empty.":
        "'{name}' esta vacio.",
    "Pick an output folder.":
        "Selecciona una carpeta de salida.",
    "Cannot create the output folder:\n{err}":
        "No se puede crear la carpeta de salida:\n{err}",
    "The folder does not exist.":
        "La carpeta no existe.",
    "Cannot open the folder:\n{err}":
        "No se pudo abrir la carpeta:\n{err}",
    "Extreme grade":
        "Pendiente extrema",
    "Rise ({rise:.0f} cm) is greater than or equal to run ({run:.0f} cm).\nThat is a grade >= 100 % (45 degrees or more), unrealistic for a car.\n\nDo you want to continue anyway?":
        "El desnivel ({rise:.0f} cm) es mayor o igual que la longitud ({run:.0f} cm).\nEso es una pendiente >= 100 % (45 grados o mas), poco realista para un coche.\n\n¿Quieres continuar de todas formas?",

    # Slope-segment yellow-callout labels.
    "Slope 1 (bottom)":       "Tramo 1 (inferior)",
    "Slope 2 (middle)":       "Tramo 2 (medio)",
    "Slope 3 (top)":          "Tramo 3 (superior)",
    "Slope {i}":              "Tramo {i}",
    "Slope 1 (near the garage / bottom)":
        "Tramo 1 (junto al garaje / abajo)",
    "Slope {n} (near the street / top)":
        "Tramo {n} (junto a la calle / arriba)",
    "Slope {n} (middle)":
        "Tramo {n} (medio)",
    "Slope 3 (near the street / top)":
        "Tramo 3 (junto a la calle / arriba)",
    "Slope 2 (middle)":      "Tramo 2 (medio)",
    "Slope 1 (near the garage / bottom)":
        "Tramo 1 (junto al garaje / abajo)",
    "{name}\n{deg:.2f} degrees ({pct:.1f} %)\nlength along plane = {L:.1f} cm":
        "{name}\n{deg:.2f} grados ({pct:.1f} %)\nlongitud sobre el plano = {L:.1f} cm",

    # Header notices in the working drawings.
    "Round every kink with a smooth curve of radius R = {fillet:.0f} cm.   The square markers show where each curve starts and ends.":
        "Redondear cada quiebre con una curva suave de radio R = {fillet:.0f} cm.   Los marcadores cuadrados indican donde empieza y termina cada curva.",
    "Slopes meet directly at the marked points (sharp corners).   No fillet needed.":
        "Las pendientes se unen directamente en los puntos marcados (esquinas vivas).   No hace falta redondear los quiebres.",
    "Round every kink with a smooth curve\nof radius R = {fillet:.0f} cm.\nThe square markers show where each\ncurve starts and ends.":
        "Redondear cada quiebre con una curva\nsuave de radio R = {fillet:.0f} cm.\nLos marcadores cuadrados indican donde\nempieza y termina cada curva.",
    "Slopes meet directly at the marked points\n(sharp corners).\nNo fillet needed.":
        "Las pendientes se unen directamente en los\npuntos marcados (esquinas vivas).\nNo hace falta redondear los quiebres.",

    # Origin arrow.
    "Origin (0, 0)\nMeasure x horizontally\nfrom here.\nMeasure y vertically.":
        "Origen (0, 0)\nMedir x horizontalmente\ndesde aqui.\nMedir y en vertical.",

    # 3-slope original blueprint.
    "True-scale view (1 cm vertical = 1 cm horizontal)":
        "Vista a escala real (1 cm vertical = 1 cm horizontal)",
    "Ramp profile to build":
        "Perfil de la rampa a construir",
    "Working drawing (vertical scale exaggerated for clarity) - use the (x, y) numbers, not the visual proportions":
        "Plano de trabajo (escala vertical aumentada para mayor claridad) - usar los valores (x, y), no las proporciones visuales",
    "Construction blueprint - 3-slope ramp  (rise {rise:.0f} cm, run {run:.0f} cm)":
        "Plano de construccion - rampa de 3 tramos  (desnivel {rise:.0f} cm, longitud {run:.0f} cm)",
    "x  (cm, horizontal - 0 at the start of the ramp)":
        "x  (cm, horizontal - 0 en el inicio de la rampa)",
    "y  (cm, height above the garage floor)":
        "y  (cm, altura sobre el suelo del garaje)",
    "smooth curve (R={r:.0f} cm)":
        "curva suave (R={r:.0f} cm)",

    # Top-reference blueprint chrome.
    "Side wall ({h:.0f} cm above the street)":
        "Muro lateral (a {h:.0f} cm sobre la calle)",
    "u (cm) - distance from the top edge (growing toward the garage)":
        "u (cm) - distancia desde el borde superior (creciendo hacia el garaje)",
    "d (cm) - depth below the top plane":
        "d (cm) - profundidad bajo el plano superior",
    "drop {drop:.1f} cm\nfrom the wall to {label}":
        "bajada {drop:.1f} cm\ndesde el muro hasta {label}",
    "drop {drop:.1f} cm\nfrom wall to {label}":
        "bajada {drop:.1f} cm\ndesde el muro al {label}",
    "start (garage floor)":
        "inicio (suelo del garaje)",
    "end (street)":
        "fin (calle)",
    "u  (cm, distance from the top edge - growing toward the garage, on the left)":
        "u  (cm, distancia desde el borde superior - creciendo hacia el garaje, a la izquierda)",
    "d  (cm, depth below the top plane - negative = above)":
        "d  (cm, profundidad bajo el plano superior - negativo = por encima)",
    "Working drawing - garage on the left, street on the right  (vertical scale exaggerated for clarity)":
        "Plano de trabajo - garaje a la izquierda, calle a la derecha  (escala vertical aumentada para mayor claridad)",
    "Construction blueprint (reference: wall and top plane) - 3-slope ramp  (rise {rise:.0f} cm, run {run:.0f} cm)":
        "Plano de construccion (referencia: muro y plano superior) - rampa de 3 tramos  (desnivel {rise:.0f} cm, longitud {run:.0f} cm)",
    "Construction blueprint (reference: wall and top plane) - {label}  (rise {rise:.0f} cm, run {run:.0f} cm)":
        "Plano de construccion (referencia: muro y plano superior) - {label}  (desnivel {rise:.0f} cm, longitud {run:.0f} cm)",
    "Construction blueprint (reference: wall and top plane) - {label}  (rise {rise:.0f} cm, run {run:.0f} cm, stations every {step:.0f} cm)":
        "Plano de construccion (referencia: muro y plano superior) - {label}  (desnivel {rise:.0f} cm, longitud {run:.0f} cm, estaciones cada {step:.0f} cm)",
    "u (cm)\nto the top edge":
        "u (cm)\nhasta el borde superior",
    "d (cm)\nbelow the top plane":
        "d (cm)\nbajo el plano superior",
    "drop (cm)\nfrom the wall":
        "bajada (cm)\ndesde el muro",
    "drop (cm)":  "bajada (cm)",
    "Working drawing - {label} - garage on the left, street on the right  (vertical scale exaggerated for clarity)":
        "Plano de trabajo - {label} - garaje a la izquierda, calle a la derecha  (escala vertical aumentada para mayor claridad)",

    # Smooth-blueprint specifics.
    "Continuous curve: mark a station every {step:.0f} cm along the wall and measure the indicated drop.":
        "Curva continua: marcar una estacion cada {step:.0f} cm a lo largo del muro y medir la bajada indicada.",
    "Curve control points (informative):":
        "Puntos de control de la curva (informativo):",
    "upper station (by the street)":
        "estacion superior (junto a la calle)",
    "lower station (by the garage)":
        "estacion inferior (junto al garaje)",

    # Side-wall on-image italic label.
    "Side wall (chalk-line reference)":
        "Muro lateral (linea de tiza de referencia)",

    # Profile-name labels used internally / in CSV log lines.
    "smooth":   "suave",
    "4 slopes": "4 tramos",
    "profile":  "perfil",

    # Short field names used in GUI error messages.
    "Rise":              "Desnivel",
    "Run":               "Longitud",
    "Ground clearance":  "Altura libre",
    "Wheelbase":         "Batalla",
    "Front overhang":    "Voladizo delantero",
    "Rear overhang":     "Voladizo trasero",
    "Done. Blueprints and CSV files generated.":
        "Listo. Planos y CSV generados.",

    # GUI stage messages.
    "Optimizing: two arcs + straight...":
        "Optimizando: dos arcos + recta...",
    "Optimizing: three slopes...":
        "Optimizando: tres tramos rectos...",
    "Generating first blueprint (3 slopes)...":
        "Generando primer plano (3 tramos)...",
    "Optimizing in parallel: 4 slopes and free-form smooth (longest step)...":
        "Optimizando en paralelo: 4 tramos y curva suave (paso mas largo)...",
    "4 slopes done. Waiting for the smooth curve...":
        "4 tramos listo. Esperando a la curva suave...",
    "Generating 4-slope blueprints...":
        "Generando planos del perfil de 4 tramos...",
    "Generating smooth-curve blueprints...":
        "Generando planos de la curva suave...",
    "Generating cord-reference blueprints...":
        "Generando planos en sistema cuerda...",
    "Generating top-reference 3-slope blueprint...":
        "Generando plano top-ref del perfil de 3 tramos...",
    "Computing sensitivity to ramp length...":
        "Calculando sensibilidad a la longitud de la rampa...",
    "Done. Blueprints and CSVs generated.":
        "Listo. Planos y CSV generados.",
}


def t(s: str) -> str:
    """Return the localized version of *s*. Identity when LANGUAGE == 'en'
    or when *s* is not in the translation dictionary."""
    if LANGUAGE == "es":
        return _TRANSLATIONS_ES.get(s, s)
    return s

try:
    import matplotlib
    # Backend no interactivo: solo necesitamos guardar figuras a fichero
    # (savefig). 'Agg' funciona desde cualquier hilo, asi que el calculo
    # puede correr en un hilo de trabajo sin que matplotlib quiera abrir
    # una ventana propia (la GUI de Tkinter es independiente). Esto evita
    # el aviso  "Starting a Matplotlib GUI outside of the main thread
    # will likely fail."
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    HAS_PLT = True
except ImportError:
    HAS_PLT = False


def _save_fig(fig, png_path: str, dpi: int = 130) -> str:
    """Save the figure as PNG and (best-effort) a vector PDF next to it.

    The PDF is a vector copy of the same drawing, intended for zooming
    in without pixelation when the worker prints or projects it.

    If the PDF backend is not available (e.g. a stripped-down PyInstaller
    bundle that does not include ``matplotlib.backends.backend_pdf``),
    we skip the PDF silently so the PNG output still goes through.
    Returns the PDF path that was written, or an empty string if PDF
    output was skipped.
    """
    fig.savefig(png_path, dpi=dpi)
    pdf_path = png_path
    if pdf_path.lower().endswith(".png"):
        pdf_path = pdf_path[:-4] + ".pdf"
    else:
        pdf_path = pdf_path + ".pdf"
    try:
        fig.savefig(pdf_path)
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        # Common cause: matplotlib.backends.backend_pdf not bundled in the
        # frozen .exe.  Warn once and continue with the PNG only.
        print(f"AVISO: no se pudo guardar el PDF '{pdf_path}' "
              f"(continuamos con el PNG): {exc}")
        return ""
    return pdf_path

try:
    from scipy.optimize import differential_evolution
    from scipy.interpolate import PchipInterpolator
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


# --------------------------------------------------------------------------- #
#  Inputs (cm).  Edit the numbers in main() to match your situation.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Car:
    """
    Car geometry, all in cm.

    `front_overhang` is the horizontal distance from the front axle to
    the lowest point of the FRONT of the car (front lip / spoiler / valance).
    Set to 0 if your front bumper is appreciably higher than the underbody
    and not at risk of scraping.

    `rear_overhang` is the same for the rear.  In most cars the rear
    bumper sits higher than the underbody and is not at risk, so the
    default is 0.  Increase it if you want to check rear-bumper drag
    when the car climbs out of the garage.
    """
    clearance: float        # underbody-to-ground on flat
    wheelbase: float        # front-axle to rear-axle
    front_overhang: float = 0.0
    rear_overhang: float = 0.0


@dataclass(frozen=True)
class Ramp:
    rise: float  # vertical change of the slope
    run: float   # horizontal length of the slope


# --------------------------------------------------------------------------- #
#  Profile generators
# --------------------------------------------------------------------------- #
def linear_profile(ramp: Ramp, n: int = 2000):
    x = np.linspace(0.0, ramp.run, n)
    y = ramp.rise * x / ramp.run
    return x, y


def three_segment_profile(
    ramp: Ramp, theta: float, r_top_frac: float, n: int = 2000
):
    """
    Bottom concave-up arc + straight middle + top concave-down arc.
    All segments are tangent at their joins.

    Closure:
        S * sin(theta) + L_m * cos(theta) = run
        S * (1 - cos(theta)) + L_m * sin(theta) = rise
    where S = R_bottom + R_top.  Solving for S and L_m:
        S   = (run * sin(theta) - rise * cos(theta)) / (1 - cos(theta))
        L_m = (rise * sin(theta) - run * (1 - cos(theta))) / (1 - cos(theta))
    """
    sin_t, cos_t = math.sin(theta), math.cos(theta)
    omc = 1.0 - cos_t
    if omc < 1e-9:
        return linear_profile(ramp, n)

    sum_r = (ramp.run * sin_t - ramp.rise * cos_t) / omc
    L_m = (ramp.rise * sin_t - ramp.run * omc) / omc
    if sum_r < -1e-6 or L_m < -1e-6:
        raise ValueError(f"theta={math.degrees(theta):.2f} deg out of range")
    sum_r = max(0.0, sum_r)
    L_m = max(0.0, L_m)

    r_top = sum_r * r_top_frac
    r_bot = sum_r - r_top

    # Distribute samples by arc length / segment length.
    arc_b = r_bot * theta
    arc_t = r_top * theta
    total_len = arc_b + L_m + arc_t
    if total_len < 1e-9:
        return linear_profile(ramp, n)
    n_b = max(2, int(round(n * arc_b / total_len)))
    n_m = max(2, int(round(n * L_m / total_len))) if L_m > 1e-6 else 0
    n_t = max(2, n - n_b - n_m)

    # Bottom arc: centre (0, r_bot), tangent horizontal at the start.
    s_b = np.linspace(0.0, theta, n_b)
    x_b = r_bot * np.sin(s_b)
    y_b = r_bot * (1.0 - np.cos(s_b))

    x_b_end = float(x_b[-1])
    y_b_end = float(y_b[-1])

    # Straight middle (skip its first point to avoid duplication).
    if n_m > 0:
        s_m = np.linspace(0.0, L_m, n_m + 1)[1:]
        x_m = x_b_end + s_m * cos_t
        y_m = y_b_end + s_m * sin_t
        x_m_end = float(x_m[-1])
        y_m_end = float(y_m[-1])
    else:
        x_m = np.empty(0)
        y_m = np.empty(0)
        x_m_end = x_b_end
        y_m_end = y_b_end

    # Top arc: centre offset r_top to the right and below the join along
    # the inward normal (sin theta, -cos theta).
    cx = x_m_end + r_top * sin_t
    cy = y_m_end - r_top * cos_t
    a = np.linspace(math.pi / 2 + theta, math.pi / 2, n_t + 1)[1:]
    x_t = cx + r_top * np.cos(a)
    y_t = cy + r_top * np.sin(a)

    x = np.concatenate([x_b, x_m, x_t])
    y = np.concatenate([y_b, y_m, y_t])
    # Snap endpoints to exact target.
    x[0], y[0] = 0.0, 0.0
    x[-1], y[-1] = ramp.run, ramp.rise
    return x, y


# --------------------------------------------------------------------------- #
#  N-slope (piecewise-linear) profile with small smoothing fillets
# --------------------------------------------------------------------------- #
def n_slope_profile(
    ramp: Ramp,
    breakpoints,           # list of (xi, yi) interior break points
    fillet: float = 30.0,
    n: int = 2400,
):
    """
    Piecewise-linear profile through (0, 0), the interior breakpoints,
    and (run, rise), with a circular fillet of the given radius at every
    kink (start, each interior breakpoint, end).
    """
    pts = [(0.0, 0.0)] + [(float(x), float(y)) for x, y in breakpoints] + \
          [(ramp.run, ramp.rise)]

    # Validate monotonicity in x and y.
    for i in range(len(pts) - 1):
        if pts[i + 1][0] <= pts[i][0] + 1e-6:
            raise ValueError(f"x not increasing at index {i}")
        if pts[i + 1][1] < pts[i][1] - 1e-6:
            raise ValueError(f"y not non-decreasing at index {i}")

    pre = (-200.0, 0.0)
    post = (ramp.run + 200.0, ramp.rise)

    def fillet_arc(p_prev, p_corner, p_next, r):
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return [p_corner]
        u1 = v1 / L1
        u2 = v2 / L2
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)
        if phi < 1e-6:
            return [p_corner]
        t = r / math.tan((math.pi - phi) / 2.0)
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return [p_corner]
        a = np.array(p_corner) - u1 * t
        b = np.array(p_corner) + u2 * t
        nrm1 = np.array([-u1[1], u1[0]])
        if np.dot(nrm1, u2) < 0:
            nrm1 = -nrm1
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        c = a + nrm1 * r_eff
        ang_a = math.atan2(a[1] - c[1], a[0] - c[0])
        ang_b = math.atan2(b[1] - c[1], b[0] - c[0])
        d = ang_b - ang_a
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        m = max(8, int(40 * abs(d) / math.pi))
        ts = np.linspace(0.0, 1.0, m)
        ang = ang_a + d * ts
        return [(c[0] + r_eff * math.cos(t_), c[1] + r_eff * math.sin(t_))
                for t_ in ang]

    path = [pts[0]]
    # Fillet at start (between virtual pre and pts[1]).
    path += fillet_arc(pre, pts[0], pts[1], fillet)
    for i in range(1, len(pts) - 1):
        path += [pts[i]]
        path += fillet_arc(pts[i - 1], pts[i], pts[i + 1], fillet)
    path += [pts[-1]]
    # Fillet at end (between pts[-2] and virtual post).
    path += fillet_arc(pts[-2], pts[-1], post, fillet)

    arr = np.array(path)
    order = np.argsort(arr[:, 0])
    arr = arr[order]
    keep = np.concatenate([[True], np.diff(arr[:, 0]) > 1e-6])
    arr = arr[keep]
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.interp(xs, arr[:, 0], arr[:, 1])
    return xs, ys


def search_n_slope(
    ramp: Ramp, car: Car, n_segments: int,
    fillet: float = 30.0,
    de_maxiter: int = 35, de_popsize: int = 12, seed: int = 7,
):
    """
    Differential-evolution search over the (n_segments - 1) interior
    breakpoints of an n-slope profile.  Each breakpoint contributes
    (x, y) coordinates, so 2 * (n_segments - 1) free parameters.
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the n-slope search")

    K = n_segments - 1                        # number of interior breakpoints
    grade = ramp.rise / ramp.run

    # Search bounds: x_i in (0, run), y_i in (0, rise).  We let the
    # objective enforce ordering and monotonicity via a heavy penalty.
    bounds = []
    for k in range(K):
        # Spread initial bounds roughly evenly along the slope to give the
        # optimiser a sensible starting region.
        x_lo = 0.05 * ramp.run + (k / K) * 0.10 * ramp.run
        x_hi = (k + 1) / K * ramp.run + 0.10 * ramp.run
        x_hi = min(x_hi, 0.95 * ramp.run)
        bounds.append((x_lo, x_hi))
    for k in range(K):
        y_lo = 0.05 * ramp.rise + (k / K) * 0.10 * ramp.rise
        y_hi = (k + 1) / K * ramp.rise + 0.10 * ramp.rise
        y_hi = min(y_hi, 0.97 * ramp.rise)
        bounds.append((y_lo, y_hi))

    def unpack(params):
        xs_int = np.asarray(params[:K], dtype=float)
        ys_int = np.asarray(params[K:], dtype=float)
        # Sort both, so the optimiser can never produce out-of-order
        # breakpoints (this is an extra safety net on top of the bounds).
        xs_int = np.sort(xs_int)
        ys_int = np.sort(ys_int)
        # Make sure breakpoints are reasonably spaced apart in x.
        for i in range(1, K):
            if xs_int[i] - xs_int[i - 1] < 30:
                xs_int[i] = xs_int[i - 1] + 30
        # Reject if last x is past the slope, or last y past the top.
        if xs_int[-1] > ramp.run - 30 or ys_int[-1] > ramp.rise - 0.5:
            return None
        return list(zip(xs_int, ys_int))

    def objective(params):
        breaks = unpack(params)
        if breaks is None:
            return 1e3
        try:
            xp, yp = n_slope_profile(ramp, breaks, fillet=fillet, n=600)
        except ValueError:
            return 1e3
        try:
            m = evaluate(xp, yp, car, ramp,
                         n_positions=400, n_chassis=100, pad=300)
        except Exception:
            return 1e3
        score = min(m["chassis_min"], m["overhang_min"])
        return -score

    result = differential_evolution(
        objective, bounds,
        maxiter=de_maxiter, popsize=de_popsize, seed=seed,
        tol=1e-3, mutation=(0.4, 1.2), recombination=0.85,
        polish=True, workers=1, updating="deferred",
    )

    breaks = unpack(result.x)
    if breaks is None:
        raise RuntimeError(f"{n_segments}-slope search failed to converge")
    xp, yp = n_slope_profile(ramp, breaks, fillet=fillet, n=1500)
    m = evaluate(xp, yp, car, ramp, n_positions=3000, n_chassis=400)
    out = dict(
        n_segments=n_segments,
        breaks=breaks,
        fillet=fillet,
        x=xp, y=yp,
        score=min(m["chassis_min"], m["overhang_min"]),
        **m,
    )
    # Slope angles for reporting.
    pts = [(0.0, 0.0)] + list(breaks) + [(ramp.run, ramp.rise)]
    out["segments"] = []
    for i in range(len(pts) - 1):
        xa, ya = pts[i]
        xb, yb = pts[i + 1]
        dx, dy = xb - xa, yb - ya
        out["segments"].append(dict(
            i=i + 1,
            x_a=xa, y_a=ya, x_b=xb, y_b=yb,
            angle_deg=math.degrees(math.atan2(dy, dx)),
            percent=100.0 * dy / dx,
            length=math.hypot(dx, dy),
        ))
    return out


# --------------------------------------------------------------------------- #
#  Free-form smooth profile (monotone cubic spline)
# --------------------------------------------------------------------------- #
def smooth_profile(
    ramp: Ramp,
    interior_x_frac, interior_y_frac,
    n: int = 2400,
):
    """
    Smooth profile defined by K interior control points at fractional
    positions along x in (0, 1) and fractional y in (0, 1).  Endpoints
    are pinned to (0, 0) and (run, rise).  PCHIP gives a monotone cubic
    interpolation (no overshoot, no spurious wiggles).
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the smooth profile")

    xs_int = np.asarray(interior_x_frac, dtype=float) * ramp.run
    ys_int = np.asarray(interior_y_frac, dtype=float) * ramp.rise
    order = np.argsort(xs_int)
    xs_int = xs_int[order]
    ys_int = ys_int[order]
    # Force monotone non-decreasing in y as well.
    ys_int = np.maximum.accumulate(ys_int)

    xs_ctrl = np.concatenate([[0.0], xs_int, [ramp.run]])
    ys_ctrl = np.concatenate([[0.0], ys_int, [ramp.rise]])

    # Deduplicate close-by xs_ctrl entries.
    keep = np.concatenate([[True], np.diff(xs_ctrl) > 1e-6])
    xs_ctrl = xs_ctrl[keep]
    ys_ctrl = ys_ctrl[keep]

    pchip = PchipInterpolator(xs_ctrl, ys_ctrl, extrapolate=False)
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.asarray(pchip(xs))
    # Numerical safety: clamp tiny excursions and force endpoints exact.
    ys = np.maximum.accumulate(ys)
    ys[0] = 0.0
    ys[-1] = ramp.rise
    return xs, ys, xs_ctrl, ys_ctrl


def search_smooth(
    ramp: Ramp, car: Car,
    K: int = 5,                  # number of interior control points
    de_maxiter: int = 50, de_popsize: int = 14, seed: int = 11,
):
    """
    Optimise the K interior control points of a monotone cubic-spline
    profile.  Each control point contributes (x_frac, y_frac) in (0, 1).
    """
    if not HAS_SCIPY:
        raise RuntimeError("scipy is required for the smooth-profile search")

    # Seed the optimiser with a roughly S-shaped start (concave-up bottom,
    # concave-down top), which is what we expect the answer to look like.
    bounds_x = [(k / (K + 1) - 0.5 / (K + 1),
                 k / (K + 1) + 0.5 / (K + 1))
                for k in range(1, K + 1)]
    bounds_y = [(0.001, 0.999) for _ in range(K)]
    bounds = bounds_x + bounds_y

    def objective(params):
        xfs = np.asarray(params[:K])
        yfs = np.asarray(params[K:])
        try:
            xp, yp, _, _ = smooth_profile(ramp, xfs, yfs, n=600)
        except Exception:
            return 1e3
        try:
            m = evaluate(xp, yp, car, ramp,
                         n_positions=400, n_chassis=100, pad=300)
        except Exception:
            return 1e3
        score = min(m["chassis_min"], m["overhang_min"])
        return -score

    result = differential_evolution(
        objective, bounds,
        maxiter=de_maxiter, popsize=de_popsize, seed=seed,
        tol=1e-3, mutation=(0.4, 1.3), recombination=0.85,
        polish=True, workers=1, updating="deferred",
    )

    xfs = np.asarray(result.x[:K])
    yfs = np.asarray(result.x[K:])
    xp, yp, xs_ctrl, ys_ctrl = smooth_profile(ramp, xfs, yfs, n=2400)
    m = evaluate(xp, yp, car, ramp, n_positions=3000, n_chassis=400)
    out = dict(
        K=K,
        xs_ctrl=xs_ctrl, ys_ctrl=ys_ctrl,
        x=xp, y=yp,
        score=min(m["chassis_min"], m["overhang_min"]),
        **m,
    )
    return out


# --------------------------------------------------------------------------- #
#  Three-slope (piecewise-linear) profile with small smoothing fillets
# --------------------------------------------------------------------------- #
def three_slope_profile(
    ramp: Ramp,
    x1: float, y1: float,   # break point between slope 1 and slope 2
    x2: float, y2: float,   # break point between slope 2 and slope 3
    fillet: float = 30.0,   # radius of the small rounding at every kink
    n: int = 2400,
):
    """
    Three straight slopes joined by small circular fillets at every
    kink (start, between slope 1 and 2, between 2 and 3, end).

    Constraints checked:
        0 < x1 < x2 < run
        0 < y1 < y2 < rise
    The slopes increase monotonically; typically the design has a
    gentle bottom slope, a steep middle slope, and a gentle top slope.
    """
    if not (0 < x1 < x2 < ramp.run):
        raise ValueError("require 0 < x1 < x2 < run")
    if not (0 < y1 < y2 < ramp.rise):
        raise ValueError("require 0 < y1 < y2 < rise")

    # Slope angles of the three straight sections.
    a0 = 0.0
    a1 = math.atan2(y1, x1)
    a2 = math.atan2(y2 - y1, x2 - x1)
    a3 = math.atan2(ramp.rise - y2, ramp.run - x2)
    a4 = 0.0

    if not (a1 < a2 and a2 > a3):
        # Not the classic gentle-steep-gentle shape; allow it but warn.
        pass

    pts = [(0.0, 0.0)]

    def fillet_arc(p_prev, p_corner, p_next, r):
        """
        Insert a tangent arc at p_corner that smoothly joins the line
        p_prev->p_corner with the line p_corner->p_next.
        """
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return [p_corner]
        u1 = v1 / L1
        u2 = v2 / L2
        # Half angle between the two tangent directions.
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)          # external angle change
        if phi < 1e-6:
            return [p_corner]
        t = r / math.tan((math.pi - phi) / 2.0)  # tangent offset from corner
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return [p_corner]
        a = np.array(p_corner) - u1 * t   # arc start (on incoming line)
        b = np.array(p_corner) + u2 * t   # arc end   (on outgoing line)
        # Centre is perpendicular to u1 from a, on the inside of the turn.
        # The inside is the side that the outgoing direction turns toward.
        nrm1 = np.array([-u1[1], u1[0]])
        # Pick the normal that points toward u2.
        if np.dot(nrm1, u2) < 0:
            nrm1 = -nrm1
        # Effective radius from geometry (tangent length t, half angle (pi-phi)/2)
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        c = a + nrm1 * r_eff
        # Sweep from a to b around c.
        ang_a = math.atan2(a[1] - c[1], a[0] - c[0])
        ang_b = math.atan2(b[1] - c[1], b[0] - c[0])
        # Take the short way around.
        d = ang_b - ang_a
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        m = max(8, int(40 * abs(d) / math.pi))
        ts = np.linspace(0.0, 1.0, m)
        ang = ang_a + d * ts
        arc = [(c[0] + r_eff * math.cos(t_), c[1] + r_eff * math.sin(t_))
               for t_ in ang]
        return arc

    # We build the path: virtual point well to the left (flat), origin,
    # corner1 = (x1, y1), corner2 = (x2, y2), top = (run, rise), virtual
    # right point well past the top.
    pre = (-200.0, 0.0)
    p0 = (0.0, 0.0)
    p1 = (x1, y1)
    p2 = (x2, y2)
    p3 = (ramp.run, ramp.rise)
    post = (ramp.run + 200.0, ramp.rise)

    path = [p0]
    path += fillet_arc(pre, p0, p1, fillet)
    path += [p1]
    path += fillet_arc(p0, p1, p2, fillet)
    path += [p2]
    path += fillet_arc(p1, p2, p3, fillet)
    path += [p3]
    path += fillet_arc(p2, p3, post, fillet)

    # Sort by x and dedupe.
    arr = np.array(path)
    order = np.argsort(arr[:, 0])
    arr = arr[order]
    keep = np.concatenate([[True], np.diff(arr[:, 0]) > 1e-6])
    arr = arr[keep]
    # Resample uniformly.
    xs = np.linspace(0.0, ramp.run, n)
    ys = np.interp(xs, arr[:, 0], arr[:, 1])
    return xs, ys


def three_slope_keypoints(ramp: Ramp, x1: float, y1: float,
                          x2: float, y2: float, fillet: float):
    """
    Compute the labeled keypoints of the 3-slope profile (kink corners
    and the start/end of each fillet arc), so a worker can mark them
    on the ground.  Returns a list of (label, x, y, kind) tuples in
    increasing x order, where kind is "kink" or "fillet".
    """
    pre = (-200.0, 0.0)
    p0 = (0.0, 0.0)
    p1 = (x1, y1)
    p2 = (x2, y2)
    p3 = (ramp.run, ramp.rise)
    post = (ramp.run + 200.0, ramp.rise)

    def fillet_endpoints(p_prev, p_corner, p_next, r):
        v1 = np.array(p_corner) - np.array(p_prev)
        v2 = np.array(p_next) - np.array(p_corner)
        L1 = float(np.linalg.norm(v1))
        L2 = float(np.linalg.norm(v2))
        if L1 < 1e-9 or L2 < 1e-9:
            return None
        u1 = v1 / L1
        u2 = v2 / L2
        cos_phi = float(np.clip(np.dot(u1, u2), -1.0, 1.0))
        phi = math.acos(cos_phi)
        if phi < 1e-6:
            return None
        t = r / math.tan((math.pi - phi) / 2.0)
        t = min(t, 0.45 * L1, 0.45 * L2)
        if t < 1e-6:
            return None
        a = np.array(p_corner) - u1 * t
        b = np.array(p_corner) + u2 * t
        r_eff = t * math.tan((math.pi - phi) / 2.0)
        return (float(a[0]), float(a[1])), (float(b[0]), float(b[1])), r_eff

    pts = []
    # Esquina en p0 (inicio de la rampa, sobre el suelo del garaje).
    f = fillet_endpoints(pre, p0, p1, fillet)
    pts.append((t("Start of the ramp (corner)"), p0[0], p0[1], "kink", None))
    if f is not None:
        pts.append((t("End of the start fillet"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina entre el tramo 1 y el tramo 2.
    f = fillet_endpoints(p0, p1, p2, fillet)
    if f is not None:
        pts.append((t("Start of fillet before kink 1"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("Kink 1 (theoretical corner)"), p1[0], p1[1], "kink", None))
    if f is not None:
        pts.append((t("End of fillet after kink 1"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina entre el tramo 2 y el tramo 3.
    f = fillet_endpoints(p1, p2, p3, fillet)
    if f is not None:
        pts.append((t("Start of fillet before kink 2"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("Kink 2 (theoretical corner)"), p2[0], p2[1], "kink", None))
    if f is not None:
        pts.append((t("End of fillet after kink 2"), f[1][0], f[1][1], "fillet", f[2]))

    # Esquina superior (final de la rampa sobre la calle).
    f = fillet_endpoints(p2, p3, post, fillet)
    if f is not None:
        pts.append((t("Start of fillet at the top"), f[0][0], f[0][1], "fillet", f[2]))
    pts.append((t("End of the ramp (corner)"), p3[0], p3[1], "kink", None))

    return pts


def search_three_slope(ramp: Ramp, car: Car, n_grid: int = 11,
                       fillet: float = 30.0) -> dict:
    """
    Search the four-parameter space (x1, y1, x2, y2) for the best
    three-slope profile.  Coarse grid + refinement.
    """
    grade = ramp.rise / ramp.run

    def grid_search(x1_lo, x1_hi, y1_lo, y1_hi,
                    x2_lo, x2_hi, y2_lo, y2_hi, n):
        best_local = None
        for x1 in np.linspace(x1_lo, x1_hi, n):
            for x2 in np.linspace(max(x1 + 30, x2_lo), x2_hi, n):
                if x2 <= x1 + 30:
                    continue
                for y1 in np.linspace(y1_lo, y1_hi, n):
                    if y1 / x1 >= grade:    # bottom slope must be gentler than mean
                        continue
                    for y2 in np.linspace(max(y1 + 5, y2_lo), y2_hi, n):
                        if y2 <= y1:
                            continue
                        if (ramp.rise - y2) / (ramp.run - x2) >= grade:
                            continue        # top slope must be gentler than mean
                        try:
                            x, y = three_slope_profile(
                                ramp, x1, y1, x2, y2, fillet=fillet, n=1200
                            )
                        except ValueError:
                            continue
                        m = evaluate(x, y, car, ramp,
                                     n_positions=900, n_chassis=180)
                        sc = min(m["chassis_min"], m["overhang_min"])
                        if best_local is None or sc > best_local["score"]:
                            best_local = dict(
                                x1=x1, y1=y1, x2=x2, y2=y2,
                                fillet=fillet, score=sc, x=x, y=y, **m,
                            )
        return best_local

    # Coarse pass.
    best = grid_search(
        0.10 * ramp.run, 0.45 * ramp.run,
        0.5,             0.30 * ramp.rise,
        0.55 * ramp.run, 0.92 * ramp.run,
        0.55 * ramp.rise, 0.97 * ramp.rise,
        n_grid,
    )
    if best is None:
        raise RuntimeError("three-slope search failed")

    # Refine around the best point.
    dx = ramp.run / n_grid
    dy = ramp.rise / n_grid
    refined = grid_search(
        max(20.0, best["x1"] - dx),  best["x1"] + dx,
        max(0.5,  best["y1"] - dy),  best["y1"] + dy,
        max(best["x1"] + 40, best["x2"] - dx), min(ramp.run - 20.0, best["x2"] + dx),
        max(best["y1"] + 5, best["y2"] - dy), min(ramp.rise - 0.5, best["y2"] + dy),
        max(7, n_grid // 2 + 1),
    )
    if refined and refined["score"] > best["score"]:
        best = refined

    # Final high-resolution evaluation.
    final = evaluate(best["x"], best["y"], car, ramp,
                     n_positions=3000, n_chassis=400)
    best.update(final)
    best["score"] = min(best["chassis_min"], best["overhang_min"])
    # Slope angles for reporting.
    best["slope1_deg"] = math.degrees(math.atan2(best["y1"], best["x1"]))
    best["slope2_deg"] = math.degrees(math.atan2(
        best["y2"] - best["y1"], best["x2"] - best["x1"]
    ))
    best["slope3_deg"] = math.degrees(math.atan2(
        ramp.rise - best["y2"], ramp.run - best["x2"]
    ))
    return best


# --------------------------------------------------------------------------- #
#  Drive simulation
# --------------------------------------------------------------------------- #
def evaluate(x_p, y_p, car: Car, ramp: Ramp, pad: float = 400.0,
             n_positions: int = 1500, n_chassis: int = 250):
    """
    Slide the car along the profile (extended with flat sections before
    and after) and return the worst clearance under the chassis between
    the wheels (high-centering) and under the overhangs (bumpers).
    """
    x_pre = np.linspace(-pad, 0.0, 200, endpoint=False)
    y_pre = np.zeros_like(x_pre)
    x_post = np.linspace(ramp.run, ramp.run + pad, 200)[1:]
    y_post = np.full_like(x_post, ramp.rise)

    x_road = np.concatenate([x_pre, x_p, x_post])
    y_road = np.concatenate([y_pre, y_p, y_post])
    order = np.argsort(x_road)
    x_road, y_road = x_road[order], y_road[order]
    keep = np.concatenate([[True], np.diff(x_road) > 1e-9])
    x_road, y_road = x_road[keep], y_road[keep]

    rear_xs = np.linspace(
        x_road[0] + 1.0, x_road[-1] - car.wheelbase - 1.0, n_positions
    )

    chassis_min = math.inf
    chassis_at = chassis_pos = None
    overhang_min = math.inf
    overhang_at = overhang_pos = None

    for x_rear in rear_xs:
        x_front = x_rear + car.wheelbase
        h_rear = float(np.interp(x_rear, x_road, y_road))
        h_front = float(np.interp(x_front, x_road, y_road))

        x_pts = np.linspace(
            x_rear - car.rear_overhang,
            x_front + car.front_overhang,
            n_chassis,
        )
        t = (x_pts - x_rear) / car.wheelbase
        chassis_y = h_rear + t * (h_front - h_rear) + car.clearance
        road_y = np.interp(x_pts, x_road, y_road)
        clr = chassis_y - road_y

        between = (x_pts >= x_rear) & (x_pts <= x_front)
        if between.any():
            i = int(np.argmin(clr[between]))
            v = float(clr[between][i])
            if v < chassis_min:
                chassis_min = v
                chassis_at = float(x_pts[between][i])
                chassis_pos = float(x_rear)

        out = ~between
        if out.any():
            i = int(np.argmin(clr[out]))
            v = float(clr[out][i])
            if v < overhang_min:
                overhang_min = v
                overhang_at = float(x_pts[out][i])
                overhang_pos = float(x_rear)

    return dict(
        chassis_min=chassis_min,
        chassis_at_x=chassis_at,
        chassis_at_rear=chassis_pos,
        overhang_min=overhang_min,
        overhang_at_x=overhang_at,
        overhang_at_rear=overhang_pos,
    )


# --------------------------------------------------------------------------- #
#  Search the (theta, R_top fraction) design space
# --------------------------------------------------------------------------- #
def search(ramp: Ramp, car: Car, n_theta: int = 25, n_frac: int = 25,
           refine: int = 9, min_r_top: float | None = None):
    theta_lo = math.atan(ramp.rise / ramp.run)        # linear ramp limit
    theta_hi = 2.0 * math.atan(ramp.rise / ramp.run)  # zero straight middle

    # Hard-floor R_top so the crest never collapses to a near-kink.  The
    # high-centering sagitta of a wheelbase-length chord on a circle of
    # radius R is W^2 / (8R); setting R_top >= W^2 / (8C) makes that
    # sagitta no worse than the ground clearance.  We default to that
    # value so the optimiser is forced to produce a genuinely flat crest.
    if min_r_top is None:
        min_r_top = (car.wheelbase ** 2) / (8.0 * car.clearance)

    def coarse_search(t_lo, t_hi, f_lo, f_hi, nt, nf):
        best_local = None
        for theta in np.linspace(t_lo, t_hi, nt):
            for frac in np.linspace(f_lo, f_hi, nf):
                try:
                    x, y = three_segment_profile(ramp, theta, frac, n=1200)
                except ValueError:
                    continue
                # Reject splits where R_top is below the high-centering
                # floor -- they look "good" only because they trade a
                # crest scrape for a mid-slope scrape.
                sin_t, omc = math.sin(theta), 1.0 - math.cos(theta)
                if omc < 1e-9:
                    continue
                sum_r = (ramp.run * sin_t - ramp.rise * math.cos(theta)) / omc
                r_top = sum_r * frac
                if r_top < min_r_top:
                    continue
                m = evaluate(x, y, car, ramp, n_positions=1000, n_chassis=200)
                score = min(m["chassis_min"], m["overhang_min"])
                if best_local is None or score > best_local["score"]:
                    best_local = dict(
                        theta=theta, theta_deg=math.degrees(theta),
                        r_top_frac=frac, score=score, x=x, y=y, **m,
                    )
        return best_local

    # Stage 1: coarse grid.
    best = coarse_search(
        theta_lo + 1e-4, theta_hi - 1e-4, 0.05, 0.98, n_theta, n_frac
    )
    if best is None:
        raise RuntimeError("search failed")

    # Stage 2: refine around the best point.
    dt = (theta_hi - theta_lo) / n_theta
    df = 0.93 / n_frac
    refined = coarse_search(
        max(theta_lo + 1e-4, best["theta"] - dt),
        min(theta_hi - 1e-4, best["theta"] + dt),
        max(0.05, best["r_top_frac"] - df),
        min(0.98, best["r_top_frac"] + df),
        refine, refine,
    )
    if refined and refined["score"] > best["score"]:
        best = refined

    # Recompute geometry numbers for reporting.
    sin_t, cos_t = math.sin(best["theta"]), math.cos(best["theta"])
    omc = 1.0 - cos_t
    sum_r = (ramp.run * sin_t - ramp.rise * cos_t) / omc
    L_m = (ramp.rise * sin_t - ramp.run * omc) / omc
    best["sum_r"] = sum_r
    best["L_m"] = max(0.0, L_m)
    best["r_top"] = sum_r * best["r_top_frac"]
    best["r_bot"] = sum_r - best["r_top"]
    best["x_b_end"] = best["r_bot"] * sin_t
    best["y_b_end"] = best["r_bot"] * omc
    best["x_m_end"] = best["x_b_end"] + best["L_m"] * cos_t
    best["y_m_end"] = best["y_b_end"] + best["L_m"] * sin_t

    # Evaluate at high resolution on the chosen profile.
    final = evaluate(best["x"], best["y"], car, ramp,
                     n_positions=3000, n_chassis=400)
    best.update(final)
    best["score"] = min(best["chassis_min"], best["overhang_min"])
    return best


# --------------------------------------------------------------------------- #
#  Reporting
# --------------------------------------------------------------------------- #
def fmt_clearance(c):
    if c < -0.05:
        note = t("  (SCRATCHES)")
    elif c < 0.05:
        note = t("  (touching)")
    else:
        note = ""
    return f"{c:+7.2f} cm{note}"


def report(name, m):
    print(t("--- {name} ---").format(name=name))
    print(t("  worst chassis-between-wheels clearance:    {value}").format(
        value=fmt_clearance(m["chassis_min"]),
    ))
    if m["chassis_at_x"] is not None:
        print(t("      occurs at x = {at_x:6.1f} cm  "
                "(rear wheel at x = {at_rear:6.1f} cm)").format(
            at_x=m["chassis_at_x"], at_rear=m["chassis_at_rear"],
        ))
    print(t("  worst overhang (bumper) clearance:         {value}").format(
        value=fmt_clearance(m["overhang_min"]),
    ))
    if m["overhang_at_x"] is not None:
        print(t("      occurs at x = {at_x:6.1f} cm  "
                "(rear wheel at x = {at_rear:6.1f} cm)").format(
            at_x=m["overhang_at_x"], at_rear=m["overhang_at_rear"],
        ))
    print()


def draw_three_slope_blueprint_topref(
    ramp: Ramp, best3: dict,
    wall_height_above_top: float = 136.0,
    path: str = "ramp_blueprint_top.png",
):
    """
    Construction drawing of the same 3-slope profile but referenced from
    the TOP of the ramp (the upper flat at the street).

    Coordinate convention used here:
        u = horizontal distance measured BACK from the top of the ramp
            (u = 0 at the top corner, u increases going into the garage).
        d = depth measured straight DOWN from the upper flat
            (d = 0 at the top, d = ramp.rise at the garage floor).

    A flat wall runs along the side of the ramp at constant height
    `wall_height_above_top` above the upper flat (so it is at the same
    physical height as the top of the ramp + that offset).  The drawing
    uses the wall as the visual zero so the worker can chalk-line the
    wall and drop a tape measure straight down to the surface.

    Conversion from the original (x, y) frame:
        u = run - x
        d = rise - y
    """
    if not HAS_PLT:
        return

    x1, y1 = best3["x1"], best3["y1"]
    x2, y2 = best3["x2"], best3["y2"]
    fillet = best3["fillet"]
    keypts_xy = three_slope_keypoints(ramp, x1, y1, x2, y2, fillet)

    # Convert keypoints to (u, d).
    def to_top(pt_x, pt_y):
        return (ramp.run - pt_x, ramp.rise - pt_y)

    keypts_top = []
    for name, xi, yi, kind, r in keypts_xy:
        ui, di = to_top(xi, yi)
        keypts_top.append((name, ui, di, kind, r))

    # Convert the dense profile to (u, d) and reverse so u increases left->right.
    u_prof = ramp.run - best3["x"]
    d_prof = ramp.rise - best3["y"]
    order = np.argsort(u_prof)
    u_prof = u_prof[order]
    d_prof = d_prof[order]

    # The wall is a horizontal line at d = -wall_height_above_top (because
    # we measure d downward from the upper flat, so above the upper flat
    # is negative d).
    d_wall = -wall_height_above_top

    fig = plt.figure(figsize=(20, 17))
    gs = fig.add_gridspec(
        2, 1, left=0.07, right=0.97, top=0.95, bottom=0.30,
        hspace=0.30, height_ratios=[1.0, 4.4],
    )
    ax_true = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[1, 0])

    # The drawing convention now is: GARAGE on the LEFT, STREET on the RIGHT.
    # We keep u = run - x (so u = 0 is at the top corner where the slope
    # meets the street), but we display u INVERTED on the x-axis so that
    # large u (the garage) appears on the left and small u (the street)
    # appears on the right.

    # ---- Vista a escala real --------------------------------------------- #
    # Wall as a thick horizontal line at d = d_wall, spans the whole figure.
    ax_true.plot([-150, ramp.run + 150], [d_wall, d_wall],
                 color="dimgray", linewidth=4.0)
    # Garage floor (lower flat) at d = ramp.rise, drawn to the LEFT
    # (large u, beyond the bottom of the slope).
    ax_true.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
                 "k-", linewidth=2.0)
    # Upper flat (street) at d = 0, drawn to the RIGHT (negative u, beyond
    # the top corner).
    ax_true.plot([-150, 0], [0, 0], "k-", linewidth=2.0)
    # The slope itself.
    ax_true.plot(u_prof, d_prof, "-", color="tab:green", linewidth=2.6)

    # Invert both axes: y because d grows downward (so down is the floor),
    # x because we want garage on the left, street on the right.
    ax_true.invert_yaxis()
    ax_true.invert_xaxis()
    ax_true.set_aspect("equal")
    ax_true.grid(True, alpha=0.4)
    ax_true.set_xlim(ramp.run + 160, -160)         # inverted: large u left
    ax_true.set_ylim(ramp.rise + 35, d_wall - 25)  # inverted: d grows down
    ax_true.set_title(
        t("True-scale view - garage on the left, street on the right"),
        fontsize=11,
    )
    ax_true.set_xlabel(t("u (cm) - distance from the top edge "
                          "(growing toward the garage)"))
    ax_true.set_ylabel(t("d (cm) - depth below the top plane"))

    # ---- Working drawing ------------------------------------------------- #
    # Wall.
    ax.plot([-150, ramp.run + 150], [d_wall, d_wall],
            color="dimgray", linewidth=5.0,
            label=t("Side wall ({h:.0f} cm above the street)").format(
                h=wall_height_above_top,
            ))
    # Hatched fill above the wall to suggest "solid wall above".
    ax.fill_between(
        [-150, ramp.run + 150], d_wall, d_wall - 30,
        facecolor="lightgray", edgecolor="dimgray", hatch="///", alpha=0.7,
    )
    # Garage floor (lower flat) on the LEFT (large u).
    ax.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
            "k-", linewidth=2.5)
    # Street (upper flat) on the RIGHT (u <= 0).
    ax.plot([-150, 0], [0, 0], "k-", linewidth=2.5)
    # The slope.
    ax.plot(u_prof, d_prof, "-", color="tab:green", linewidth=3.0,
            label=t("Ramp profile to build"))

    # Vertical drop indicators from wall to the FIRST and LAST keypoints
    # (the two endpoints of the slope).  The callouts go INTO the empty
    # space between wall and slope.
    n_pts = len(keypts_top)
    first_letter = label_letters_global = "ABCDEFGHIJKLMN"
    for letter_idx, label in [(0, label_letters_global[0]),
                              (n_pts - 1, label_letters_global[n_pts - 1])]:
        name, ui, di, kind, r = keypts_top[letter_idx]
        ax.plot([ui, ui], [d_wall, di], color="gray", linestyle=":",
                linewidth=1.2, alpha=0.85)
        # Mid-line of the dotted measurement, in the empty zone between
        # the wall and the slope.
        mid_d = (d_wall + di) / 2
        # A is at u=540 (visually LEFT, since x is inverted) -> push
        # callout further left in data space (positive offset).  J is at
        # u=0 (visually RIGHT) -> push callout right in data space
        # (negative offset).
        is_first = (letter_idx == 0)
        offset = 60 if is_first else -60
        ha = "left" if is_first else "right"
        ax.annotate(
            t("drop {drop:.1f} cm\nfrom the wall to {label}").format(
                drop=di + wall_height_above_top, label=label,
            ),
            xy=(ui, mid_d),
            xytext=(ui + offset, mid_d),
            ha=ha, va="center", fontsize=10, color="dimgray", fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="gray", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="dimgray",
                            linewidth=1.0, alpha=0.85),
        )

    # Grid: major every 50 cm in u, every 10 cm in d; minor every 10 / 2.
    ax.set_xticks(np.arange(-150, ramp.run + 151, 50))
    ax.set_xticks(np.arange(-150, ramp.run + 151, 10), minor=True)
    ax.set_yticks(np.arange(d_wall, ramp.rise + 41, 10))
    ax.set_yticks(np.arange(d_wall, ramp.rise + 41, 2), minor=True)
    ax.grid(True, which="major", alpha=0.55, linewidth=0.9)
    ax.grid(True, which="minor", alpha=0.18, linewidth=0.5)

    # Label every keypoint.  With fillet = 0 we have just the four corners
    # (A start, B kink 1, C kink 2, D end), so a simple alternating
    # above/below offset is more than enough.  With fillet > 0 we still
    # alternate but use slightly larger offsets so the fillet endpoints
    # (small squares) don't sit on top of the corner labels.
    # NOTE: data x is inverted in the figure (garage on the left = high u,
    # street on the right = low u), so positive slot_dx visually pushes
    # the label to the LEFT and negative slot_dx visually pushes RIGHT.
    # Positive slot_dy is data-down which is visually DOWN as well
    # (because we also invert y).
    label_letters = "ABCDEFGHIJKLMN"
    table_rows = []
    n_pts = len(keypts_top)
    for i, (name, ui, di, kind, r) in enumerate(keypts_top):
        letter = label_letters[i]
        marker = "o" if kind == "kink" else "s"
        size = 110 if kind == "kink" else 80
        face = "tab:green" if kind == "kink" else "white"
        ax.scatter([ui], [di], s=size, marker=marker,
                   facecolor=face, edgecolor="black",
                   linewidth=1.6, zorder=6)

        # Alternate above / below; nudge horizontally for the first and
        # last points so their labels aren't clipped at the figure edge.
        above = (i % 2 == 0)
        slot_dy = -28 if above else 28
        if i == 0:
            slot_dx = 35           # first corner: garage side -> push left
        elif i == n_pts - 1:
            slot_dx = -35          # last corner: street side -> push right
        else:
            slot_dx = 0
        ha = "right" if slot_dx < 0 else ("left" if slot_dx > 0 else "center")
        va = "bottom" if slot_dy < 0 else "top"
        ax.annotate(
            f"{letter}  (u={ui:.1f}, d={di:.1f}) cm",
            xy=(ui, di),
            xytext=(ui + slot_dx, di + slot_dy),
            ha=ha, va=va,
            fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="black", alpha=0.95),
            arrowprops=dict(arrowstyle="-", color="black",
                            linewidth=0.8, alpha=0.7),
        )
        table_rows.append((letter, name, ui, di, kind, r))

    # Slope segments in the (u, d) frame.  Yellow callouts go BELOW each
    # segment midpoint (in the d > 0 direction, which is visually below
    # the line because we invert the y-axis).
    seg_lines = [
        (t("Slope 3 (near the street / top)"),
         to_top(x2, y2), to_top(ramp.run, ramp.rise)),
        (t("Slope 2 (middle)"),
         to_top(x1, y1), to_top(x2, y2)),
        (t("Slope 1 (near the garage / bottom)"),
         to_top(0.0, 0.0), to_top(x1, y1)),
    ]
    for name, (ua, da), (ub, db) in seg_lines:
        du = ub - ua
        dd = db - da
        ang_deg = math.degrees(math.atan2(abs(dd), abs(du)))
        pct = 100.0 * abs(dd) / abs(du)
        L = math.hypot(du, dd)
        mu, md = (ua + ub) / 2, (da + db) / 2
        ax.annotate(
            t("{name}\n{deg:.2f} degrees ({pct:.1f} %)\n"
              "length along plane = {L:.1f} cm").format(
                name=name, deg=ang_deg, pct=pct, L=L,
            ),
            xy=(mu, md), xytext=(mu, md + 28),
            ha="center", va="top", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow",
                      edgecolor="goldenrod", alpha=0.95),
            arrowprops=dict(arrowstyle="-", color="goldenrod",
                            linewidth=0.8, alpha=0.6),
        )

    # Worker-instruction notice.
    if fillet > 0.5:
        msg = t("Round every kink with a smooth curve of radius "
                 "R = {fillet:.0f} cm.   The square markers show where "
                 "each curve starts and ends.").format(fillet=fillet)
    else:
        msg = t("Slopes meet directly at the marked points (sharp "
                 "corners).   No fillet needed.")
    ax.text(
        0.5, 0.98, msg,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="lightcyan",
                  edgecolor="steelblue", alpha=0.95),
    )

    # Surface labels (garage on the LEFT now, street on the RIGHT).
    ax.text(ramp.run + 75, ramp.rise - 4,
            t("Garage floor (flat)"), ha="center", va="bottom",
            fontsize=12, style="italic", fontweight="bold")
    ax.text(-75, -4, t("Street / outside (flat)"),
            ha="center", va="bottom", fontsize=12, style="italic",
            fontweight="bold")
    # Wall label sits ON the wall, on the LEFT half of the figure so it
    # doesn't collide with the radius callout above it.
    ax.text(ramp.run * 0.78, d_wall - 5,
            t("Side wall (chalk-line reference)"),
            ha="center", va="bottom", fontsize=11, style="italic",
            color="dimgray", fontweight="bold")

    # Origin arrow at the TOP corner (u = 0, d = 0).  The origin is on
    # the RIGHT side of the figure (because x is inverted).  Anchor the
    # callout BELOW the street line where there is open space.
    ax.annotate(
        t("Origin (u=0, d=0)\n"
          "Upper corner of the ramp\n"
          "(where the street begins).\n"
          "Measure u to the left (toward the garage).\n"
          "Measure d downward."),
        "Medir d hacia abajo.",
        xy=(0, 0), xytext=(-130, 60),
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                  edgecolor="black", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
    )

    # IMPORTANT: invert both axes so garage is on the left and d grows down.
    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlim(ramp.run + 200, -200)             # inverted: large u left
    ax.set_ylim(ramp.rise + 80, d_wall - 55)      # inverted: d grows downward
    ax.set_xlabel(t("u  (cm, distance from the top edge - growing "
                     "toward the garage, on the left)"),
                  fontsize=12)
    ax.set_ylabel(t("d  (cm, depth below the top plane - "
                     "negative = above)"), fontsize=12)
    ax.set_title(
        t("Working drawing - garage on the left, street on the right  "
          "(vertical scale exaggerated for clarity)"),
        fontsize=11,
    )
    ax.legend(loc="lower left", fontsize=11)

    fig.suptitle(
        t("Construction blueprint (reference: wall and top plane) - "
          "3-slope ramp  (rise {rise:.0f} cm, run {run:.0f} cm)").format(
            rise=ramp.rise, run=ramp.run,
        ),
        fontsize=13, fontweight="bold", y=0.985,
    )

    # Table.
    ax_table = fig.add_axes([0.05, 0.03, 0.92, 0.26])
    ax_table.set_axis_off()
    cell_text = []
    for letter, name, ui, di, kind, r in table_rows:
        kind_str = (t("corner") if kind == "kink"
                    else t("smooth curve (R={r:.0f} cm)").format(r=r))
        # Distance from the wall is wall_height_above_top + d.
        dist_from_wall = wall_height_above_top + di
        cell_text.append([
            letter, name,
            f"{ui:7.1f}", f"{di:7.1f}",
            f"{dist_from_wall:7.1f}",
            kind_str,
        ])
    table = ax_table.table(
        cellText=cell_text,
        colLabels=[
            t("pt"), t("what"),
            t("u (cm)\nto the top edge"),
            t("d (cm)\nbelow the top plane"),
            t("drop (cm)\nfrom the wall"),
            t("type"),
        ],
        loc="center",
        cellLoc="left",
        colLoc="left",
        colWidths=[0.04, 0.34, 0.13, 0.13, 0.12, 0.24],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.9)
    for c in range(6):
        cell = table[(0, c)]
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#e6e6e6")
    for r_idx, (_, _, _, _, kind, _) in enumerate(table_rows, start=1):
        for c in range(6):
            if kind == "kink":
                table[(r_idx, c)].set_facecolor("#eaf6ea")
            else:
                table[(r_idx, c)].set_facecolor("#fff8e0")

    pdf_path = _save_fig(fig, path)
    print(t("Construction blueprint (top reference) saved to {path} "
            "(+ PDF: {pdf})").format(path=path, pdf=pdf_path))


def _draw_topref_chrome(
    fig, ax_true, ax, ramp: Ramp, x_curve, y_curve, color: str,
    wall_height_above_top: float, top_label: str, fillet_msg_extra: str = "",
):
    """
    Draw the common chrome of a top-referenced blueprint: wall, garage
    floor, street, surface labels, origin arrow, axis ticks/limits, and
    the top-of-figure caption.

    Coordinates: u = run - x (0 at top corner, growing into the garage),
    d = rise - y (0 at upper flat, growing downward).  The figure is
    flipped so the GARAGE is on the LEFT and the STREET on the RIGHT.
    """
    d_wall = -wall_height_above_top
    u_prof = ramp.run - x_curve
    d_prof = ramp.rise - y_curve
    order = np.argsort(u_prof)
    u_prof = u_prof[order]
    d_prof = d_prof[order]

    # ---- Vista a escala real -------------------------------------------- #
    ax_true.plot([-150, ramp.run + 150], [d_wall, d_wall],
                 color="dimgray", linewidth=4.0)
    ax_true.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
                 "k-", linewidth=2.0)
    ax_true.plot([-150, 0], [0, 0], "k-", linewidth=2.0)
    ax_true.plot(u_prof, d_prof, "-", color=color, linewidth=2.6)
    ax_true.invert_yaxis()
    ax_true.invert_xaxis()
    ax_true.set_aspect("equal")
    ax_true.grid(True, alpha=0.4)
    ax_true.set_xlim(ramp.run + 160, -160)
    ax_true.set_ylim(ramp.rise + 35, d_wall - 25)
    ax_true.set_title(
        t("True-scale view - garage on the left, street on the right"),
        fontsize=11,
    )
    ax_true.set_xlabel("u (cm)")
    ax_true.set_ylabel("d (cm)")

    # ---- Working drawing ------------------------------------------------- #
    ax.plot([-150, ramp.run + 150], [d_wall, d_wall],
            color="dimgray", linewidth=5.0,
            label=t("Side wall ({h:.0f} cm above the street)").format(
                h=wall_height_above_top,
            ))
    ax.fill_between(
        [-150, ramp.run + 150], d_wall, d_wall - 30,
        facecolor="lightgray", edgecolor="dimgray", hatch="///", alpha=0.7,
    )
    ax.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
            "k-", linewidth=2.5)
    ax.plot([-150, 0], [0, 0], "k-", linewidth=2.5)
    ax.plot(u_prof, d_prof, "-", color=color, linewidth=3.0,
            label=t("Ramp profile to build"))

    # Drop-from-wall callouts at the two endpoints (start of slope at
    # u=run, end of slope at u=0).
    for u_pt, d_pt, tag in [(ramp.run, ramp.rise,
                              t("start (garage floor)")),
                            (0.0, 0.0, t("end (street)"))]:
        ax.plot([u_pt, u_pt], [d_wall, d_pt], color="gray",
                linestyle=":", linewidth=1.2, alpha=0.85)
        is_garage_side = (u_pt == ramp.run)
        offset = 60 if is_garage_side else -60
        ha = "left" if is_garage_side else "right"
        mid_d = (d_wall + d_pt) / 2
        ax.annotate(
            t("drop {drop:.1f} cm\nfrom wall to {label}").format(
                drop=d_pt + wall_height_above_top, label=tag,
            ),
            xy=(u_pt, mid_d),
            xytext=(u_pt + offset, mid_d),
            ha=ha, va="center", fontsize=10, color="dimgray",
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="gray", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="dimgray",
                            linewidth=1.0, alpha=0.85),
        )

    # Header instruction.
    head = t("Slopes meet directly at the marked points (sharp corners). "
              "  No fillet needed.")
    if fillet_msg_extra:
        head = fillet_msg_extra
    ax.text(
        0.5, 0.98, head,
        transform=ax.transAxes, ha="center", va="top",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="lightcyan",
                  edgecolor="steelblue", alpha=0.95),
    )

    # Surface labels.
    ax.text(ramp.run + 75, ramp.rise - 4,
            t("Garage floor (flat)"), ha="center", va="bottom",
            fontsize=12, style="italic", fontweight="bold")
    ax.text(-75, -4, t("Street / outside (flat)"),
            ha="center", va="bottom", fontsize=12, style="italic",
            fontweight="bold")
    ax.text(ramp.run * 0.78, d_wall - 5,
            t("Side wall (chalk-line reference)"),
            ha="center", va="bottom", fontsize=11, style="italic",
            color="dimgray", fontweight="bold")

    # Origin arrow.
    ax.annotate(
        t("Origin (u=0, d=0)\n"
          "Upper corner of the ramp\n"
          "(where the street begins).\n"
          "Measure u to the left (toward the garage).\n"
          "Measure d downward."),
        xy=(0, 0), xytext=(-130, 60),
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                  edgecolor="black", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
    )

    ax.set_xticks(np.arange(-150, ramp.run + 151, 50))
    ax.set_xticks(np.arange(-150, ramp.run + 151, 10), minor=True)
    ax.set_yticks(np.arange(d_wall, ramp.rise + 41, 10))
    ax.set_yticks(np.arange(d_wall, ramp.rise + 41, 2), minor=True)
    ax.grid(True, which="major", alpha=0.55, linewidth=0.9)
    ax.grid(True, which="minor", alpha=0.18, linewidth=0.5)

    ax.invert_xaxis()
    ax.invert_yaxis()
    ax.set_xlim(ramp.run + 200, -200)
    ax.set_ylim(ramp.rise + 80, d_wall - 55)
    ax.set_xlabel(t("u  (cm, distance from the top edge - growing "
                     "toward the garage, on the left)"),
                  fontsize=12)
    ax.set_ylabel(t("d  (cm, depth below the top plane - "
                     "negative = above)"), fontsize=12)
    ax.set_title(
        t("Working drawing - {label} - garage on the left, street on "
          "the right  (vertical scale exaggerated for clarity)").format(
            label=top_label,
        ),
        fontsize=11,
    )
    ax.legend(loc="lower left", fontsize=11)


def _topref_table(fig, table_rows, n_cols: int = 5):
    """Place the measurements table at the bottom of the figure."""
    ax_table = fig.add_axes([0.05, 0.03, 0.92, 0.26])
    ax_table.set_axis_off()
    table = ax_table.table(
        cellText=[row[:n_cols] for row in table_rows[1:]],
        colLabels=table_rows[0][:n_cols],
        loc="center",
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.0, 1.7)
    for c in range(n_cols):
        cell = table[(0, c)]
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#e6e6e6")
    for r_idx, row in enumerate(table_rows[1:], start=1):
        kind = row[-1] if len(row) > n_cols else ""
        for c in range(n_cols):
            if "esquina" in str(kind):
                table[(r_idx, c)].set_facecolor("#eaf6ea")
            else:
                table[(r_idx, c)].set_facecolor("#fff8e0")


def draw_piecewise_blueprint_topref(
    ramp: Ramp,
    breaks,                             # interior breakpoints [(x, y), ...]
    x_curve, y_curve,                   # dense (x, y) profile to draw
    color: str = "tab:purple",
    wall_height_above_top: float = 136.0,
    label: str = "rampa de tramos rectos",
    path: str = "ramp_blueprint_top_piecewise.png",
):
    """
    Top-referenced worker blueprint for any piecewise-linear profile.
    Marks the start corner, every interior breakpoint, and the end
    corner.  Slopes are joined at sharp corners (no fillets).
    """
    if not HAS_PLT:
        return

    # Build the corner list: (label, name, u, d).
    pts_xy = [(0.0, 0.0)] + [(float(bx), float(by)) for bx, by in breaks] \
             + [(ramp.run, ramp.rise)]
    n_pts = len(pts_xy)
    letters = "ABCDEFGHIJKLMN"
    keypts = []
    for i, (xi, yi) in enumerate(pts_xy):
        if i == 0:
            name = t("Start of the ramp (by the garage)")
        elif i == n_pts - 1:
            name = t("End of the ramp (by the street)")
        else:
            name = t("Kink {i} (corner)").format(i=i)
        ui = ramp.run - xi
        di = ramp.rise - yi
        keypts.append((letters[i], name, ui, di))

    fig = plt.figure(figsize=(20, 17))
    gs = fig.add_gridspec(
        2, 1, left=0.07, right=0.97, top=0.95, bottom=0.30,
        hspace=0.30, height_ratios=[1.0, 4.4],
    )
    ax_true = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[1, 0])

    _draw_topref_chrome(
        fig, ax_true, ax, ramp, x_curve, y_curve, color,
        wall_height_above_top, label,
    )

    # Corner labels.
    for i, (letter, name, ui, di) in enumerate(keypts):
        ax.scatter([ui], [di], s=120, marker="o",
                   facecolor=color, edgecolor="black",
                   linewidth=1.6, zorder=6)
        above = (i % 2 == 0)
        slot_dy = -28 if above else 28
        if i == 0:
            slot_dx = 35
        elif i == n_pts - 1:
            slot_dx = -35
        else:
            slot_dx = 0
        ha = "right" if slot_dx < 0 else ("left" if slot_dx > 0 else "center")
        va = "bottom" if slot_dy < 0 else "top"
        ax.annotate(
            f"{letter}  (u={ui:.1f}, d={di:.1f}) cm",
            xy=(ui, di),
            xytext=(ui + slot_dx, di + slot_dy),
            ha=ha, va=va,
            fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                      edgecolor="black", alpha=0.95),
            arrowprops=dict(arrowstyle="-", color="black",
                            linewidth=0.8, alpha=0.7),
        )

    # Yellow segment callouts.  We list segments from street side (top)
    # to garage side (bottom) so the order matches the visual reading
    # direction (right -> left in the inverted-x figure).
    seg_labels = [
        t("Slope {i}").format(i=i + 1) for i in range(n_pts - 1)
    ]
    # Re-label end segments more descriptively.
    seg_labels[0] = t("Slope 1 (near the garage / bottom)")
    seg_labels[-1] = t("Slope {n} (near the street / top)").format(
        n=n_pts - 1,
    )
    if n_pts - 1 >= 4:
        for k in range(1, n_pts - 2):
            seg_labels[k] = t("Slope {n} (middle)").format(n=k + 1)
    for i in range(n_pts - 1):
        xa, ya = pts_xy[i]
        xb, yb = pts_xy[i + 1]
        ua, da = ramp.run - xa, ramp.rise - ya
        ub, db = ramp.run - xb, ramp.rise - yb
        du, dd = ub - ua, db - da
        ang_deg = math.degrees(math.atan2(abs(yb - ya), abs(xb - xa)))
        pct = 100.0 * (yb - ya) / (xb - xa)
        L = math.hypot(xb - xa, yb - ya)
        mu, md = (ua + ub) / 2, (da + db) / 2
        ax.annotate(
            t("{name}\n{deg:.2f} degrees ({pct:.1f} %)\n"
              "length along plane = {L:.1f} cm").format(
                name=seg_labels[i], deg=ang_deg, pct=pct, L=L,
            ),
            xy=(mu, md), xytext=(mu, md + 28),
            ha="center", va="top", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow",
                      edgecolor="goldenrod", alpha=0.95),
            arrowprops=dict(arrowstyle="-", color="goldenrod",
                            linewidth=0.8, alpha=0.6),
        )

    # Table.
    table_rows = [(
        t("pt"), t("what"),
        t("u (cm)\nto the top edge"),
        t("d (cm)\nbelow the top plane"),
        t("drop (cm)\nfrom the wall"),
        t("type"),
    )]
    for letter, name, ui, di in keypts:
        bajada = wall_height_above_top + di
        table_rows.append((
            letter, name,
            f"{ui:7.1f}", f"{di:7.1f}", f"{bajada:7.1f}",
            t("corner"),
        ))
    _topref_table(fig, table_rows, n_cols=6)

    fig.suptitle(
        t("Construction blueprint (reference: wall and top plane) - "
          "{label}  (rise {rise:.0f} cm, run {run:.0f} cm)").format(
            label=label, rise=ramp.rise, run=ramp.run,
        ),
        fontsize=13, fontweight="bold", y=0.985,
    )
    pdf_path = _save_fig(fig, path)
    print(t("Construction blueprint saved to {path} (+ PDF: {pdf})"
            ).format(path=path, pdf=pdf_path))


def draw_smooth_blueprint_topref(
    ramp: Ramp,
    x_curve, y_curve,                   # dense profile to draw
    ctrl_x, ctrl_y,                     # control points used by the spline
    color: str = "tab:orange",
    wall_height_above_top: float = 136.0,
    station_step_cm: float = 30.0,
    label: str = "free-form smooth curve",
    path: str = "ramp_blueprint_top_smooth.png",
):
    """
    Top-referenced worker blueprint for the smooth (PCHIP) profile.
    Instead of corner labels, marks measurement stations every
    `station_step_cm` along the slope (from the upper edge), so the
    worker can lay out the curve by tape-measuring at regular intervals
    along the wall.  The original control points are drawn as small
    diamonds for context.
    """
    if not HAS_PLT:
        return

    # Stations: every station_step_cm along the slope's run, indexed from
    # the TOP (u = 0), increasing into the garage.
    n_stations = int(math.floor(ramp.run / station_step_cm)) + 1
    us = np.arange(n_stations + 1, dtype=float) * station_step_cm
    us = np.clip(us, 0.0, ramp.run)
    # Make sure we always include u = run exactly.
    us = np.unique(np.concatenate([us, [ramp.run]]))
    # Convert u -> x, then look up y, then convert y -> d.
    xs_st = ramp.run - us
    ys_st = np.interp(xs_st, x_curve, y_curve)
    ds_st = ramp.rise - ys_st

    fig = plt.figure(figsize=(22, 17))
    gs = fig.add_gridspec(
        2, 1, left=0.06, right=0.98, top=0.95, bottom=0.30,
        hspace=0.30, height_ratios=[1.0, 4.4],
    )
    ax_true = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[1, 0])

    head = t(
        "Continuous curve: mark a station every {step:.0f} cm along the "
        "wall and measure the indicated drop."
    ).format(step=station_step_cm)
    _draw_topref_chrome(
        fig, ax_true, ax, ramp, x_curve, y_curve, color,
        wall_height_above_top, label, fillet_msg_extra=head,
    )

    # Draw control points as small diamonds for reference.
    ctrl_u = ramp.run - np.asarray(ctrl_x)
    ctrl_d = ramp.rise - np.asarray(ctrl_y)
    ax.scatter(ctrl_u, ctrl_d, s=80, marker="D",
               facecolor="white", edgecolor=color, linewidth=1.4,
               zorder=5, label=t("Curve control points"))

    # Stations: dotted vertical line from wall, dot on the surface, and
    # a small label with the station number.
    table_rows = [(
        "n", "u (cm)",
        "d (cm)", t("drop (cm)"), t("type"),
    )]
    for n, (ui, di) in enumerate(zip(us, ds_st), start=1):
        ax.plot([ui, ui], [-wall_height_above_top, di],
                color="lightgray", linestyle=":", linewidth=0.8, alpha=0.7)
        ax.scatter([ui], [di], s=70, marker="o",
                   facecolor=color, edgecolor="black",
                   linewidth=1.0, zorder=6)
        # Alternate label above/below.
        above = (n % 2 == 1)
        slot_dy = -22 if above else 22
        ha = "center"
        va = "bottom" if above else "top"
        ax.annotate(
            f"{n}\n({ui:.0f}, {di:.1f})",
            xy=(ui, di),
            xytext=(ui, di + slot_dy),
            ha=ha, va=va, fontsize=8, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.18", facecolor="white",
                      edgecolor="black", alpha=0.9),
            arrowprops=dict(arrowstyle="-", color="black",
                            linewidth=0.6, alpha=0.5),
        )
        bajada = wall_height_above_top + di
        if n == 1:
            kind = t("upper station (by the street)")
        elif n == len(us):
            kind = t("lower station (by the garage)")
        else:
            kind = t("intermediate station")
        table_rows.append((
            f"{n}", f"{ui:7.1f}",
            f"{di:7.1f}", f"{bajada:7.1f}", kind,
        ))

    # Add control-point coordinates as a small note in the corner.
    ctrl_lines = [t("Curve control points (informative):")]
    for i, (ux, dy) in enumerate(zip(ctrl_u, ctrl_d)):
        ctrl_lines.append(
            f"  cp{i+1}:  u = {ux:6.1f} cm   d = {dy:6.1f} cm"
        )
    ax.text(
        0.985, 0.02,
        "\n".join(ctrl_lines),
        transform=ax.transAxes, ha="right", va="bottom",
        fontsize=9, family="monospace",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                  edgecolor=color, alpha=0.95),
    )

    ax.legend(loc="lower left", fontsize=11)

    # Table at the bottom.
    _topref_table(fig, table_rows, n_cols=5)

    fig.suptitle(
        t("Construction blueprint (reference: wall and top plane) - "
          "{label}  (rise {rise:.0f} cm, run {run:.0f} cm, "
          "stations every {step:.0f} cm)").format(
            label=label, rise=ramp.rise, run=ramp.run,
            step=station_step_cm,
        ),
        fontsize=13, fontweight="bold", y=0.985,
    )
    pdf_path = _save_fig(fig, path)
    print(t("Construction blueprint saved to {path} (+ PDF: {pdf})"
            ).format(path=path, pdf=pdf_path))


def chord_coords(ramp: Ramp, x_arr, y_arr):
    """
    Project (x, y) -> (s, p) using the straight chord between
    T = (run, rise) (the upper corner, junto a la calle) and
    B = (0, 0) (the lower corner, junto al garaje) as the reference.

    s = distance along the chord measured from T toward B
        (so s = 0 at T and s = L = sqrt(run^2 + rise^2) at B).
    p = signed perpendicular distance from the chord, with the
        convention requested by the user:
            p > 0  ->  the surface is ABOVE the chord
                       (i.e., on the up-left side of the cord)
            p < 0  ->  the surface is BELOW the chord
                       (the natural "sag" side of an optimised ramp)
    """
    L = math.hypot(ramp.run, ramp.rise)
    x_arr = np.asarray(x_arr, dtype=float)
    y_arr = np.asarray(y_arr, dtype=float)
    s = (ramp.run * (ramp.run - x_arr)
         + ramp.rise * (ramp.rise - y_arr)) / L
    p = (ramp.run * y_arr - ramp.rise * x_arr) / L
    return s, p


def draw_chord_blueprint(
    ramp: Ramp,
    x_curve, y_curve,
    label: str,
    color: str,
    breaks=None,                       # piecewise: list of (x, y)
    ctrl_x=None, ctrl_y=None,           # smooth: control points (informational)
    station_step_cm: float = 30.0,
    path: str = "ramp_blueprint_chord.png",
):
    """
    Top-referenced worker blueprint that uses a STRAIGHT CORD from T
    (street, parte alta) to B (garage, parte baja) as the only reference.

    For each marked point the worker reads:
        s = how far to slide along the cord, starting at T
        p = how far to measure PERPENDICULAR to the cord
            (positive = surface is on the cord's lower side)

    Two flavours:
      * piecewise (breaks given): mark the corners only.
      * smooth (breaks = None): mark stations every station_step_cm
        along the cord plus the spline control points.
    """
    if not HAS_PLT:
        return

    L_total = math.hypot(ramp.run, ramp.rise)
    profile_s, profile_p = chord_coords(ramp, x_curve, y_curve)
    order = np.argsort(profile_s)
    profile_s = profile_s[order]
    profile_p = profile_p[order]

    is_smooth = breaks is None

    keypts = []
    if is_smooth:
        # Stations at multiples of station_step_cm, plus s=0 and s=L_total.
        n = int(math.floor(L_total / station_step_cm)) + 2
        ss = np.arange(n + 1, dtype=float) * station_step_cm
        ss = ss[ss <= L_total - 0.5]
        ss = np.unique(np.concatenate([[0.0], ss, [L_total]]))
        ps = np.interp(ss, profile_s, profile_p)
        for i, (s, p) in enumerate(zip(ss, ps), start=1):
            keypts.append(dict(label=str(i), name="estacion",
                               s=float(s), p=float(p)))
    else:
        pts = [(0.0, 0.0)] + [(float(bx), float(by)) for bx, by in breaks] \
              + [(ramp.run, ramp.rise)]
        ss_pts, ps_pts = chord_coords(
            ramp,
            np.array([p[0] for p in pts]),
            np.array([p[1] for p in pts]),
        )
        # Sort by s ascending (top -> bottom along the cord).
        idx_sorted = sorted(range(len(pts)), key=lambda j: ss_pts[j])
        n_pts = len(pts)
        letters = "ABCDEFGHIJKL"
        for new_i, idx in enumerate(idx_sorted):
            xo, yo = pts[idx]
            if idx == 0:
                name = t("Start of the ramp (by the garage)")
            elif idx == n_pts - 1:
                name = t("End of the ramp (by the street)")
            else:
                name = t("Kink {i} (corner)").format(i=idx)
            keypts.append(dict(
                label=letters[new_i], name=name,
                s=float(ss_pts[idx]), p=float(ps_pts[idx]),
                x=xo, y=yo,
            ))

    # Ensure each keypoint has its (x, y) on the actual surface so we can
    # plot the perpendicular drop from the chord to the surface point.
    # Convention: p > 0 -> ABOVE the chord -> surface = foot + p * (-rise, run)/L
    for kp in keypts:
        if kp.get("x") is None:
            s_, p_ = kp["s"], kp["p"]
            kp["x"] = (ramp.run - s_ * ramp.run / L_total
                       - p_ * ramp.rise / L_total)
            kp["y"] = (ramp.rise - s_ * ramp.rise / L_total
                       + p_ * ramp.run / L_total)

    # ---------------------------------------------------------------- Figure
    # Layout: small true-scale overview on top, large EQUAL-ASPECT working
    # drawing in the middle (so the cord appears at its real angle and
    # perpendicular drops are visually perpendicular to the cord), then a
    # measurements table well below the plot.
    fig = plt.figure(figsize=(26, 19))
    gs = fig.add_gridspec(
        2, 1, left=0.05, right=0.98, top=0.94, bottom=0.42,
        hspace=0.30, height_ratios=[1.0, 3.6],
    )
    ax_true = fig.add_subplot(gs[0, 0])
    ax = fig.add_subplot(gs[1, 0])

    # ---- Top: true-scale overview (garage on the left, street on right) - #
    ax_true.plot([-150, 0], [0, 0], "k-", linewidth=2.0)
    ax_true.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
                 "k-", linewidth=2.0)
    ax_true.plot([0, ramp.run], [0, ramp.rise], "--", color="gray",
                 linewidth=2.2,
                 label=t("Reference straight cord (B -> T)"))
    ax_true.plot(x_curve, y_curve, "-", color=color, linewidth=2.5,
                 label=t("Ramp profile"))
    ax_true.scatter([0, ramp.run], [0, ramp.rise], s=160, marker="*",
                    facecolor="yellow", edgecolor="black", linewidth=1.4,
                    zorder=6)
    ax_true.text(0, -10, t("B (garage)"),
                 ha="center", va="top", fontsize=10, fontweight="bold")
    ax_true.text(ramp.run, ramp.rise + 12, t("T (street)"),
                 ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax_true.set_aspect("equal")
    ax_true.grid(True, alpha=0.4)
    ax_true.set_xlim(-160, ramp.run + 160)
    ax_true.set_ylim(-25, ramp.rise + 35)
    ax_true.set_title(
        t("True-scale view - garage on the left, street on the right. "
          "The dashed line is the reference straight cord."),
        fontsize=11,
    )
    ax_true.set_xlabel("x (cm)")
    ax_true.set_ylabel("y (cm)")
    ax_true.legend(loc="upper left", fontsize=10)

    # ---- Main: equal-aspect working drawing with diagonal cord -------- #
    # Surfaces: street + garage flats.
    ax.plot([-200, 0], [0, 0], "k-", linewidth=2.5)
    ax.plot([ramp.run, ramp.run + 200], [ramp.rise, ramp.rise],
            "k-", linewidth=2.5)
    # Diagonal cord from B to T.
    ax.plot([0, ramp.run], [0, ramp.rise], "--", color="gray", linewidth=3.0,
            label=t("Reference straight cord (length {L:.2f} cm)"
                     ).format(L=L_total))
    # Profile.
    ax.plot(x_curve, y_curve, "-", color=color, linewidth=3.0,
            label=t("Ramp profile"))

    # Optional: spline control points for smooth case (informational).
    if is_smooth and ctrl_x is not None:
        ax.scatter(np.asarray(ctrl_x), np.asarray(ctrl_y),
                   s=80, marker="D", facecolor="white",
                   edgecolor=color, linewidth=1.3, zorder=5,
                   label=t("Curve control points"))

    # Mark T and B with stars.
    ax.scatter([0, ramp.run], [0, ramp.rise], s=240, marker="*",
               facecolor="yellow", edgecolor="black",
               linewidth=1.5, zorder=7)
    # Yellow callouts for B and T live in the EMPTY side-margin areas of
    # the figure (well beyond the slope itself), so they cannot collide
    # with the cord, the profile, or any keypoint label.  Arrows reach
    # back to the corner stars.
    ax.annotate(
        t("B (garage, bottom)\ns = {L:.1f} cm,  p = 0 cm").format(L=L_total),
        xy=(0, 0), xytext=(-180, 95),
        ha="center", va="bottom",
        fontsize=12, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow",
                  edgecolor="goldenrod", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
    )
    ax.annotate(
        t("T (street, top)\ns = 0 cm,  p = 0 cm"),
        xy=(ramp.run, ramp.rise), xytext=(ramp.run + 180, ramp.rise - 95),
        ha="center", va="top",
        fontsize=12, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow",
                  edgecolor="goldenrod", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
    )

    # Surface labels stay above / below their respective flats, well clear
    # of the yellow callouts which are now far out in the side margins.
    ax.text(-75, -8, t("Garage floor (flat)"),
            ha="center", va="top", fontsize=12, style="italic",
            fontweight="bold")
    ax.text(ramp.run + 75, ramp.rise + 8, t("Street / outside (flat)"),
            ha="center", va="bottom", fontsize=12, style="italic",
            fontweight="bold")

    # Perpendicular drops + labels for each interior keypoint (skip the two
    # endpoints, which are on the chord).
    for i, kp in enumerate(keypts):
        x_p, y_p = kp["x"], kp["y"]
        s_, p_ = kp["s"], kp["p"]
        # Foot of perpendicular on the chord (at distance s from T).
        foot_x = ramp.run - s_ * ramp.run / L_total
        foot_y = ramp.rise - s_ * ramp.rise / L_total

        is_endpoint = abs(p_) < 0.5 and (
            abs(s_) < 0.5 or abs(s_ - L_total) < 0.5
        )

        if not is_endpoint:
            # Perpendicular from foot to surface point (at the true
            # geometric angle since we use equal aspect).
            ax.plot([foot_x, x_p], [foot_y, y_p],
                    color="gray", linestyle=":", linewidth=1.4, alpha=0.85)
            # Foot mark (small open circle on the chord).
            ax.scatter([foot_x], [foot_y], s=40, marker="o",
                       facecolor="white", edgecolor="gray",
                       linewidth=1.0, zorder=5)
            # Surface point mark.
            ax.scatter([x_p], [y_p],
                       s=130 if not is_smooth else 65, marker="o",
                       facecolor=color, edgecolor="black",
                       linewidth=1.4, zorder=6)

            # Place the label further along the perpendicular extension
            # (away from the chord), so it doesn't sit on top of the cord.
            # Normal direction for p > 0 (above-left side) is (-rise, run)/L.
            sign = 1.0 if p_ > 0 else -1.0
            nx = -ramp.rise / L_total * sign
            ny = ramp.run / L_total * sign
            offset_dist = 30.0 if not is_smooth else 20.0
            label_x = x_p + nx * offset_dist
            label_y = y_p + ny * offset_dist

            if is_smooth:
                txt = f"{kp['label']}\ns={s_:.0f}\np={p_:+.1f}"
                font = 8
            else:
                txt = (f"{kp['label']}  s = {s_:.1f} cm  p = {p_:+.1f} cm\n"
                       f"(x = {x_p:.1f}, y = {y_p:.1f}) cm")
                font = 10
            ax.annotate(
                txt,
                xy=(x_p, y_p),
                xytext=(label_x, label_y),
                ha="center", va="center", fontsize=font, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", facecolor="white",
                          edgecolor="black", alpha=0.95),
                arrowprops=dict(arrowstyle="-", color="black",
                                linewidth=0.7, alpha=0.6),
            )

    # Header note (placed inside the axes, top-center, so it does not
    # collide with the figure title or the axis title above).
    head = t(
        "Stretch a tight straight cord between B (garage) and T "
        "(street). Total length = {L:.2f} cm.\n"
        "s = distance along the cord measured from T toward B.   "
        "p = perpendicular distance from the cord.\n"
        "p > 0  =  profile ABOVE the cord.   "
        "p < 0  =  profile BELOW the cord."
    ).format(L=L_total)
    ax.text(
        0.5, 0.985, head, transform=ax.transAxes,
        ha="center", va="top",
        fontsize=10, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="lightcyan",
                  edgecolor="steelblue", alpha=0.95),
    )

    # Equal aspect, no axis inversion (garage on left, street on right).
    ax.set_aspect("equal")
    ax.set_xlim(-260, ramp.run + 260)
    ax.set_ylim(-90, ramp.rise + 110)
    ax.set_xlabel(t("x (cm) - horizontal distance (0 = start of the "
                     "ramp at the garage)"), fontsize=12)
    ax.set_ylabel(t("y (cm) - height above the garage floor"), fontsize=12)
    ax.grid(True, which="major", alpha=0.45)
    ax.set_xticks(np.arange(-250, ramp.run + 251, 50))
    ax.set_yticks(np.arange(-80, ramp.rise + 101, 20))
    ax.legend(loc="lower right", fontsize=11)
    # No subtitle here -- the header note above and the figure suptitle are
    # enough; an extra title would just overlap the header note box.

    # Bottom: measurements table, placed well below the working drawing
    # (the gridspec ends at y=0.42, so the table fits in the lower 36%
    # of the figure without overlapping the plot area).
    ax_table = fig.add_axes([0.05, 0.02, 0.92, 0.36])
    ax_table.set_axis_off()
    if is_smooth:
        col_labels = [
            "n",
            t("s (cm)\nalong cord (from T)"),
            t("p (cm)\nperpendicular"),
            t("type"),
        ]
        rows = []
        n_kp_local = len(keypts)
        for i, kp in enumerate(keypts):
            if i == 0:
                kind = t("upper station (at T, by the street)")
            elif i == n_kp_local - 1:
                kind = t("lower station (at B, by the garage)")
            else:
                kind = t("intermediate station")
            rows.append((kp["label"], f"{kp['s']:7.1f}",
                         f"{kp['p']:+7.1f}", kind))
    else:
        col_labels = [
            t("pt"), t("what"),
            t("s (cm)\nalong cord (from T)"),
            t("p (cm)\nperpendicular"),
            t("x (cm) original"), t("y (cm) original"),
        ]
        rows = []
        for kp in keypts:
            rows.append((
                kp["label"], kp["name"],
                f"{kp['s']:7.1f}", f"{kp['p']:+7.1f}",
                f"{kp['x']:7.1f}", f"{kp['y']:7.1f}",
            ))

    table = ax_table.table(
        cellText=rows, colLabels=col_labels,
        loc="center", cellLoc="left", colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(12 if not is_smooth else 10)
    table.scale(1.0, 1.9 if not is_smooth else 1.5)
    n_cols = len(col_labels)
    for c in range(n_cols):
        cell = table[(0, c)]
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#e6e6e6")
    for r_idx in range(1, len(rows) + 1):
        for c in range(n_cols):
            table[(r_idx, c)].set_facecolor(
                "#fff8e0" if r_idx % 2 else "#fffefa"
            )

    fig.suptitle(
        t("Construction blueprint (reference: straight cord T -> B) - "
          "{label}  (cord = {L:.2f} cm, rise {rise:.0f} cm, "
          "run {run:.0f} cm)").format(
            label=label, L=L_total, rise=ramp.rise, run=ramp.run,
        ),
        fontsize=13, fontweight="bold", y=0.985,
    )
    pdf_path = _save_fig(fig, path)
    print(t("Construction blueprint (cord reference) saved to {path} "
            "(+ PDF: {pdf})").format(path=path, pdf=pdf_path))


def draw_three_slope_blueprint(ramp: Ramp, best3: dict, path: str = "ramp_blueprint.png"):
    """
    Single-page construction drawing of the 3-slope profile, intended
    for an on-site worker.  Shows:
      * a true-scale side-view of the slope on a 10 cm grid
      * every keypoint labeled with its (x, y) measurement in cm
      * each segment annotated with its slope angle and percent
      * fillet radii called out
      * a measurement table on the side
    Coordinates: x = horizontal distance from the bottom of the slope
    (the start of the rise), y = vertical height above the garage floor.
    """
    if not HAS_PLT:
        return

    x1, y1 = best3["x1"], best3["y1"]
    x2, y2 = best3["x2"], best3["y2"]
    fillet = best3["fillet"]

    keypts = three_slope_keypoints(ramp, x1, y1, x2, y2, fillet)

    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(
        2, 1, left=0.07, right=0.97, top=0.95, bottom=0.32,
        hspace=0.28, height_ratios=[1.0, 3.6],
    )
    ax_true = fig.add_subplot(gs[0, 0])    # true-scale overview
    ax = fig.add_subplot(gs[1, 0])         # stretched-Y working drawing

    # ---- True-scale overview --------------------------------------------- #
    ax_true.plot([-150, 0], [0, 0], "k-", linewidth=2.0)
    ax_true.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
                 "k-", linewidth=2.0)
    ax_true.plot(best3["x"], best3["y"], "-",
                 color="tab:green", linewidth=2.6)
    ax_true.set_aspect("equal")
    ax_true.set_xticks(np.arange(-150, ramp.run + 151, 100))
    ax_true.set_yticks(np.arange(0, ramp.rise + 31, 50))
    ax_true.grid(True, alpha=0.4)
    ax_true.set_xlim(-160, ramp.run + 160)
    ax_true.set_ylim(-15, ramp.rise + 35)
    ax_true.set_title(
        t("True-scale view (1 cm vertical = 1 cm horizontal)"),
        fontsize=11,
    )
    ax_true.set_xlabel("x (cm)")
    ax_true.set_ylabel("y (cm)")

    # ---- Working drawing (vertical scale exaggerated) -------------------- #
    ax.plot([-150, 0], [0, 0], "k-", linewidth=2.5)
    ax.plot([ramp.run, ramp.run + 150], [ramp.rise, ramp.rise],
            "k-", linewidth=2.5)
    ax.plot(best3["x"], best3["y"], "-", color="tab:green", linewidth=3.0,
            label=t("Ramp profile to build"))

    # Fine grid: major every 50 cm in x and 10 cm in y; minor every 10/2.
    ax.set_xticks(np.arange(-150, ramp.run + 151, 50))
    ax.set_xticks(np.arange(-150, ramp.run + 151, 10), minor=True)
    ax.set_yticks(np.arange(0, ramp.rise + 41, 10))
    ax.set_yticks(np.arange(0, ramp.rise + 41, 2), minor=True)
    ax.grid(True, which="major", alpha=0.55, linewidth=0.9)
    ax.grid(True, which="minor", alpha=0.18, linewidth=0.5)

    label_letters = "ABCDEFGHIJKLMN"
    table_rows = []
    # Build a list of (letter, x, y, kind) so we can decide label offsets
    # without overlapping.
    for i, (name, xi, yi, kind, r) in enumerate(keypts):
        letter = label_letters[i]
        marker = "o" if kind == "kink" else "s"
        size = 110 if kind == "kink" else 80
        face = "tab:green" if kind == "kink" else "white"
        ax.scatter([xi], [yi], s=size, marker=marker,
                   facecolor=face, edgecolor="black",
                   linewidth=1.6, zorder=6)
        # Place labels above for early points, below for later, alternating.
        # In the stretched-Y view there's plenty of room.
        above = (i % 2 == 0)
        dy = 14 if above else -14
        ax.annotate(
            f"{letter}  ({xi:.1f}, {yi:.1f}) cm",
            xy=(xi, yi),
            xytext=(xi, yi + dy),
            ha="center", va="bottom" if above else "top",
            fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="black", alpha=0.95),
            arrowprops=dict(arrowstyle="-", color="black",
                            linewidth=0.9, alpha=0.7),
        )
        table_rows.append((letter, name, xi, yi, kind, r))

    # Per-segment annotations (mid-segment): angle and percent.
    seg_lines = [
        (t("Slope 1 (bottom)"),  (0.0, 0.0), (x1, y1)),
        (t("Slope 2 (middle)"),  (x1, y1), (x2, y2)),
        (t("Slope 3 (top)"),     (x2, y2), (ramp.run, ramp.rise)),
    ]
    for name, (xa, ya), (xb, yb) in seg_lines:
        dx_seg = xb - xa
        dy_seg = yb - ya
        ang_deg = math.degrees(math.atan2(dy_seg, dx_seg))
        pct = 100.0 * dy_seg / dx_seg
        L = math.hypot(dx_seg, dy_seg)
        mx, my = (xa + xb) / 2, (ya + yb) / 2
        ax.annotate(
            t("{name}\n{deg:.2f} degrees ({pct:.1f} %)\n"
              "length along plane = {L:.1f} cm").format(
                name=name, deg=ang_deg, pct=pct, L=L,
            ),
            xy=(mx, my), xytext=(mx, my - 26),
            ha="center", va="top", fontsize=11, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="lightyellow",
                      edgecolor="goldenrod", alpha=0.95),
        )

    # Header notice. No fillet radius -> slopes meet at sharp corners.
    if fillet > 0.5:
        msg = t("Round every kink with a smooth curve\n"
                 "of radius R = {fillet:.0f} cm.\n"
                 "The square markers show where each\n"
                 "curve starts and ends.").format(fillet=fillet)
    else:
        msg = t("Slopes meet directly at the marked points\n"
                 "(sharp corners).\n"
                 "No fillet needed.")
    ax.text(
        0.012, 0.98, msg,
        transform=ax.transAxes, ha="left", va="top",
        fontsize=11, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="lightcyan",
                  edgecolor="steelblue", alpha=0.95),
    )

    # Reference labels on the flat surfaces.
    ax.text(-75, -6, t("Garage floor (flat)"),
            ha="center", va="top", fontsize=11, style="italic")
    ax.text(ramp.run + 75, ramp.rise + 4,
            t("Street / outside (flat)"),
            ha="center", va="bottom", fontsize=11, style="italic")

    # Origin arrow.
    ax.annotate(
        t("Origin (0, 0)\nMeasure x horizontally\nfrom here.\n"
          "Measure y vertically."),
        xy=(0, 0), xytext=(-120, 55),
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                  edgecolor="black", alpha=0.95),
        arrowprops=dict(arrowstyle="->", color="black", linewidth=1.2),
    )

    ax.set_xlim(-160, ramp.run + 160)
    ax.set_ylim(-25, ramp.rise + 50)
    # Note: the vertical scale is exaggerated so that the labels stay
    # legible.  The true proportions are shown in the panel above.
    ax.set_xlabel(t("x  (cm, horizontal - 0 at the start of the ramp)"),
                  fontsize=12)
    ax.set_ylabel(t("y  (cm, height above the garage floor)"), fontsize=12)
    ax.set_title(
        t("Working drawing (vertical scale exaggerated for clarity) - "
          "use the (x, y) numbers, not the visual proportions"),
        fontsize=11,
    )
    ax.legend(loc="lower right", fontsize=11)
    fig.suptitle(
        t("Construction blueprint - 3-slope ramp  "
          "(rise {rise:.0f} cm, run {run:.0f} cm)").format(
            rise=ramp.rise, run=ramp.run,
        ),
        fontsize=14, fontweight="bold", y=0.985,
    )

    # ----  Measurements table in its own axes below the drawing.  ---- #
    ax_table = fig.add_axes([0.05, 0.03, 0.92, 0.26])
    ax_table.set_axis_off()
    cell_text = []
    for letter, name, xi, yi, kind, r in table_rows:
        kind_str = (t("corner") if kind == "kink"
                    else t("smooth curve (R={r:.0f} cm)").format(r=r))
        cell_text.append([letter, name, f"{xi:7.1f}", f"{yi:7.1f}", kind_str])
    table = ax_table.table(
        cellText=cell_text,
        colLabels=[t("pt"), t("what"), "x (cm)", "y (cm)", t("type")],
        loc="center",
        cellLoc="left",
        colLoc="left",
        colWidths=[0.04, 0.42, 0.10, 0.10, 0.34],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.0, 1.7)
    # Bold header.
    for c in range(5):
        cell = table[(0, c)]
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#e6e6e6")
    # Tint kink rows green.
    for r_idx, (_, _, _, _, kind, _) in enumerate(table_rows, start=1):
        for c in range(5):
            if kind == "kink":
                table[(r_idx, c)].set_facecolor("#eaf6ea")
            else:
                table[(r_idx, c)].set_facecolor("#fff8e0")

    pdf_path = _save_fig(fig, path)
    print(t("Construction blueprint saved to {path} (+ PDF: {pdf})"
            ).format(path=path, pdf=pdf_path))


def write_offsets(path, x, y, n=28):
    xs = np.linspace(0.0, x[-1], n)
    ys = np.interp(xs, x, y)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["x_cm", "y_cm"])
        for xi, yi in zip(xs, ys):
            w.writerow([f"{xi:.2f}", f"{yi:.2f}"])
    print(t("Construction offsets saved to {path}").format(path=path))
    print(t("  x = horizontal distance from the start of the ramp"))
    print(t("  y = height above the garage floor"))
    print()
    print("  x (cm)   y (cm)")
    for xi, yi in zip(xs, ys):
        print(f"  {xi:6.1f}   {yi:6.2f}")


# --------------------------------------------------------------------------- #
def sensitivity(car: Car, base_ramp: Ramp, runs):
    """For a list of candidate runs, optimise the ramp and report the
    worst-case clearance.  Useful when you can extend the slope into
    the garage or street area."""
    rows = []
    for run in runs:
        ramp = Ramp(rise=base_ramp.rise, run=run)
        try:
            best = search(ramp, car, n_theta=18, n_frac=18, refine=7)
            rows.append((run, best["chassis_min"], best["overhang_min"],
                         best["score"]))
        except Exception as e:  # pragma: no cover
            rows.append((run, float("nan"), float("nan"), float("nan")))
    return rows


def _ask_float(prompt: str, default: float | None = None,
               minimum: float = 0.01) -> float:
    """Read a numeric value from stdin, with validation."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        try:
            raw = input(f"  {prompt}{suffix}: ").strip().replace(",", ".")
        except EOFError:
            if default is not None:
                return float(default)
            raise SystemExit("\n" + t("Input cancelled."))
        if not raw and default is not None:
            return float(default)
        try:
            value = float(raw)
        except ValueError:
            print("    " + t("I do not understand that number. Try again."))
            continue
        if value < minimum:
            print("    " + t("The value must be greater than {minimum}. "
                              "Try again.").format(minimum=minimum))
            continue
        return value


def parse_inputs() -> tuple["Ramp", "Car"]:
    """
    Reads the ramp and car parameters from the command line, or asks for
    them on the console if missing.

    Required: rise and run.  The other car parameters default to the
    typical values of a Seat Leon FR 2025 if omitted.
    """
    global LANGUAGE
    parser = argparse.ArgumentParser(
        prog="ramp_optimizer",
        description=t(
            "Garage ramp profile optimizer. Computes the optimal ramp "
            "shape to avoid scraping, using several methods (linear ramp, "
            "two arcs + straight, 3 segments, 4 segments and free-form "
            "smooth curve)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-d", "--desnivel", "--rise", dest="desnivel",
        type=float, default=None,
        help=t("Total rise between the garage floor and the street (cm). "
                "Can also be passed as the first positional argument."),
    )
    parser.add_argument(
        "-l", "--longitud", "--run", dest="longitud",
        type=float, default=None,
        help=t("Horizontal length of the ramp (cm). Can also be passed "
                "as the second positional argument."),
    )
    parser.add_argument(
        "-c", "--altura-libre", "--clearance", dest="clearance",
        type=float, default=14.0,
        help=t("Ground clearance of the lowest underbody point on flat "
                "ground (cm)."),
    )
    parser.add_argument(
        "-w", "--batalla", "--wheelbase", dest="wheelbase",
        type=float, default=269.0,
        help=t("Distance between the front and rear axles (cm)."),
    )
    parser.add_argument(
        "-f", "--voladizo-delantero", "--front-overhang",
        dest="front_overhang", type=float, default=87.0,
        help=t("Distance from the front axle to the lowest front edge "
                "(bumper / lip, cm)."),
    )
    parser.add_argument(
        "-r", "--voladizo-trasero", "--rear-overhang",
        dest="rear_overhang", type=float, default=0.0,
        help=t("Distance from the rear axle to the lowest rear edge "
                "(cm). Leave at 0 if the rear bumper sits higher than "
                "the underbody."),
    )
    parser.add_argument(
        "--lang", choices=["en", "es"], default=None,
        help=t("Output language for the GUI, the console messages and "
                "the blueprint plots ('en' = English, 'es' = Spanish). "
                "Default: 'en' (or 'es' if compiled with --spanish)."),
    )
    parser.add_argument(
        "positional", nargs="*", type=float,
        help=t("Shortcut: 'ramp_optimizer RISE RUN' is equivalent to "
                "-d RISE -l RUN."),
    )
    args = parser.parse_args()

    if args.lang:
        LANGUAGE = args.lang

    if len(args.positional) >= 1 and args.desnivel is None:
        args.desnivel = args.positional[0]
    if len(args.positional) >= 2 and args.longitud is None:
        args.longitud = args.positional[1]

    interactive = (args.desnivel is None) or (args.longitud is None)
    if interactive:
        print("=" * 78)
        print("  " + t("GARAGE RAMP OPTIMIZER"))
        print("  " + t("Author: Efren Rodriguez Rodriguez"))
        print("  " + t("Web:   https://efrenrodriguezrodriguez.com/"))
        print("=" * 78)
        print()
        print(t("Enter the dimensions of the ramp you want to build."))
        print()
        if args.desnivel is None:
            args.desnivel = _ask_float(
                t("Total rise between the garage floor and the street (cm)"),
            )
        if args.longitud is None:
            args.longitud = _ask_float(
                t("Horizontal length of the ramp (cm)"),
            )
        print()
        print(t("Car data (press Enter to use the defaults for a Seat "
                 "Leon FR 2025):"))
        args.clearance = _ask_float(
            t("Ground clearance of the lowest underbody point (cm)"),
            default=args.clearance,
        )
        args.wheelbase = _ask_float(
            t("Wheelbase / distance between axles (cm)"),
            default=args.wheelbase,
        )
        args.front_overhang = _ask_float(
            t("Front overhang (axle to lowest front point, cm)"),
            default=args.front_overhang, minimum=0.0,
        )
        args.rear_overhang = _ask_float(
            t("Rear overhang (0 if it does not scrape, cm)"),
            default=args.rear_overhang, minimum=0.0,
        )
        print()

    if args.desnivel <= 0 or args.longitud <= 0:
        print(t("ERROR: rise and run must be positive."), file=sys.stderr)
        raise SystemExit(2)

    if args.desnivel >= args.longitud:
        print(
            t("WARNING: rise is greater than or equal to run. The mean "
              "grade would be >= 100 % (45 degrees or more), which is "
              "not realistic for a car."),
            file=sys.stderr,
        )

    car = Car(
        clearance=args.clearance,
        wheelbase=args.wheelbase,
        front_overhang=args.front_overhang,
        rear_overhang=args.rear_overhang,
    )
    ramp = Ramp(rise=args.desnivel, run=args.longitud)
    return ramp, car


def main() -> None:
    """Punto de entrada CLI: lee parametros y llama a compute_and_save."""
    ramp, car = parse_inputs()
    compute_and_save(ramp, car)


def compute_and_save(ramp: "Ramp", car: "Car") -> None:
    """Run every search, generate every file (PNG, PDF, CSV) in the
    current working directory.  Called from both the CLI and the GUI."""
    grade_pct = 100.0 * ramp.rise / ramp.run
    grade_deg = math.degrees(math.atan(ramp.rise / ramp.run))
    print(t("Ramp:  rise = {rise} cm,  run = {run} cm,  mean grade = "
            "{pct:.1f} % ({deg:.2f} degrees)").format(
        rise=ramp.rise, run=ramp.run, pct=grade_pct, deg=grade_deg,
    ))
    print(t("Car:   ground clearance = {clearance} cm,  wheelbase = "
            "{wheelbase} cm,").format(
        clearance=car.clearance, wheelbase=car.wheelbase,
    ))
    print(t("       front overhang = {fo} cm,  rear overhang = {ro} cm"
            ).format(fo=car.front_overhang, ro=car.rear_overhang))
    print()

    # ---- Linear ramp baseline ------------------------------------------- #
    x_lin, y_lin = linear_profile(ramp)
    res_lin = evaluate(x_lin, y_lin, car, ramp,
                       n_positions=3000, n_chassis=400)
    report(t("Linear ramp (current geometry)"), res_lin)

    # ---- Two arcs + straight middle ------------------------------------- #
    print(t("Searching the design space (two arcs + straight) ..."))
    best = search(ramp, car)
    print(t("Best parameters:"))
    print(t("  theta (max slope of the straight middle)  = {deg:.2f} "
            "degrees   (tan = {pct:.1f} %)").format(
        deg=best["theta_deg"], pct=math.tan(best["theta"]) * 100,
    ))
    print(t("  R_bottom (lower-arc radius)               = {value:7.1f} cm"
            ).format(value=best["r_bot"]))
    print(t("  R_top    (upper-arc radius)               = {value:7.1f} cm"
            ).format(value=best["r_top"]))
    print(t("  Length of the straight middle (along ramp) = {value:7.1f} cm"
            ).format(value=best["L_m"]))
    print()
    print(t("Segment endpoints (cm):"))
    print(t("  start of bottom arc      : x =   0.0,  y =   0.0"))
    print(t("  bottom arc -> straight   : x = {x:5.1f},  y = {y:5.1f}"
            ).format(x=best["x_b_end"], y=best["y_b_end"]))
    print(t("  straight -> top arc      : x = {x:5.1f},  y = {y:5.1f}"
            ).format(x=best["x_m_end"], y=best["y_m_end"]))
    print(t("  end of top arc           : x = {x:5.1f},  y = {y:5.1f}"
            ).format(x=ramp.run, y=ramp.rise))
    print()
    report(t("Optimal three-segment ramp (two arcs + straight)"), best)

    write_offsets("ramp_offsets.csv", best["x"], best["y"])

    # ---- 3 piecewise-linear slopes -------------------------------------- #
    print(t("Searching the best three-slope profile ..."))
    best3 = search_three_slope(ramp, car, n_grid=11, fillet=0.0)
    print(t("Best parameters (3 slopes):"))
    print(t("  break point 1:  x1 = {x:5.1f} cm,  y1 = {y:5.2f} cm"
            ).format(x=best3["x1"], y=best3["y1"]))
    print(t("  break point 2:  x2 = {x:5.1f} cm,  y2 = {y:5.2f} cm"
            ).format(x=best3["x2"], y=best3["y2"]))
    print(t("  slope 1 (bottom):    {deg:5.2f} degrees ({pct:.1f} %)"
            ).format(deg=best3["slope1_deg"],
                     pct=100*math.tan(math.radians(best3["slope1_deg"]))))
    print(t("  slope 2 (middle):    {deg:5.2f} degrees ({pct:.1f} %)"
            ).format(deg=best3["slope2_deg"],
                     pct=100*math.tan(math.radians(best3["slope2_deg"]))))
    print(t("  slope 3 (top):       {deg:5.2f} degrees ({pct:.1f} %)"
            ).format(deg=best3["slope3_deg"],
                     pct=100*math.tan(math.radians(best3["slope3_deg"]))))
    print(t("  fillet radius at every kink: {fillet:.0f} cm"
            ).format(fillet=best3["fillet"]))
    print()
    report(t("Optimal three-slope ramp"), best3)
    write_offsets("ramp_offsets_3slope.csv", best3["x"], best3["y"], n=28)
    draw_three_slope_blueprint(ramp, best3, "ramp_blueprint.png")

    # ---- 4 slopes + free-form smooth curve (parallel) ------------------- #
    best4 = None
    best_smooth = None
    if HAS_SCIPY:
        print(t("Searching in parallel: 4-slope ramp and free-form smooth "
                "curve ..."))
        with ProcessPoolExecutor(max_workers=2) as pool:
            fut4 = pool.submit(search_n_slope, ramp, car, 4, 0.0)
            fut_smooth = pool.submit(search_smooth, ramp, car, 5)
            best4 = fut4.result()
            best_smooth = fut_smooth.result()

        print(t("Best parameters (4 slopes):"))
        for k, (xb, yb) in enumerate(best4["breaks"], start=1):
            print(t("  break point {k}:  x{k} = {x:5.1f} cm,  "
                    "y{k} = {y:5.2f} cm").format(k=k, x=xb, y=yb))
        for s in best4["segments"]:
            print(t("  slope {i}: {deg:5.2f} degrees ({pct:5.1f} %)   "
                    "length {L:.1f} cm").format(
                i=s["i"], deg=s["angle_deg"],
                pct=s["percent"], L=s["length"],
            ))
        print()
        report(t("Optimal four-slope ramp"), best4)
        write_offsets("ramp_offsets_4slope.csv", best4["x"], best4["y"], n=28)

        print(t("Best control points of the smooth curve:"))
        print(f"  {'i':>2}  {'x (cm)':>8}  {'y (cm)':>8}")
        for i, (xc, yc) in enumerate(zip(best_smooth["xs_ctrl"],
                                          best_smooth["ys_ctrl"])):
            tag = (t("(endpoint)")
                   if i in (0, len(best_smooth["xs_ctrl"]) - 1) else "")
            print(f"  {i:>2}  {xc:8.1f}  {yc:8.2f}  {tag}")
        print()
        report(t("Optimal smooth ramp (PCHIP monotone spline)"), best_smooth)
        write_offsets("ramp_offsets_smooth.csv",
                      best_smooth["x"], best_smooth["y"], n=40)

        # Worker-friendly blueprints (top-of-ramp / wall reference).
        WALL_OFFSET = 136.0
        draw_piecewise_blueprint_topref(
            ramp,
            breaks=best4["breaks"],
            x_curve=best4["x"], y_curve=best4["y"],
            color="tab:purple",
            wall_height_above_top=WALL_OFFSET,
            label=t("4-slope ramp"),
            path="ramp_blueprint_top_4slope.png",
        )
        draw_smooth_blueprint_topref(
            ramp,
            x_curve=best_smooth["x"], y_curve=best_smooth["y"],
            ctrl_x=best_smooth["xs_ctrl"], ctrl_y=best_smooth["ys_ctrl"],
            color="tab:orange",
            wall_height_above_top=WALL_OFFSET,
            station_step_cm=30.0,
            label=t("free-form smooth curve (PCHIP)"),
            path="ramp_blueprint_top_smooth.png",
        )

        # Cord-reference blueprints (T -> B straight cord).
        draw_chord_blueprint(
            ramp,
            x_curve=best4["x"], y_curve=best4["y"],
            label=t("4-slope ramp"),
            color="tab:purple",
            breaks=best4["breaks"],
            path="ramp_blueprint_chord_4slope.png",
        )
        draw_chord_blueprint(
            ramp,
            x_curve=best_smooth["x"], y_curve=best_smooth["y"],
            label=t("free-form smooth curve (PCHIP)"),
            color="tab:orange",
            breaks=None,
            ctrl_x=best_smooth["xs_ctrl"], ctrl_y=best_smooth["ys_ctrl"],
            station_step_cm=30.0,
            path="ramp_blueprint_chord_smooth.png",
        )

        # CSVs (s, p) para los dos perfiles, referidos a la cuerda recta.
        for profile_name, x_arr, y_arr, fname in [
            ("4 tramos", best4["x"], best4["y"],
             "ramp_offsets_4slope_chord.csv"),
            ("suave", best_smooth["x"], best_smooth["y"],
             "ramp_offsets_smooth_chord.csv"),
        ]:
            s_arr, p_arr = chord_coords(ramp, x_arr, y_arr)
            order = np.argsort(s_arr)
            s_arr = s_arr[order]
            p_arr = p_arr[order]
            n_rows = 28 if profile_name == "4 tramos" else 40
            ss_out = np.linspace(0.0, s_arr[-1], n_rows)
            ps_out = np.interp(ss_out, s_arr, p_arr)
            with open(fname, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow([
                    "s_cm_along_cuerda_desde_T",
                    "p_cm_perpendicular_a_cuerda",
                ])
                for si, pi in zip(ss_out, ps_out):
                    w.writerow([f"{si:.2f}", f"{pi:.2f}"])
            print(t("Top-reference cord offsets ({label}) saved to {path}"
                    ).format(label=t(profile_name), path=fname))

        # Top-reference (u, d) CSVs for both profiles.
        for name, xc, yc, fname in [
            ("4 slopes", best4["x"], best4["y"],
             "ramp_offsets_4slope_top.csv"),
            ("smooth",   best_smooth["x"], best_smooth["y"],
             "ramp_offsets_smooth_top.csv"),
        ]:
            u_arr = ramp.run - xc
            d_arr = ramp.rise - yc
            order = np.argsort(u_arr)
            u_arr = u_arr[order]
            d_arr = d_arr[order]
            n_rows = 28 if name == "4 slopes" else 40
            us = np.linspace(0.0, u_arr[-1], n_rows)
            ds = np.interp(us, u_arr, d_arr)
            with open(fname, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow([
                    "u_cm_from_top_edge",
                    "d_cm_below_top_plane",
                    "drop_cm_from_wall",
                ])
                for ui, di in zip(us, ds):
                    w.writerow([f"{ui:.2f}", f"{di:.2f}",
                                f"{WALL_OFFSET + di:.2f}"])
            print(t("Top-reference offsets ({label}) saved to {path}"
                    ).format(label=t(name), path=fname))

    # ---- Comparison summary --------------------------------------------- #
    print("\n" + t("Comparison summary (worst scrape, in cm; positive = "
                    "no scrape):"))
    head_perfil = "profile" if LANGUAGE == "en" else "perfil"
    head_bajo = t("    bajo").lstrip().rjust(8) if LANGUAGE == "es" \
        else "chassis".rjust(8)
    head_bumper = "bumper".rjust(9)
    head_score = "worst".rjust(8)
    if LANGUAGE == "es":
        head_bumper = "paragol.".rjust(9)
        head_score = "peor".rjust(8)
    print(f"  {head_perfil:<32}  {head_bajo}  {head_bumper}  {head_score}")
    candidates = [
        (t("Linear ramp (current)"),         res_lin),
        (t("Two arcs + straight"),           best),
        (t("Three slopes"),                  best3),
    ]
    if best4 is not None:
        candidates.append((t("Four slopes"), best4))
    if best_smooth is not None:
        candidates.append((t("Free-form smooth curve (PCHIP)"), best_smooth))
    for label, m in candidates:
        ch = m["chassis_min"]
        ov = m["overhang_min"]
        sc = min(ch, ov)
        print(f"  {label:<32}  {ch:+8.2f}  {ov:+9.2f}  {sc:+8.2f}")
    print()
    # 3-slope blueprint with the wall / top-of-ramp reference.
    # Default wall height: 136 cm above the upper flat (street).
    WALL_OFFSET_OVER_TOP = 136.0
    draw_three_slope_blueprint_topref(
        ramp, best3,
        wall_height_above_top=WALL_OFFSET_OVER_TOP,
        path="ramp_blueprint_top.png",
    )

    # 3-slope (u, d) top-reference CSV.
    u_arr = ramp.run - best3["x"]
    d_arr = ramp.rise - best3["y"]
    order = np.argsort(u_arr)
    u_arr = u_arr[order]
    d_arr = d_arr[order]
    us_top = np.linspace(0.0, u_arr[-1], 28)
    ds_top = np.interp(us_top, u_arr, d_arr)
    with open("ramp_offsets_3slope_top.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "u_cm_from_top_edge",
            "d_cm_below_top_plane",
            "drop_cm_from_wall",
        ])
        for ui, di in zip(us_top, ds_top):
            w.writerow([f"{ui:.2f}", f"{di:.2f}",
                        f"{WALL_OFFSET_OVER_TOP + di:.2f}"])
    print(t("Top-reference offsets saved to {path}").format(
        path="ramp_offsets_3slope_top.csv",
    ))

    # Print key points of the 3-slope ramp to the terminal.
    print()
    print(t("Three-slope key points (mark these on the ground):"))
    pt_label_w = 42
    print(f"  {t('  pt'):<3} {t('what'):<{pt_label_w}} "
          f"{t('x (cm)'):>8} {t('y (cm)'):>8}  {t('notes')}")
    for i, (name, xi, yi, kind, r) in enumerate(
        three_slope_keypoints(ramp, best3["x1"], best3["y1"],
                              best3["x2"], best3["y2"], best3["fillet"])
    ):
        letter = "ABCDEFGHIJKLMN"[i]
        notes = (t("corner") if kind == "kink"
                 else t("fillet (R={r:.0f} cm)").format(r=r))
        print(f"  {letter:<3} {name:<{pt_label_w}} {xi:8.1f} {yi:8.1f}  {notes}")
    print()

    # ---- Sensitivity if the ramp is lengthened -------------------------- #
    if best["score"] < -0.1:
        print("\n" + t("The current run length leaves some unavoidable "
                        "scraping."))
        print(t("Sensitivity if the ramp is lengthened (rise stays at "
                "{rise:.0f} cm):").format(rise=ramp.rise))
        print(f"  {t('    run'):>6}  {t('chassis'):>8}  "
              f"{t('bumper'):>9}  {t('score'):>8}")
        for run, ch, ov, sc in sensitivity(
            car, ramp, [ramp.run, ramp.run + 30, ramp.run + 60,
                        ramp.run + 100, ramp.run + 150, ramp.run + 200]
        ):
            print(f"  {run:6.0f}  {ch:+8.2f}  {ov:+9.2f}  {sc:+8.2f}")
        print(t("  (chassis = worst between-wheels clearance;"))
        print(t("   bumper  = worst front-overhang / bumper clearance;"))
        print(t("   worst   = the smaller of the two; positive means no "
                "scraping.)"))
        print()

    # ---- Plot ------------------------------------------------------------- #
    if HAS_PLT:
        # Build the road profile (with flat extensions) and a clearance
        # trace for each candidate.
        def trace_clearance(x_p, y_p):
            x_pre = np.linspace(-300, 0.0, 120, endpoint=False)
            y_pre = np.zeros_like(x_pre)
            x_post = np.linspace(ramp.run, ramp.run + 300, 120)[1:]
            y_post = np.full_like(x_post, ramp.rise)
            x_road = np.concatenate([x_pre, x_p, x_post])
            y_road = np.concatenate([y_pre, y_p, y_post])
            order = np.argsort(x_road)
            x_road, y_road = x_road[order], y_road[order]
            keep = np.concatenate([[True], np.diff(x_road) > 1e-9])
            x_road, y_road = x_road[keep], y_road[keep]
            rear_xs = np.linspace(-200, ramp.run + 200 - car.wheelbase, 900)
            min_clr = np.full_like(rear_xs, np.inf)
            for i, x_rear in enumerate(rear_xs):
                x_front = x_rear + car.wheelbase
                h_rear = float(np.interp(x_rear, x_road, y_road))
                h_front = float(np.interp(x_front, x_road, y_road))
                x_pts = np.linspace(
                    x_rear - car.rear_overhang,
                    x_front + car.front_overhang, 200,
                )
                t = (x_pts - x_rear) / car.wheelbase
                chassis_y = h_rear + t * (h_front - h_rear) + car.clearance
                road_y = np.interp(x_pts, x_road, y_road)
                min_clr[i] = float(np.min(chassis_y - road_y))
            return rear_xs, min_clr

        profiles = [
            (t("Linear ramp (current geometry)"),
             x_lin, y_lin, "tab:red", res_lin, []),
            (t("Two arcs + straight"),
             best["x"], best["y"], "tab:blue", best,
             [(best["x_b_end"], best["y_b_end"]),
              (best["x_m_end"], best["y_m_end"])]),
            (t("Three slopes"),
             best3["x"], best3["y"], "tab:green", best3,
             [(best3["x1"], best3["y1"]),
              (best3["x2"], best3["y2"])]),
        ]
        if best4 is not None:
            profiles.append((
                t("Four slopes"),
                best4["x"], best4["y"], "tab:purple", best4,
                list(best4["breaks"]),
            ))
        if best_smooth is not None:
            ctrl_breaks = list(zip(
                best_smooth["xs_ctrl"][1:-1],
                best_smooth["ys_ctrl"][1:-1],
            ))
            profiles.append((
                t("Free-form smooth curve (PCHIP)"),
                best_smooth["x"], best_smooth["y"],
                "tab:orange", best_smooth, ctrl_breaks,
            ))

        # Top row: profiles (one column per design, all at the same scale).
        # Bottom row: clearance traces (same x-axis as the row above).
        x_min, x_max = -250, ramp.run + 250
        y_min_p, y_max_p = -10, ramp.rise + 30

        # Find a common y-range for the clearance traces.
        traces = [trace_clearance(p[1], p[2]) for p in profiles]
        all_clr = np.concatenate([t[1] for t in traces])
        clr_lo = min(-3.0, float(np.nanmin(all_clr)) - 1.0)
        clr_hi = max(16.0, float(np.nanmax(all_clr)) + 1.0)

        n_cols = len(profiles)
        fig, axes = plt.subplots(
            2, n_cols, figsize=(4.6 * n_cols + 1, 9),
            gridspec_kw={"height_ratios": [1.0, 1.0]},
        )
        if n_cols == 1:
            axes = np.array([[axes[0]], [axes[1]]])

        for col, (title, xp, yp, color, m, breaks) in enumerate(profiles):
            ax_top = axes[0, col]
            ax_bot = axes[1, col]

            # Profile.
            ax_top.plot([x_min, 0], [0, 0], "k-", linewidth=1.2)
            ax_top.plot([ramp.run, x_max], [ramp.rise, ramp.rise],
                        "k-", linewidth=1.2)
            ax_top.plot(xp, yp, "-", color=color, linewidth=2.4)
            if breaks:
                bx = [b[0] for b in breaks]
                by = [b[1] for b in breaks]
                ax_top.scatter(bx, by, color=color, s=40, zorder=5)
            ax_top.set_xlim(x_min, x_max)
            ax_top.set_ylim(y_min_p, y_max_p)
            ax_top.set_aspect("equal")
            ax_top.grid(True, alpha=0.3)
            ax_top.set_title(title, fontsize=11)
            if col == 0:
                ax_top.set_ylabel(t("Height (cm)"))
            ax_top.set_xlabel(t("Horizontal distance (cm)"))

            # Annotate worst points on the profile.
            for label_pt, x_pt in [
                ("chassis worst", m["chassis_at_x"]),
                ("bumper worst",  m["overhang_at_x"]),
            ]:
                if x_pt is None:
                    continue
                y_pt = float(np.interp(x_pt, xp, yp)) if 0 <= x_pt <= ramp.run \
                       else (0.0 if x_pt < 0 else ramp.rise)
                ax_top.scatter([x_pt], [y_pt], marker="x",
                               color="black", s=55, zorder=6)

            # Clearance trace.
            rear_xs, min_clr = traces[col]
            ax_bot.fill_between(
                rear_xs, min_clr, 0,
                where=(min_clr < 0), color="tab:red", alpha=0.25,
            )
            ax_bot.plot(rear_xs, min_clr, "-", color=color, linewidth=2.0)
            ax_bot.axhline(0, color="k", linewidth=0.9)
            ax_bot.set_xlim(x_min, x_max)
            ax_bot.set_ylim(clr_lo, clr_hi)
            ax_bot.grid(True, alpha=0.3)
            ax_bot.set_xlabel(t("Rear-wheel position (cm)"))
            if col == 0:
                ax_bot.set_ylabel(t("Minimum clearance (cm)\n"
                                     "(negative = scrape)"))
            worst = float(np.min(min_clr))
            ax_bot.set_title(
                t("worst scrape: {worst:+.2f} cm").format(worst=worst),
                fontsize=10,
            )

        fig.suptitle(
            t("Ramp profile comparison  "
              "(rise {rise:.0f} cm, run {run:.0f} cm, "
              "ground clearance {clearance:.0f} cm, "
              "wheelbase {wheelbase:.0f} cm, "
              "front overhang {fo:.0f} cm)").format(
                rise=ramp.rise, run=ramp.run,
                clearance=car.clearance, wheelbase=car.wheelbase,
                fo=car.front_overhang,
            ),
            fontsize=12,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        pdf_path = _save_fig(fig, "ramp_profile.png", dpi=120)
        print(f"Grafica de perfiles guardada en ramp_profile.png "
              f"(+ PDF: {pdf_path})")
    else:
        print("(matplotlib no esta instalado; no se genera la grafica)")


def launch_gui() -> None:
    """Interfaz grafica (Tkinter).  Se usa cuando se ejecuta el programa
    sin argumentos por linea de comandos (incluyendo el caso 'doble click
    sobre rampa.exe' del compilado con PyInstaller --windowed)."""
    import contextlib
    import io
    import os
    import platform
    import queue
    import subprocess
    import threading
    import tkinter as tk
    import webbrowser
    from tkinter import filedialog, messagebox, ttk

    AUTHOR = "Efren Rodriguez Rodriguez"
    URL = "https://efrenrodriguezrodriguez.com/"

    # Carpeta de salida por defecto: junto al .exe (modo congelado) o junto
    # al script .py.
    if getattr(sys, "frozen", False):
        default_out_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        default_out_dir = os.path.dirname(os.path.abspath(__file__))

    root = tk.Tk()
    root.title(t("Garage Ramp Optimizer"))
    root.geometry("820x820")
    try:
        root.tk.call("tk", "scaling", 1.1)
    except tk.TclError:
        pass
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")

    # ---- Header --------------------------------------------------------- #
    header = ttk.Frame(root, padding=(14, 12, 14, 4))
    header.pack(fill="x")
    ttk.Label(header, text=t("Garage Ramp Optimizer"),
              font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(header, text=t("Author: {name}").format(name=AUTHOR),
              font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 0))
    link = tk.Label(header, text=URL, fg="#1565c0", cursor="hand2",
                    font=("Segoe UI", 10, "underline"))
    link.pack(anchor="w")
    link.bind("<Button-1>", lambda _e: webbrowser.open(URL))

    ttk.Separator(root).pack(fill="x", padx=10)

    # ---- Ramp data ------------------------------------------------------ #
    ramp_frame = ttk.LabelFrame(root, text=t("Ramp data"), padding=10)
    ramp_frame.pack(fill="x", padx=14, pady=(8, 4))

    def _entry(parent, row, label, default):
        ttk.Label(parent, text=label).grid(
            row=row, column=0, sticky="e", padx=6, pady=4)
        var = tk.StringVar(value=str(default))
        ent = ttk.Entry(parent, textvariable=var, width=10,
                        justify="right")
        ent.grid(row=row, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(parent, text="cm").grid(
            row=row, column=2, sticky="w", padx=2, pady=4)
        return var

    desnivel_var = _entry(ramp_frame, 0,
                           t("Total rise (garage to street):"), 136)
    longitud_var = _entry(ramp_frame, 1,
                           t("Horizontal length of the ramp:"), 540)

    # ---- Car data ------------------------------------------------------- #
    car_frame = ttk.LabelFrame(
        root,
        text=t("Car data  (defaults: Seat Leon FR 2025)"),
        padding=10,
    )
    car_frame.pack(fill="x", padx=14, pady=4)

    altura_var = _entry(car_frame, 0,
                          t("Ground clearance (on flat):"), 14)
    batalla_var = _entry(car_frame, 1,
                           t("Wheelbase (between axles):"), 269)
    voladizo_d_var = _entry(car_frame, 2,
                              t("Front overhang (axle to front):"), 87)
    voladizo_t_var = _entry(car_frame, 3,
                              t("Rear overhang (0 if it does not scrape):"), 0)

    # ---- Output folder -------------------------------------------------- #
    folder_frame = ttk.LabelFrame(
        root, text=t("Output folder for the blueprints and CSV files"),
        padding=10,
    )
    folder_frame.pack(fill="x", padx=14, pady=4)
    folder_var = tk.StringVar(value=default_out_dir)
    ttk.Entry(folder_frame, textvariable=folder_var).grid(
        row=0, column=0, sticky="ew", padx=4)
    folder_frame.columnconfigure(0, weight=1)

    def choose_folder():
        d = filedialog.askdirectory(initialdir=folder_var.get(),
                                     title=t("Pick the output folder"))
        if d:
            folder_var.set(d)

    ttk.Button(folder_frame, text=t("Browse..."),
               command=choose_folder).grid(row=0, column=1, padx=4)

    # ---- Calculate button + status ------------------------------------- #
    action_frame = ttk.Frame(root, padding=(14, 6))
    action_frame.pack(fill="x")
    calc_btn = ttk.Button(action_frame,
                           text=t("Calculate and generate blueprints"))
    calc_btn.pack(side="left")
    progress = ttk.Progressbar(action_frame, mode="determinate",
                                length=260, maximum=100)
    progress.pack(side="left", padx=10)
    pct_var = tk.StringVar(value="0 %")
    ttk.Label(action_frame, textvariable=pct_var,
              font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 12))
    status_var = tk.StringVar(
        value=t("Ready. Enter the data and click Calculate."))
    ttk.Label(action_frame, textvariable=status_var,
              font=("Segoe UI", 10, "italic")).pack(side="left")

    # Elapsed-time line.
    time_frame = ttk.Frame(root, padding=(14, 0))
    time_frame.pack(fill="x")
    time_var = tk.StringVar(value="")
    ttk.Label(time_frame, textvariable=time_var,
              font=("Segoe UI", 9), foreground="#444").pack(anchor="w")

    # ---- Output text area ---------------------------------------------- #
    results_frame = ttk.LabelFrame(root, text=t("Calculation output"),
                                     padding=4)
    results_frame.pack(fill="both", expand=True, padx=14, pady=(4, 8))
    txt_scroll = ttk.Scrollbar(results_frame)
    txt_scroll.pack(side="right", fill="y")
    results_text = tk.Text(
        results_frame, font=("Consolas", 9),
        yscrollcommand=txt_scroll.set, wrap="none", height=18,
    )
    results_text.pack(fill="both", expand=True)
    txt_scroll.config(command=results_text.yview)

    # ---- Bottom buttons ------------------------------------------------ #
    bottom = ttk.Frame(root, padding=(14, 4, 14, 12))
    bottom.pack(fill="x")

    def open_results_folder():
        d = folder_var.get()
        if not os.path.isdir(d):
            messagebox.showerror(t("Error"), t("The folder does not exist."))
            return
        try:
            if platform.system() == "Windows":
                os.startfile(d)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception as e:
            messagebox.showerror(
                t("Error"),
                t("Cannot open the folder:\n{err}").format(err=e),
            )

    ttk.Button(bottom, text=t("Open output folder"),
               command=open_results_folder).pack(side="left")
    ttk.Button(bottom, text=t("Close"),
                command=root.destroy).pack(side="right")

    # ---- Stage triggers parsed from the log to drive the progress bar -- #
    # Each tuple is (substring printed by compute_and_save when the stage
    # finishes, target percentage at that point, status message to show
    # NEXT). Order must match the chronological order of those prints.
    # The trigger substrings are taken from the LOCALIZED log output, so
    # we generate them through t() to match whatever language is active.
    def _trig(en: str) -> str:
        return t(en)

    STAGES = [
        (_trig("Searching the design space (two arcs + straight) ..."),
         3,  t("Optimizing: two arcs + straight...")),
        (_trig("Optimal three-segment ramp (two arcs + straight)"),
         8,  t("Optimizing: three slopes...")),
        (_trig("Searching the best three-slope profile ..."),
         10, t("Optimizing: three slopes...")),
        (_trig("Optimal three-slope ramp"),
         15, t("Generating first blueprint (3 slopes)...")),
        (_trig("Searching in parallel: 4-slope ramp and free-form smooth "
                 "curve ..."),
         18, t("Optimizing in parallel: 4 slopes and free-form smooth "
                "(longest step)...")),
        (_trig("Optimal four-slope ramp"),
         55, t("4 slopes done. Waiting for the smooth curve...")),
        (_trig("Optimal smooth ramp (PCHIP monotone spline)"),
         70, t("Generating 4-slope blueprints...")),
        ("ramp_blueprint_top_4slope",
         76, t("Generating smooth-curve blueprints...")),
        ("ramp_blueprint_top_smooth",
         80, t("Generating cord-reference blueprints...")),
        ("ramp_blueprint_chord_4slope",
         83, t("Generating cord-reference blueprints...")),
        ("ramp_blueprint_chord_smooth",
         86, t("Generating top-reference 3-slope blueprint...")),
        ("ramp_blueprint_top.png",
         88, t("Computing sensitivity to ramp length...")),
        (_trig("Sensitivity if the ramp is lengthened"),
         90, t("Computing sensitivity to ramp length...")),
        ("ramp_profile.png",
         100, t("Done. Blueprints and CSVs generated.")),
    ]
    current_stage = [0]
    start_time = [None]    # type: list

    # ---- Cola para comunicacion hilo->GUI ------------------------------ #
    msg_q: "queue.Queue[tuple[str, str]]" = queue.Queue()

    class _GuiStream:
        """File-like que envia cada print() a la cola, para mostrarlo en
        el cuadro de texto de la GUI."""
        def write(self, s: str) -> int:
            if s:
                msg_q.put(("log", s))
            return len(s)
        def flush(self) -> None:
            return

    def _worker(ramp, car, out_dir):
        try:
            cwd = os.getcwd()
            os.chdir(out_dir)
            try:
                stream = _GuiStream()
                with contextlib.redirect_stdout(stream), \
                     contextlib.redirect_stderr(stream):
                    compute_and_save(ramp, car)
            finally:
                os.chdir(cwd)
            msg_q.put(("done", ""))
        except Exception as e:  # noqa: BLE001
            import traceback
            msg_q.put(("error", f"{e}\n\n{traceback.format_exc()}"))

    def _set_progress(pct: int, msg: str | None = None) -> None:
        progress["value"] = pct
        pct_var.set(f"{pct} %")
        if msg is not None:
            status_var.set(msg)

    def _format_secs(s: int) -> str:
        if s < 60:
            return f"{s} s"
        return f"{s // 60} min {s % 60:02d} s"

    def _tick_elapsed():
        """Refresh the elapsed-time label once a second while the
        computation is running."""
        import time
        if start_time[0] is None:
            return
        elapsed = int(time.time() - start_time[0])
        time_var.set(t("Elapsed: {elapsed}   (usually takes between 1 "
                        "and 3 minutes)").format(
            elapsed=_format_secs(elapsed),
        ))
        root.after(1000, _tick_elapsed)

    def _drain_queue():
        finished = False
        try:
            while True:
                kind, payload = msg_q.get_nowait()
                if kind == "log":
                    results_text.insert("end", payload)
                    results_text.see("end")
                    # Advance the progress bar when the next expected
                    # trigger substring shows up.
                    while current_stage[0] < len(STAGES):
                        trigger, pct, msg = STAGES[current_stage[0]]
                        if trigger in payload:
                            _set_progress(pct, msg)
                            current_stage[0] += 1
                        else:
                            break
                elif kind == "done":
                    finished = True
                    _set_progress(100,
                                   t("Done. Blueprints and CSV files generated."))
                    calc_btn.config(state="normal")
                    if start_time[0] is not None:
                        import time
                        total = int(time.time() - start_time[0])
                        time_var.set(t("Total time: {total}").format(
                            total=_format_secs(total),
                        ))
                    start_time[0] = None
                    messagebox.showinfo(
                        t("Calculation complete"),
                        t("Blueprints (PNG and PDF) and CSV files saved "
                          "to:\n\n{folder}").format(
                            folder=folder_var.get(),
                        ),
                    )
                elif kind == "error":
                    finished = True
                    progress.stop()
                    calc_btn.config(state="normal")
                    status_var.set(t("Error during the calculation."))
                    results_text.insert("end", "\n\nERROR:\n" + payload)
                    results_text.see("end")
                    start_time[0] = None
                    messagebox.showerror(t("Error"), payload[:1000])
        except queue.Empty:
            pass
        if not finished:
            root.after(150, _drain_queue)

    def _read_float(var: tk.StringVar, name: str) -> float:
        raw = var.get().strip().replace(",", ".")
        if not raw:
            raise ValueError(t("'{name}' is empty.").format(name=name))
        return float(raw)

    def on_calculate():
        try:
            desnivel = _read_float(desnivel_var, t("Rise"))
            longitud = _read_float(longitud_var, t("Run"))
            altura = _read_float(altura_var, t("Ground clearance"))
            batalla = _read_float(batalla_var, t("Wheelbase"))
            voladizo_d = _read_float(voladizo_d_var, t("Front overhang"))
            voladizo_t = _read_float(voladizo_t_var, t("Rear overhang"))
        except ValueError as e:
            messagebox.showerror(t("Invalid data"), str(e))
            return

        if desnivel <= 0 or longitud <= 0:
            messagebox.showerror(
                t("Invalid data"),
                t("Rise and run must be greater than 0."),
            )
            return
        if altura <= 0 or batalla <= 0:
            messagebox.showerror(
                t("Invalid data"),
                t("Ground clearance and wheelbase must be greater than 0."),
            )
            return
        if desnivel >= longitud:
            if not messagebox.askyesno(
                t("Extreme grade"),
                t("Rise ({rise:.0f} cm) is greater than or equal to run "
                  "({run:.0f} cm).\nThat is a grade >= 100 % (45 degrees "
                  "or more), unrealistic for a car.\n\nDo you want to "
                  "continue anyway?").format(
                    rise=desnivel, run=longitud,
                ),
            ):
                return

        out_dir = folder_var.get().strip()
        if not out_dir:
            messagebox.showerror(t("Error"), t("Pick an output folder."))
            return
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(
                t("Error"),
                t("Cannot create the output folder:\n{err}").format(err=e),
            )
            return

        car = Car(clearance=altura, wheelbase=batalla,
                  front_overhang=voladizo_d, rear_overhang=voladizo_t)
        ramp = Ramp(rise=desnivel, run=longitud)

        results_text.delete("1.0", "end")
        current_stage[0] = 0
        _set_progress(1,
                       t("Preparing the data and the linear reference "
                         "ramp..."))
        time_var.set(t("Elapsed: 0 s   (usually takes between 1 and 3 "
                        "minutes)"))
        calc_btn.config(state="disabled")

        import time
        start_time[0] = time.time()
        root.after(1000, _tick_elapsed)

        thread = threading.Thread(
            target=_worker, args=(ramp, car, out_dir), daemon=True,
        )
        thread.start()
        root.after(150, _drain_queue)

    calc_btn.config(command=on_calculate)
    root.mainloop()


if __name__ == "__main__":
    # Soporte para que el ejecutable empaquetado con PyInstaller pueda
    # lanzar procesos hijos (ProcessPoolExecutor) sin reentrar en el
    # programa principal.
    import multiprocessing
    multiprocessing.freeze_support()

    # Sin argumentos -> GUI.  Con argumentos -> modo CLI (compatibilidad).
    if len(sys.argv) > 1:
        main()
    else:
        try:
            launch_gui()
        except Exception as gui_err:  # noqa: BLE001
            # Si Tkinter no esta disponible, caer al modo de consola.
            print(f"GUI no disponible ({gui_err}). Usando modo de consola...")
            main()
