# Changelog

All notable changes to this project are documented here.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-05-08

### Added

- Initial public release.
- Five profile families:
  - linear ramp,
  - two arcs + straight middle,
  - three piecewise slopes,
  - four piecewise slopes (with parallel `differential_evolution`),
  - free-form smooth curve (monotone PCHIP cubic spline, with
    parallel `differential_evolution`).
- Three reference systems for the construction blueprints:
  - origin at the start of the ramp,
  - wall reference (drop from a chalk-line on the side wall),
  - straight cord T → B reference (`s` along the cord, `p`
    perpendicular to it).
- Tkinter GUI with a real progress bar, elapsed-time counter and a
  live log of the calculation.
- Silent CLI mode (`python ramp_optimizer.py 136 540`).
- English UI by default; Spanish opt-in via `--lang es`,
  the `RAMP_LANG=es` environment variable, or by compiling with
  `python build_exe.py --spanish`.
- Pre-built Windows executables `rampa-en.exe` and `rampa-es.exe`
  attached to GitHub Releases by an automated CI workflow.

[Unreleased]: https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/EfrenPy/garage-ramp-optimizer/releases/tag/v0.1.0
