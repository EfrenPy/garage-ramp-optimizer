"""Re-sync the gettext catalogs from ``ramp_i18n._TRANSLATIONS_ES``.

Standard practice is to extract a `.pot` template with ``xgettext`` /
``pybabel``, edit one ``.po`` file per language, and compile each one
to a binary ``.mo`` with ``msgfmt``.

Maintaining that toolchain just to mirror a single Python dict is
overkill for a one-translator project, so we go the other way: the
authoritative source of translations stays the dict in
``ramp_i18n``; this script *generates* the ``.po`` and ``.mo`` files
from it.

That way:

* External tools that expect a real gettext catalog
  (Poedit, Crowdin, Weblate, the GNU gettext API) can read it.
* Translators can patch the ``.po`` directly; running this script
  re-imports their changes into the dict (TODO).
* The build pipeline still ships the ``.mo`` files in the bundled
  ``rampa.exe`` for users who prefer the gettext path at runtime.

Run from the project root:

    python scripts/sync_translations.py

Outputs:

    locale/ramp_optimizer.pot                    (template, English-only)
    locale/es/LC_MESSAGES/ramp_optimizer.po      (English -> Spanish)
    locale/es/LC_MESSAGES/ramp_optimizer.mo      (compiled .po)
"""

from __future__ import annotations

import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ramp_i18n import _TRANSLATIONS_ES  # noqa: E402

LOCALE_DIR = PROJECT / "locale"
DOMAIN = "ramp_optimizer"


def _po_escape(s: str) -> str:
    """Escape *s* for use inside a ``msgid`` / ``msgstr`` string."""
    return (
        s.replace("\\", "\\\\")
         .replace('"', '\\"')
         .replace("\n", "\\n")
         .replace("\t", "\\t")
    )


def _write_po_lines(out_lines: list[str], header: str, value: str) -> None:
    """Append a ``msgid`` / ``msgstr`` block in canonical po formatting."""
    out_lines.append(f'{header} "{_po_escape(value)}"')


def write_pot(path: Path) -> None:
    """Write the gettext template (English-only)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M+0000")
    lines: list[str] = [
        "# Translation template for the garage ramp optimizer.",
        "# Copyright (C) 2026 Efren Rodriguez Rodriguez",
        "# This file is distributed under the same MIT licence as the project.",
        "#",
        "msgid \"\"",
        "msgstr \"\"",
        '"Project-Id-Version: garage-ramp-optimizer 0.1.0\\n"',
        f'"POT-Creation-Date: {now}\\n"',
        '"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"',
        '"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"',
        '"Language-Team: LANGUAGE <LL@li.org>\\n"',
        '"Language: \\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]
    for english in _TRANSLATIONS_ES.keys():
        _write_po_lines(lines, "msgid", english)
        _write_po_lines(lines, "msgstr", "")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")


def write_po(path: Path, lang: str, mapping: dict[str, str]) -> None:
    """Write the language-specific .po file."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M+0000")
    lines: list[str] = [
        f"# Spanish ({lang}) translation for the garage ramp optimizer.",
        "# Copyright (C) 2026 Efren Rodriguez Rodriguez",
        "# This file is distributed under the same MIT licence as the project.",
        "#",
        "msgid \"\"",
        "msgstr \"\"",
        '"Project-Id-Version: garage-ramp-optimizer 0.1.0\\n"',
        f'"POT-Creation-Date: {now}\\n"',
        f'"PO-Revision-Date: {now}\\n"',
        '"Last-Translator: Efren Rodriguez Rodriguez\\n"',
        '"Language-Team: Spanish\\n"',
        f'"Language: {lang}\\n"',
        '"MIME-Version: 1.0\\n"',
        '"Content-Type: text/plain; charset=UTF-8\\n"',
        '"Content-Transfer-Encoding: 8bit\\n"',
        "",
    ]
    for english, spanish in mapping.items():
        _write_po_lines(lines, "msgid", english)
        _write_po_lines(lines, "msgstr", spanish)
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {path}")


def write_mo(po_mapping: dict[str, str], mo_path: Path) -> None:
    """Compile *po_mapping* into a binary .mo file (no msgfmt needed).

    Reference: GNU gettext manual, "The Format of GNU MO Files".
    https://www.gnu.org/software/gettext/manual/html_node/MO-Files.html
    """
    # An empty msgid stores the metadata header.
    header = (
        "Project-Id-Version: garage-ramp-optimizer 0.1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "Content-Transfer-Encoding: 8bit\n"
    )
    items = [("", header)] + sorted(po_mapping.items())

    # Build packed offset tables.
    keys = b"\x00".join(k.encode("utf-8") for k, _v in items)
    values = b"\x00".join(v.encode("utf-8") for _k, v in items)

    # We'll lay out:
    #   [magic] [version] [n_strings] [orig_off] [trans_off] [hash_size=0] [hash_off=0]
    #   [orig_table: (length, offset) per string]
    #   [trans_table: (length, offset) per string]
    #   [original strings, NUL-separated]
    #   [translated strings, NUL-separated]
    n = len(items)
    header_size = 28
    table_size = n * 8

    orig_table_off = header_size
    trans_table_off = orig_table_off + table_size
    strings_start = trans_table_off + table_size

    out = bytearray()
    out += struct.pack(
        "<IIIIIII",
        0x950412de,            # magic (little-endian)
        0,                     # version
        n,
        orig_table_off,
        trans_table_off,
        0,                     # hash table size (none)
        0,                     # hash table offset
    )

    # Build flat string blobs.
    orig_offsets = []
    trans_offsets = []
    orig_blob = bytearray()
    trans_blob = bytearray()
    for k, v in items:
        kb = k.encode("utf-8")
        vb = v.encode("utf-8")
        orig_offsets.append((len(kb), strings_start + len(orig_blob)))
        orig_blob += kb + b"\x00"
        # translated strings live after orig_blob.
        # We patch in the offset once orig_blob is finalised below.
        trans_offsets.append((len(vb), len(trans_blob)))
        trans_blob += vb + b"\x00"

    # Now we know orig_blob length; compute absolute trans offsets.
    trans_base = strings_start + len(orig_blob)
    trans_offsets = [(length, trans_base + rel) for length, rel in trans_offsets]

    # Original-strings table.
    for length, offset in orig_offsets:
        out += struct.pack("<II", length, offset)
    # Translation-strings table.
    for length, offset in trans_offsets:
        out += struct.pack("<II", length, offset)

    out += orig_blob
    out += trans_blob

    mo_path.parent.mkdir(parents=True, exist_ok=True)
    mo_path.write_bytes(out)
    print(f"Wrote {mo_path} ({len(out)} bytes, {n - 1} translated strings)")


def main() -> None:
    write_pot(LOCALE_DIR / f"{DOMAIN}.pot")

    es_dir = LOCALE_DIR / "es" / "LC_MESSAGES"
    write_po(es_dir / f"{DOMAIN}.po", "es", _TRANSLATIONS_ES)
    write_mo(_TRANSLATIONS_ES, es_dir / f"{DOMAIN}.mo")


if __name__ == "__main__":
    main()
