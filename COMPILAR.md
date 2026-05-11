# How to compile `rampa.exe` (Windows)

`ramp_optimizer.py` runs as-is with Python, but if you prefer a single
GUI `.exe` that can be opened with a double-click (no Python visible
to the user), follow these steps. **PyInstaller** bundles the
interpreter and every dependency inside the `.exe`, so there is no
`.bat` and nothing the antivirus typically blocks.

## 1. Requirements

- **Python 3.10 or newer** installed on Windows
  (https://www.python.org/downloads/windows/).  Tick **"Add Python to
  PATH"** during the installation.
- Internet access the first time (so pip can fetch `numpy`, `scipy`,
  `matplotlib` and `pyinstaller`).

## 2. Build the executable

1. Open **`cmd`** (Command Prompt) or **PowerShell**.
2. Navigate to the folder where you cloned this repository, e.g.:

       cd path\to\garage-ramp-optimizer

3. Run the build script.

   - **English UI (default):**

         python build_exe.py

   - **Spanish UI** (everything in the GUI, the console output, the
     plot titles and tables, etc. is in Spanish):

         python build_exe.py --spanish

     `--es` is a short alias.

   The first run will pip-install `numpy`, `scipy`, `matplotlib` and
   `pyinstaller` straight from `requirements.txt`. Expect it to take a
   couple of minutes.

   > **Note**: `scipy` is pinned to `>=1.10,<1.12` in `requirements.txt`.
   > Newer scipy releases changed the differential-evolution
   > implementation enough that the smooth-curve search lands on a
   > worse local optimum (about a 7 mm scrape instead of 1.4 mm) on
   > the default Seat Leon geometry.  If you already have a newer
   > scipy installed system-wide, the build script will downgrade it
   > inside this project's environment for you.

4. When it finishes you will see a banner that reads
   **`OK. Executable created [English UI]:`** (or `[Spanish UI]`) and
   the file lands at:

       dist\rampa.exe

   The resulting binary weighs ~80–120 MB because it ships Python,
   numpy, scipy, matplotlib and Tk inside.

   > **Optional — reduce antivirus false positives**: pass
   > `--rebuild-bootloader` to reinstall PyInstaller from source so
   > the bootloader is compiled locally with your toolchain (instead
   > of using the prebuilt one that ships on PyPI, which many AVs
   > flag by hash):
   >
   >     python build_exe.py --rebuild-bootloader
   >     python build_exe.py --spanish --rebuild-bootloader
   >
   > Requires a C compiler on PATH — Visual Studio Build Tools on
   > Windows (free), `gcc` / `clang` elsewhere.  The official CI
   > release builds already use this flag.  Adds ~1-2 min to the
   > build.

## 3. Use the executable

### GUI mode (recommended)

**Double-click** `dist\rampa.exe`.  The window has:

- Input fields for **rise** (cm) and **horizontal length** of the
  ramp (cm).
- Car parameters: ground clearance, wheelbase, front and rear
  overhangs.  They default to a Seat León FR 2025; tweak them for
  your car.
- Output-folder picker (defaults to the folder containing the
  `.exe`).
- A **"Calculate and generate blueprints"** button.
- A real progress bar (0–100 %) with a numeric percentage label.
- A live **elapsed-time** counter that ticks every second.  The full
  computation usually takes **between 1 and 3 minutes**.
- A scrolling text box that shows the live log of the calculation.
- An **"Open output folder"** button.

A pop-up confirms when the calculation is finished.

### Silent mode (command line)

From `cmd`, pass values directly. **No GUI is opened**, the
blueprints are produced straight to disk.  Useful for automation:

    dist\rampa.exe 136 540

with all the optional car parameters:

    dist\rampa.exe -d 136 -l 540 -c 14 -w 269 -f 87 -r 0

| flag | parameter |
|---|---|
| `-d` / `--desnivel` / `--rise` | rise (cm) |
| `-l` / `--longitud` / `--run` | horizontal length of the ramp (cm) |
| `-c` / `--altura-libre` / `--clearance` | ground clearance (cm) |
| `-w` / `--batalla` / `--wheelbase` | wheelbase / distance between axles (cm) |
| `-f` / `--voladizo-delantero` / `--front-overhang` | front overhang (cm) |
| `-r` / `--voladizo-trasero` / `--rear-overhang` | rear overhang (cm), default 0 |
| `--lang en` / `--lang es` | force English / Spanish output, regardless of how the binary was compiled |

## 4. Outputs

The program writes seven blueprint pairs (each as **PNG** and **PDF**)
plus several CSV tables in the chosen output folder (next to the
`.exe` by default).

### Blueprints

| File | What it shows |
|---|---|
| `ramp_blueprint.png/.pdf` | 3 piecewise slopes, referenced from the start of the ramp (origin (0,0) on the garage floor). |
| `ramp_blueprint_top.png/.pdf` | 3 slopes, referenced from the wall / top of the ramp (cotas `u` horizontal, `d` downward). |
| `ramp_blueprint_top_4slope.png/.pdf` | 4 slopes, referenced from the wall. |
| `ramp_blueprint_top_smooth.png/.pdf` | Smooth (PCHIP) curve, stations every 30 cm along the wall. |
| `ramp_blueprint_chord_4slope.png/.pdf` | 4 slopes, **straight cord T → B as the reference**. Each corner has its `s` (along the cord) and `p` (perpendicular to the cord). |
| `ramp_blueprint_chord_smooth.png/.pdf` | Smooth curve, same cord system, stations every 30 cm. |
| `ramp_profile.png/.pdf` | Side-by-side comparison of the 5 profile families (linear, two arcs + straight, 3 slopes, 4 slopes, smooth). |

The **PDF** copies are vector graphics: zoom in as much as you want
without pixelation.

### CSV tables

| File | Coordinates |
|---|---|
| `ramp_offsets.csv` | (x, y) of the "two arcs + straight" profile, 28 points. |
| `ramp_offsets_3slope.csv` | (x, y) of the 3-slope profile, 28 points. |
| `ramp_offsets_4slope.csv` | (x, y) of the 4-slope profile, 28 points. |
| `ramp_offsets_smooth.csv` | (x, y) of the smooth curve, 40 points. |
| `ramp_offsets_3slope_top.csv` | (u, d, drop-from-wall), wall reference, 3 slopes. |
| `ramp_offsets_4slope_top.csv` | (u, d, drop-from-wall), wall reference, 4 slopes. |
| `ramp_offsets_smooth_top.csv` | (u, d, drop-from-wall), wall reference, smooth curve. |
| `ramp_offsets_4slope_chord.csv` | (s, p), cord reference, 4 slopes. |
| `ramp_offsets_smooth_chord.csv` | (s, p), cord reference, smooth curve. |

## 5. Sign conventions

### Cord-reference system (`*_chord*`)

- **s** = distance along the straight cord T → B, measured from
  **T** (street, top) toward B (garage, bottom).
- **p** = perpendicular distance from the cord to the actual surface.
  - **p > 0** → the surface lies **ABOVE** the cord.
  - **p < 0** → the surface lies **BELOW** the cord (the usual case:
    the ramp dips slightly under a tight cord stretched between the
    two corners).

### Wall-reference system (`*_top*`)

- **u** = horizontal distance measured from the top edge of the ramp
  toward the garage (u = 0 at the street, u = run at the garage).
- **d** = depth below the top plane (d = 0 at street level,
  d = rise at the garage floor).
- **drop from the wall** = vertical distance from the chalk-line on
  the wall (136 cm above the street by default) down to the surface.
  This is the value the worker reads off a tape measure.

## 6. (Optional) Sign the executable

A pristine, never-seen-before `.exe` triggers reputation-based
warnings ("SmartScreen prevented an unrecognized app from
starting...") in Windows.  Signing the binary with a code-signing
certificate makes that warning go away.

### Option 0 — SignPath Foundation (this project's planned path)

For releases produced by **this repo's CI** (not local builds),
the long-term plan is **sponsored Authenticode signing via
[SignPath Foundation](https://signpath.org/)** — free for
qualifying open-source projects, no certificate purchase, no
hardware token.  The application was submitted on 2026-05-11;
once approved, every `rampa-*.exe` attached to a GitHub Release
will ship pre-signed.  **Local builds done by following this
guide remain unsigned** — the CI signing only applies to the
binaries the maintainer attaches to a GitHub Release.

Background, application checklist and the post-approval
flip-the-switch steps are in
[`docs/SIGNPATH.md`](docs/SIGNPATH.md).  The CI wiring is
pre-staged on the `signpath/wire-up` branch and is **not** merged
to `main` yet.

End-users who want to verify the signature on a CI-released
`.exe` once signing is live: see the
[Verifying the Windows signature](README.md#verifying-the-windows-signature)
section of the README.

### Option A — paid certificate (proper fix)

1. Buy an OV (Organisation Validation) or EV (Extended Validation)
   code-signing certificate from a CA such as Sectigo, DigiCert or
   SSL.com.  Expect ~120 €/year for OV, more for EV.
2. After the CA validates your identity (a few days), they hand you
   a `.pfx` file (or, for EV, a hardware token).
3. Sign the executable with the Microsoft `signtool`:

       signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f path\to\your-cert.pfx /p YOUR_PFX_PASSWORD dist\rampa.exe

   (`signtool` ships with the Windows 10 / 11 SDK.)

4. Verify:

       signtool verify /pa /v dist\rampa.exe

OV signatures still need to build reputation before SmartScreen
trusts them silently; EV signatures are trusted from the first run.

### Option B — self-signed certificate (free, partial fix)

A self-signed cert does **not** clear SmartScreen, but it changes
the warning from "publisher unknown" to your name + an "untrusted
publisher" line, and can be added to the Trusted Publishers store on
machines you control (handy for an internal deployment).

```powershell
# 1. One-time: make a self-signed cert in your Personal store.
$cert = New-SelfSignedCertificate `
    -Type CodeSigningCert `
    -Subject "CN=Efrén Rodríguez Rodríguez" `
    -CertStoreLocation Cert:\CurrentUser\My `
    -KeyUsage DigitalSignature `
    -KeyExportPolicy Exportable `
    -NotAfter (Get-Date).AddYears(3)

# 2. Export to a .pfx (you set the password the first time).
$pwd = ConvertTo-SecureString -String "YOUR_PFX_PASSWORD" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath rampa-codesign.pfx -Password $pwd

# 3. Sign every build:
& "C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe" `
    sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    /f rampa-codesign.pfx /p YOUR_PFX_PASSWORD `
    dist\rampa.exe
```

### Option C — do nothing

For a hobby tool that's downloaded by a handful of users, the
practical workaround is "click `More info` → `Run anyway`" the first
time, or whitelist `dist\rampa.exe` in the antivirus.  The release
notes already document that.

## 7. If the antivirus blocks `rampa.exe`

Some antiviruses flag PyInstaller-built executables as suspicious by
reputation (any uncommon `.exe` can trigger a warning).  Workarounds:

- Add the `dist\` folder to the antivirus' exclusion list.
- Or run the script directly with Python without compiling:

      python ramp_optimizer.py

  (no arguments → GUI; with arguments → silent mode).

## 8. Advanced configuration

If you want to tune the plots beyond the GUI flags, edit these
constants in `ramp_optimizer.py`:

- **Wall height above the street** (default 136 cm).  Look for
  `WALL_OFFSET = 136.0` inside `compute_and_save`.
- **Station spacing** for the smooth profile (default 30 cm).  Look
  for `station_step_cm=30.0` in the calls to
  `draw_smooth_blueprint_topref` and `draw_chord_blueprint`.

After editing, rebuild with `python build_exe.py` (add `--spanish` if
you want Spanish output).

---

## Author

**Efrén Rodríguez Rodríguez**
Personal website: <https://efrenrodriguezrodriguez.com/>
