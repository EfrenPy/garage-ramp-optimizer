## Summary

<!-- One or two sentences describing the change. -->

## Why

<!-- Optional: motivation. Link to the issue this fixes / closes. -->

Fixes #

## Test plan

- [ ] `python -m py_compile ramp_optimizer.py build_exe.py` is clean.
- [ ] Ran `python ramp_optimizer.py 136 540` (or other inputs) end-to-end.
- [ ] Generated blueprints look right (PNG and PDF).
- [ ] If user-visible strings changed, the Spanish translation
      dictionary in `ramp_optimizer.py` is up to date.
- [ ] If new dependencies were added, `requirements.txt`, `README.md`
      and `CONTRIBUTING.md` reflect them.
- [ ] No build artifacts staged (`dist/`, `build/`, `*.spec`,
      `__pycache__/`, generated `ramp_blueprint*` PNG/PDF or
      `ramp_offsets*.csv`).

## Notes for the reviewer

<!-- Anything subtle, edge cases handled or knowingly out of scope. -->
