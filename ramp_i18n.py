"""
ramp_i18n
=========

Localization layer for the garage ramp optimizer.

The application is written in English by default.  A Spanish
translation is available; activate it with one of:

  * the CLI flag  ``--lang es``
  * the environment variable  ``RAMP_LANG=es``
  * a marker file  ``_lang_es.flag``  bundled inside the .exe, which
    is what ``python build_exe.py --spanish`` does

Public API consumed by ``ramp_optimizer``:

* :data:`LANGUAGE`         - current active language code (``"en"`` / ``"es"``)
* :func:`t`                - translate a string
* :data:`_TRANSLATIONS_ES` - the dict of English -> Spanish strings
"""

from __future__ import annotations

import os
import sys


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
    "(matplotlib is not installed; skipping comparison plot)":
        "(matplotlib no esta instalado; no se genera la grafica)",
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
    "Curve control points":
        "Puntos de control de la curva",
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
    "Working drawing (vertical scale exaggerated for clarity) - use the (x, y) numbers, not the visual proportions":
        "Plano de trabajo (escala vertical aumentada para mayor claridad) - usar los valores (x, y), no las proporciones visuales",
    "Construction blueprint - 3-slope ramp  (rise {rise:.0f} cm, run {run:.0f} cm)":
        "Plano de construccion - rampa de 3 tramos  (desnivel {rise:.0f} cm, longitud {run:.0f} cm)",
    "x  (cm, horizontal - 0 at the start of the ramp)":
        "x  (cm, horizontal - 0 en el inicio de la rampa)",
    "y  (cm, height above the garage floor)":
        "y  (cm, altura sobre el suelo del garaje)",

    # Top-reference blueprint chrome.
    "Side wall ({h:.0f} cm above the street)":
        "Muro lateral (a {h:.0f} cm sobre la calle)",
    "u (cm) - distance from the top edge (growing toward the garage)":
        "u (cm) - distancia desde el borde superior (creciendo hacia el garaje)",
    "d (cm) - depth below the top plane":
        "d (cm) - profundidad bajo el plano superior",
    "drop {drop:.1f} cm\nfrom the wall to {label}":
        "bajada {drop:.1f} cm\ndesde el muro hasta {label}",
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
    "Continuous curve: mark a station every {step:.0f} cm along the garage floor from the start of the ramp; for each station measure y vertically.":
        "Curva continua: marcar una estacion cada {step:.0f} cm a lo largo del suelo del garaje desde el inicio de la rampa; para cada estacion medir y en vertical.",
    "start station (at the garage)":
        "estacion inicial (en el garaje)",
    "end station (at the street)":
        "estacion final (en la calle)",
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

    # ---- Parallel-search log lines (added in v0.5+) ---------------- #
    "Searching all profiles in parallel ({names}) ...":
        "Buscando todos los perfiles en paralelo ({names}) ...",
    "Searching all profiles in parallel ":
        "Buscando todos los perfiles en paralelo ",
    "none -- only the linear baseline will be reported":
        "ninguno -- solo se mostrara la rampa lineal de referencia",
    "  ... {name}: done.":
        "  ... {name}: listo.",
    "two arcs + straight":
        "dos arcos + recta",
    "three slopes":
        "tres tramos rectos",
    "four slopes":
        "cuatro tramos rectos",
    "free-form smooth (PCHIP)":
        "curva suave libre (PCHIP)",
    "Optimizing all profiles in parallel (longest step)...":
        "Optimizando todos los perfiles en paralelo (paso mas largo)...",
    "Generating top-reference blueprints...":
        "Generando planos en sistema muro...",
    "two arcs + straight: done.  Waiting for the rest...":
        "dos arcos + recta: listo. Esperando al resto...",
    "three slopes: done.  Waiting for the rest...":
        "tres tramos rectos: listo. Esperando al resto...",
    "four slopes: done.  Waiting for the rest...":
        "cuatro tramos rectos: listo. Esperando al resto...",
    "free-form smooth (PCHIP): done.":
        "curva suave libre (PCHIP): listo.",
    "Best parameters (two arcs + straight):":
        "Mejores parametros (dos arcos + recta):",

    # ---- Live linear-ramp preview (GUI, added in v0.6) ------------ #
    "Live preview (linear ramp)":
        "Vista previa en directo (rampa lineal)",
    "Linear ramp":
        "Rampa lineal",
    "rise {r:.0f} cm,  run {n:.0f} cm   ({pct:.1f} %,  {deg:.1f} degrees)":
        "desnivel {r:.0f} cm,  longitud {n:.0f} cm   ({pct:.1f} %,  {deg:.1f} grados)",

    # ---- Concrete-volume cost estimator (added in v0.6) ----------- #
    "Concrete cost estimator (optional)":
        "Estimador de coste del hormigon (opcional)",
    "Ramp width:":
        "Ancho de la rampa:",
    "Concrete cost per m^3:":
        "Coste del hormigon por m^3:",
    "(leave width or cost empty to skip the cost report)":
        "(deja el ancho o el coste vacios para omitir el informe de coste)",
    "Ramp width":
        "Ancho de la rampa",
    "Cost per m^3":
        "Coste por m^3",
    "Concrete-volume estimate (ramp width: {w:.0f} cm; "
    "slab from the floor up to the surface):":
        "Estimacion de volumen de hormigon (ancho de rampa: {w:.0f} cm; "
        "losa desde el suelo hasta la superficie):",
    "volume (m^3)":
        "volumen (m^3)",
    "delta vs linear (m^3)":
        "delta vs lineal (m^3)",
    "cost ({sym})":
        "coste ({sym})",
    "  (positive 'delta' = more concrete than the linear baseline)":
        "  (delta positivo = mas hormigon que la rampa lineal de referencia)",
    "  (rate used: {rate:.2f} {sym} per m^3)":
        "  (precio usado: {rate:.2f} {sym} por m^3)",
    "Ramp width in cm (perpendicular to the slope direction). "
    "Used only by the optional concrete-volume cost estimator. "
    "Leave at 0 to skip the cost report.":
        "Ancho de la rampa en cm (perpendicular a la direccion de la "
        "pendiente). Lo usa solo el estimador opcional de volumen de "
        "hormigon. Deja 0 para omitir el informe de coste.",
    "Cost per cubic metre of concrete in your currency, used "
    "by the optional cost estimator.  Leave at 0 to print "
    "only the volumes.":
        "Coste por metro cubico de hormigon en tu moneda, usado por "
        "el estimador opcional de coste. Deja 0 para mostrar solo los "
        "volumenes.",
    "Currency symbol shown next to the estimated cost "
    "(e.g. EUR, USD, GBP).":
        "Simbolo de la moneda mostrado junto al coste estimado "
        "(p.ej. EUR, USD, GBP).",

    # ---- Method-selection checkboxes / CLI flags (added in v0.6) - #
    "Profiles to optimize":
        "Perfiles a optimizar",
    "Three slopes  (computationally harder, takes longer)":
        "Tres tramos rectos  (mas costoso de calcular, tarda mas)",
    "Pick at least one profile to optimise.":
        "Selecciona al menos un perfil para optimizar.",
    "Skip the two-arc + straight optimisation.":
        "Omitir la optimizacion de dos arcos + recta.",
    "Run the three-slope grid search.  Off by default; the "
    "result rarely beats the 4-slope or smooth profile.":
        "Ejecutar la busqueda en rejilla de tres tramos rectos. "
        "Desactivada por defecto; el resultado rara vez supera al "
        "perfil de 4 tramos o a la curva suave.",
    "Skip the four-slope optimisation.":
        "Omitir la optimizacion de cuatro tramos rectos.",
    "Skip the free-form smooth (PCHIP) optimisation.":
        "Omitir la optimizacion de la curva suave libre (PCHIP).",

    # ---- Output-format toggles + tighter labels (added in v0.7) ---- #
    "Free-form smooth (PCHIP)":
        "Curva suave libre (PCHIP)",
    "Three slopes  (slower, usually worse)":
        "Tres tramos rectos  (mas lento, suele dar peor resultado)",
    "Output formats:":
        "Formatos de salida:",
    "PDF blueprints":
        "Planos en PDF",
    "PNG images":
        "Imagenes PNG",
    "CSV measurements":
        "Medidas en CSV",
    "Pick at least one output format (PDF / PNG / CSV).":
        "Selecciona al menos un formato de salida (PDF / PNG / CSV).",
    "NOTE: skipping {fmts} output (disabled by the user); the "
    "'saved to ...' lines below name the canonical filename "
    "even when the file is not actually written.":
        "NOTA: omitiendo la salida {fmts} (desactivada por el usuario); "
        "las lineas 'saved to ...' siguientes nombran el fichero "
        "canonico aunque no se escriba realmente en disco.",
    "Skip the PDF blueprints (only PNGs / CSVs are written).":
        "Omitir los planos en PDF (solo se escriben los PNG / CSV).",
    "Also write the raster PNG copies of every blueprint.":
        "Escribir tambien las copias en PNG (raster) de cada plano.",
    "Also write the CSV measurement tables.":
        "Escribir tambien las tablas de medidas en CSV.",
}


# --------------------------------------------------------------------------- #
#  Optional gettext catalog
# --------------------------------------------------------------------------- #
# When a compiled gettext catalog (locale/<lang>/LC_MESSAGES/ramp_optimizer.mo)
# is reachable -- both during regular Python execution and inside a
# PyInstaller bundle -- we prefer it over the in-process dict.  This way
# external translators can edit the .po file with Poedit / Crowdin /
# Weblate without touching Python code, and the dict still serves as a
# safety net when the catalog is missing.

import gettext as _gettext


def _candidate_locale_dirs() -> "list[str]":
    """Return every plausible folder where the gettext .mo files might live.

    Order matters: PyInstaller-bundled location first, then the local
    project tree (handy when running ``python ramp_optimizer.py``
    straight from a clone), then the system fallback.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = []
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS",
                          os.path.dirname(os.path.abspath(sys.executable)))
        dirs.append(os.path.join(bundle, "locale"))
    dirs.append(os.path.join(here, "locale"))
    return dirs


def _load_translations() -> "_gettext.NullTranslations":
    """Build the gettext.translation chain for the active language.

    Falls back to ``NullTranslations`` (identity) if no .mo is found.
    """
    if LANGUAGE == "en":
        return _gettext.NullTranslations()
    for d in _candidate_locale_dirs():
        if os.path.isdir(d):
            try:
                return _gettext.translation(
                    "ramp_optimizer", localedir=d,
                    languages=[LANGUAGE],
                )
            except FileNotFoundError:
                continue
    return _gettext.NullTranslations()


# Cache the active translation object for the current LANGUAGE.  When the
# language changes (via _set_language in ramp_optimizer.py we mirror the
# global), the cache is invalidated lazily on the next ``t`` call.
_active_lang: "str | None" = None
_active_tr: "_gettext.NullTranslations | None" = None


def t(s: str) -> str:
    """Return the localized version of *s*.

    Lookup order:

    1. If ``LANGUAGE == "en"``, return the input unchanged.
    2. Otherwise consult the compiled gettext catalog if one is
       reachable.  This is the path external translation tools edit.
    3. As a fall-back, look up the in-process ``_TRANSLATIONS_ES``
       dict (used during development before
       ``scripts/sync_translations.py`` is run, and as a safety net
       when the .mo file is not bundled).
    4. Pass *s* through unchanged.
    """
    global _active_lang, _active_tr
    if LANGUAGE == "en":
        return s

    if _active_lang != LANGUAGE or _active_tr is None:
        _active_lang = LANGUAGE
        _active_tr = _load_translations()

    catalog_hit = _active_tr.gettext(s)
    if catalog_hit != s:
        return catalog_hit

    return _TRANSLATIONS_ES.get(s, s)
