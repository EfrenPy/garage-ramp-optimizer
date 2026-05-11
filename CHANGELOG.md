# Changelog

All notable changes to this project are documented here.

The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.2](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.7.1...v0.7.2) (2026-05-11)


### Miscellaneous Chores

* ship dependabot CI action bumps (v0.7.2) ([7c69d3e](https://github.com/EfrenPy/garage-ramp-optimizer/commit/7c69d3ec3c71f221ef736e0ca2b92b9b73dbad34))

## [0.7.1](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.7.0...v0.7.1) (2026-05-09)


### Bug Fixes

* **optimizer:** run search_smooth with three RNG seeds and keep the best ([5d13647](https://github.com/EfrenPy/garage-ramp-optimizer/commit/5d13647937a9c3b28a61c7020ea340e713b2c2c9))

## [0.7.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.6.0...v0.7.0) (2026-05-09)


### Features

* **gui:** 2-column inputs, smaller-screen sizing, output-format toggles ([849ad15](https://github.com/EfrenPy/garage-ramp-optimizer/commit/849ad15ba0b939a9dcd8961f8e966ec629c41e56))


### Bug Fixes

* **blueprints:** give the wall-reference smooth blueprint room below the plot ([80b8c8e](https://github.com/EfrenPy/garage-ramp-optimizer/commit/80b8c8e030338ef4b5efeb3df77320c486d1b5be))

## [0.6.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.5.0...v0.6.0) (2026-05-09)


### Features

* **cost:** concrete-volume estimator for each profile ([15522e9](https://github.com/EfrenPy/garage-ramp-optimizer/commit/15522e909891db6ac6a228315d2686aaca96618b))
* **gui:** live preview of the linear ramp profile ([ffdf68c](https://github.com/EfrenPy/garage-ramp-optimizer/commit/ffdf68c1107a60a2853ff3414456624ce97587f7))
* let the user pick which profile searches to run ([13165b9](https://github.com/EfrenPy/garage-ramp-optimizer/commit/13165b9a4b8a439e807d405a2d203ccff5da3d58))

## [0.5.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.4.2...v0.5.0) (2026-05-09)


### Features

* parallelize every profile search and bump GUI legibility ([bf2d5af](https://github.com/EfrenPy/garage-ramp-optimizer/commit/bf2d5afcb3b33734979d75197dea432f4bba56d1))

## [0.4.2](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.4.1...v0.4.2) (2026-05-09)


### Bug Fixes

* **blueprints:** give the floor-reference smooth blueprint room below the plot ([f316b88](https://github.com/EfrenPy/garage-ramp-optimizer/commit/f316b8885038bd2b03627b9486e5df767adad56a))

## [0.4.1](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.4.0...v0.4.1) (2026-05-09)


### Bug Fixes

* **optimizer:** make smooth-curve search bit-for-bit reproducible ([f2ed23c](https://github.com/EfrenPy/garage-ramp-optimizer/commit/f2ed23c34875d9f4fc5de31741ce6f6bc6b3ae1a))

## [0.4.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.3.0...v0.4.0) (2026-05-08)


### Features

* **i18n:** localize the output filenames in Spanish builds ([cbe6e55](https://github.com/EfrenPy/garage-ramp-optimizer/commit/cbe6e5589f054ba59d2486c7e1e8c6c851c8caff))

## [0.3.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.2.0...v0.3.0) (2026-05-08)


### Features

* **blueprints:** add floor-reference smooth-curve blueprint (PNG + PDF) ([c757e9b](https://github.com/EfrenPy/garage-ramp-optimizer/commit/c757e9bbea29fc2b0dea65f1f768984735b16bed))


### Documentation

* add codecov badge to README ([eeb87bf](https://github.com/EfrenPy/garage-ramp-optimizer/commit/eeb87bf8f16bd05d8595898afd286e2a4b6d3341))

## [0.2.0](https://github.com/EfrenPy/garage-ramp-optimizer/compare/v0.1.0...v0.2.0) (2026-05-08)


### Features

* add pytest suite, fix annotate() bug, expand README ([9301a88](https://github.com/EfrenPy/garage-ramp-optimizer/commit/9301a88db89da30743bf85c4ca9ba7fc78249f9b))
* **i18n:** generate gettext catalog (.po/.mo) from the translation dict ([e4529f9](https://github.com/EfrenPy/garage-ramp-optimizer/commit/e4529f966cf91f0fd27f8ba04d2790ff9054acf6))
* ship rampa.exe with a custom icon and a real GUI screenshot ([30d3dce](https://github.com/EfrenPy/garage-ramp-optimizer/commit/30d3dce54734a8414c4a1b89896b31d5fc9c9dff))


### Documentation

* add MkDocs Material site, release-please workflow, code-signing notes ([ebca0d1](https://github.com/EfrenPy/garage-ramp-optimizer/commit/ebca0d10ab43a24cac9cad6427ca59818488f7a3))

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
