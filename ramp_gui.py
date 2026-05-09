"""
ramp_gui
========

Tkinter front-end for ``ramp_optimizer``.  Kept in its own module so
``ramp_optimizer.py`` can stay focused on the optimisation maths and the
``compute_and_save`` orchestration.

The GUI is launched via :func:`launch_gui`, which is invoked when the
program is started without command-line arguments (including the
"double-click rampa.exe" path used by the PyInstaller .exe build).
"""

from __future__ import annotations

import math
import os
import sys

# We need a handful of symbols from the main module.  Importing them at
# function-call time (inside :func:`launch_gui`) instead of at module
# import time keeps the dependency one-way: ``ramp_optimizer`` imports
# this module lazily from its ``__main__`` block, so we must NOT import
# ``ramp_optimizer`` at the top level here or we would create a cycle.


def launch_gui() -> None:
    """Interfaz grafica (Tkinter).  Se usa cuando se ejecuta el programa
    sin argumentos por linea de comandos (incluyendo el caso 'doble click
    sobre rampa.exe' del compilado con PyInstaller --windowed)."""
    import contextlib
    import platform
    import queue
    import subprocess
    import threading
    import tkinter as tk
    import webbrowser
    from tkinter import filedialog, messagebox, ttk

    # Late imports break the would-be circular dependency between
    # ``ramp_optimizer`` (which imports this module's ``launch_gui`` at
    # ``__main__`` time) and this file.
    from ramp_optimizer import (
        Car,
        HAS_PLT,
        Ramp,
        _output_name,
        compute_and_save,
        t,
    )

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

    # Responsive window: target a comfortable size, but never larger than
    # ~92 % of the available screen so the window always fits.  A minsize
    # keeps the controls usable when the user shrinks the window.
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    target_w = min(960, max(720, int(sw * 0.92)))
    target_h = min(960, max(620, int(sh * 0.90)))
    pos_x = max(0, (sw - target_w) // 2)
    pos_y = max(0, (sh - target_h) // 2 - 24)
    root.geometry(f"{target_w}x{target_h}+{pos_x}+{pos_y}")
    root.minsize(640, 560)

    # Slightly larger Tk scaling so every widget (including dialogs and
    # menus that ttk does not theme) renders at a comfortable size on
    # both standard- and high-DPI screens.
    try:
        root.tk.call("tk", "scaling", 1.30)
    except tk.TclError:
        pass

    # Base font sizes used everywhere in the GUI.  Bumping these is the
    # single knob that makes every label / entry / button text larger.
    BASE_FONT      = ("Segoe UI", 12)
    BASE_FONT_BOLD = ("Segoe UI", 12, "bold")
    SMALL_FONT     = ("Segoe UI", 11)
    HEADER_FONT    = ("Segoe UI", 20, "bold")
    MONO_FONT      = ("Consolas", 11)

    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    # Make every ttk widget pick up the larger base font.  We cover the
    # specific styles we use in addition to the catch-all "." pattern,
    # because some platforms (notably the "vista" theme on Windows) ignore
    # the catch-all for certain widgets.
    style.configure(".", font=BASE_FONT)
    style.configure("TLabel", font=BASE_FONT)
    style.configure("TLabelframe.Label", font=BASE_FONT_BOLD)
    style.configure("TButton", font=BASE_FONT)
    style.configure("TEntry", font=BASE_FONT)
    style.configure("TCheckbutton", font=BASE_FONT)

    # ---- Header --------------------------------------------------------- #
    header = ttk.Frame(root, padding=(14, 12, 14, 4))
    header.pack(fill="x")
    ttk.Label(header, text=t("Garage Ramp Optimizer"),
              font=HEADER_FONT).pack(anchor="w")
    ttk.Label(header, text=t("Author: {name}").format(name=AUTHOR),
              font=BASE_FONT).pack(anchor="w", pady=(4, 0))
    link = tk.Label(header, text=URL, fg="#1565c0", cursor="hand2",
                    font=("Segoe UI", 12, "underline"))
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

    # ---- Live linear-ramp preview -------------------------------------- #
    # A small embedded matplotlib canvas that re-renders the linear
    # baseline ramp every time the user edits rise or run (debounced by
    # 200 ms).  This gives instant visual feedback that the geometry the
    # user typed in is sane, without having to wait for a full
    # optimisation pass.  It is purely a sanity-check view: the curved
    # / piecewise profiles are only computed when the user clicks
    # "Calculate".
    preview_ok = HAS_PLT
    preview_canvas = None
    preview_ax = None
    if preview_ok:
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            preview_ok = False

    if preview_ok:
        preview_frame = ttk.LabelFrame(
            root, text=t("Live preview (linear ramp)"), padding=4,
        )
        preview_frame.pack(fill="x", padx=14, pady=(2, 4))
        preview_fig = Figure(figsize=(8, 1.9), dpi=100)
        preview_ax = preview_fig.add_subplot(111)
        preview_canvas = FigureCanvasTkAgg(preview_fig, master=preview_frame)
        preview_canvas.get_tk_widget().pack(fill="x", expand=False)

    _preview_after_id = [None]

    def _redraw_preview() -> None:
        if not preview_ok:
            return
        try:
            rise_v = float(desnivel_var.get().strip().replace(",", "."))
            run_v = float(longitud_var.get().strip().replace(",", "."))
        except ValueError:
            return
        if rise_v <= 0 or run_v <= 0:
            return
        ax = preview_ax
        ax.clear()
        # Garage floor + street stubs.
        ax.plot([-100, 0], [0, 0], "k-", linewidth=1.6)
        ax.plot([run_v, run_v + 100], [rise_v, rise_v], "k-",
                linewidth=1.6)
        # The linear ramp itself.
        ax.plot([0, run_v], [0, rise_v], color="tab:red",
                linewidth=2.6, label=t("Linear ramp"))
        ax.scatter([0, run_v], [0, rise_v], color="tab:red", s=35,
                   zorder=5)
        ax.set_aspect("equal")
        ax.set_xlim(-120, run_v + 120)
        ax.set_ylim(-12, rise_v + 18)
        ax.grid(True, alpha=0.3)
        grade_pct = 100.0 * rise_v / run_v
        grade_deg = math.degrees(math.atan2(rise_v, run_v))
        ax.set_title(
            t("rise {r:.0f} cm,  run {n:.0f} cm   "
              "({pct:.1f} %,  {deg:.1f} degrees)").format(
                r=rise_v, n=run_v, pct=grade_pct, deg=grade_deg,
            ),
            fontsize=10,
        )
        ax.set_xlabel(t("x (cm)"), fontsize=9)
        ax.set_ylabel(t("y (cm)"), fontsize=9)
        ax.tick_params(labelsize=8)
        preview_fig.tight_layout()
        preview_canvas.draw_idle()

    def _schedule_preview(*_a) -> None:
        if not preview_ok:
            return
        if _preview_after_id[0] is not None:
            try:
                root.after_cancel(_preview_after_id[0])
            except tk.TclError:
                pass
        _preview_after_id[0] = root.after(200, _redraw_preview)

    if preview_ok:
        desnivel_var.trace_add("write", _schedule_preview)
        longitud_var.trace_add("write", _schedule_preview)
        # Render the initial preview right after Tk has measured the
        # main window so the canvas picks up the correct width.
        root.after(50, _redraw_preview)

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

    # ---- Concrete cost estimator (optional) ---------------------------- #
    # Both fields are optional: leave them empty to skip the cost report.
    cost_frame = ttk.LabelFrame(
        root,
        text=t("Concrete cost estimator (optional)"),
        padding=10,
    )
    cost_frame.pack(fill="x", padx=14, pady=4)

    ttk.Label(cost_frame, text=t("Ramp width:")).grid(
        row=0, column=0, sticky="e", padx=6, pady=4)
    ramp_width_var = tk.StringVar(value="")
    ttk.Entry(cost_frame, textvariable=ramp_width_var,
              width=10, justify="right").grid(
        row=0, column=1, sticky="w", padx=4, pady=4)
    ttk.Label(cost_frame, text="cm").grid(
        row=0, column=2, sticky="w", padx=2, pady=4)

    ttk.Label(cost_frame, text=t("Concrete cost per m^3:")).grid(
        row=1, column=0, sticky="e", padx=6, pady=4)
    cost_var = tk.StringVar(value="")
    ttk.Entry(cost_frame, textvariable=cost_var,
              width=10, justify="right").grid(
        row=1, column=1, sticky="w", padx=4, pady=4)

    currency_var = tk.StringVar(value="EUR")
    ttk.Entry(cost_frame, textvariable=currency_var,
              width=6, justify="left").grid(
        row=1, column=2, sticky="w", padx=2, pady=4)
    ttk.Label(
        cost_frame,
        text=t("(leave width or cost empty to skip the cost report)"),
        font=SMALL_FONT, foreground="#666",
    ).grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(2, 0))

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
              font=BASE_FONT_BOLD).pack(side="left", padx=(0, 12))
    status_var = tk.StringVar(
        value=t("Ready. Enter the data and click Calculate."))
    ttk.Label(action_frame, textvariable=status_var,
              font=("Segoe UI", 12, "italic")).pack(side="left")

    # Elapsed-time line.
    time_frame = ttk.Frame(root, padding=(14, 0))
    time_frame.pack(fill="x")
    time_var = tk.StringVar(value="")
    ttk.Label(time_frame, textvariable=time_var,
              font=SMALL_FONT, foreground="#444").pack(anchor="w")

    # ---- Output text area ---------------------------------------------- #
    # The text widget uses both vertical and horizontal scrollbars so the
    # tabular output never gets clipped if the window is shrunk to a
    # narrow size.  ``wrap="none"`` preserves the column alignment of the
    # numerical reports.
    results_frame = ttk.LabelFrame(root, text=t("Calculation output"),
                                     padding=4)
    results_frame.pack(fill="both", expand=True, padx=14, pady=(4, 8))
    results_frame.rowconfigure(0, weight=1)
    results_frame.columnconfigure(0, weight=1)

    txt_scroll_y = ttk.Scrollbar(results_frame, orient="vertical")
    txt_scroll_x = ttk.Scrollbar(results_frame, orient="horizontal")
    results_text = tk.Text(
        results_frame, font=MONO_FONT,
        yscrollcommand=txt_scroll_y.set,
        xscrollcommand=txt_scroll_x.set,
        wrap="none", height=18,
    )
    results_text.grid(row=0, column=0, sticky="nsew")
    txt_scroll_y.grid(row=0, column=1, sticky="ns")
    txt_scroll_x.grid(row=1, column=0, sticky="ew")
    txt_scroll_y.config(command=results_text.yview)
    txt_scroll_x.config(command=results_text.xview)

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
        (_trig("Searching all profiles in parallel "
                 "(2-arc, 3-slope, 4-slope, smooth) ..."),
         5,  t("Optimizing all profiles in parallel "
                "(longest step)...")),
        (_trig("Optimal three-segment ramp (two arcs + straight)"),
         62, t("Generating first blueprint (3 slopes)...")),
        (_trig("Optimal three-slope ramp"),
         66, t("Generating 4-slope blueprints...")),
        (_trig("Optimal four-slope ramp"),
         70, t("Generating smooth-curve blueprints...")),
        (_trig("Optimal smooth ramp (PCHIP monotone spline)"),
         74, t("Generating top-reference blueprints...")),
        # The blueprint-progress triggers below match the basename of
        # each generated file; the names switch with the active language
        # (see _OUTPUT_NAMES_*), so we resolve them through
        # ``_output_name`` instead of hard-coding the English strings.
        (_output_name("blueprint_4slope_top", ""),
         78, t("Generating smooth-curve blueprints...")),
        (_output_name("blueprint_smooth_top", ""),
         82, t("Generating cord-reference blueprints...")),
        (_output_name("blueprint_4slope_chord", ""),
         85, t("Generating cord-reference blueprints...")),
        (_output_name("blueprint_smooth_chord", ""),
         88, t("Generating top-reference 3-slope blueprint...")),
        (_output_name("blueprint_3slope_top", ".png"),
         90, t("Computing sensitivity to ramp length...")),
        (_trig("Sensitivity if the ramp is lengthened"),
         92, t("Computing sensitivity to ramp length...")),
        (_output_name("blueprint_compare", ".png"),
         100, t("Done. Blueprints and CSVs generated.")),
    ]

    # Parallel-search completion triggers (any order, each fires once).
    # We bump the bar by a fixed amount per completion so the user gets
    # incremental feedback during the long parallel block.
    parallel_done_triggers = [
        ("  ... " + t("two arcs + straight") + ": done.",
         t("two arcs + straight: done.  Waiting for the rest...")),
        ("  ... " + t("three slopes") + ": done.",
         t("three slopes: done.  Waiting for the rest...")),
        ("  ... " + t("four slopes") + ": done.",
         t("four slopes: done.  Waiting for the rest...")),
        ("  ... " + t("free-form smooth (PCHIP)") + ": done.",
         t("free-form smooth (PCHIP): done.")),
    ]
    parallel_done_remaining = list(parallel_done_triggers)
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

    def _worker(ramp, car, out_dir, ramp_width, cost_per_m3, currency):
        try:
            cwd = os.getcwd()
            os.chdir(out_dir)
            try:
                stream = _GuiStream()
                with contextlib.redirect_stdout(stream), \
                     contextlib.redirect_stderr(stream):
                    compute_and_save(
                        ramp, car,
                        ramp_width_cm=ramp_width,
                        cost_per_m3=cost_per_m3,
                        currency=currency,
                    )
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
                    # Parallel-search completion triggers fire in any
                    # order; bump the bar a bit each time one is matched.
                    for ptrig in list(parallel_done_remaining):
                        if ptrig[0] in payload:
                            cur = int(progress["value"])
                            _set_progress(min(cur + 12, 60), ptrig[1])
                            parallel_done_remaining.remove(ptrig)
                    # Advance the ordered progress bar when the next
                    # expected trigger substring shows up.
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
            # Cost-estimator inputs are optional: blank means "skip".
            ramp_width_v = (_read_float(ramp_width_var, t("Ramp width"))
                            if ramp_width_var.get().strip() else 0.0)
            cost_v = (_read_float(cost_var, t("Cost per m^3"))
                      if cost_var.get().strip() else 0.0)
            currency_v = (currency_var.get().strip() or "EUR")
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
        parallel_done_remaining[:] = list(parallel_done_triggers)
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
            target=_worker,
            args=(ramp, car, out_dir, ramp_width_v, cost_v, currency_v),
            daemon=True,
        )
        thread.start()
        root.after(150, _drain_queue)

    calc_btn.config(command=on_calculate)
    root.mainloop()
