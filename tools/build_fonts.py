"""Builds the font files bundled with the app (T1.1, decision 121).

Circle labels must look the same on Windows and Mac, so the app ships its own
font files and does not use system fonts or load fonts from a font service.
Each file is cut from an open-licence font (SIL OFL 1.1): one weight, only the
characters the app needs (digits, Latin, the Ukrainian alphabet, punctuation).
The modified files get their own family name ("... TMT"), and the licence of
each font is copied next to it.

Why these fonts: the digit 3 has a flat top, so it differs from the letter З
(decision 121). In Inter that shape is the alternate "cv09"; here it is made
the default 3, so nothing depends on browser support for font features.

Sources (https://github.com/google/fonts, folder ofl/<name>/):
    inter/Inter[opsz,wght].ttf            Version 4.001
    montserrat/Montserrat[wght].ttf       Version 9.000
    arsenal/Arsenal-Bold.ttf              Version 2.000

Needs fonttools and brotli. Usage, from app/:
    python tools/build_fonts.py <folder with the downloaded ofl/ subfolders>
Writes src/fonts/*.woff2, the licences and src/fonts/fonts.json.
"""

import json
import shutil
import sys
from pathlib import Path

from fontTools import subset
from fontTools.pens.boundsPen import BoundsPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

OUT = Path(__file__).resolve().parent.parent / "src" / "fonts"

UKRAINIAN = "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"
CHARS = (
    "".join(chr(c) for c in range(0x20, 0x7F))
    + UKRAINIAN + UKRAINIAN.lower()
    + " «»’–—…№"
)

FONTS = [
    {
        "id": "inter",
        "family": "Inter TMT",
        "label": "Inter",
        "source": "inter/Inter[opsz,wght].ttf",
        "axes": {"wght": 500, "opsz": 14},
        "weight": 500,
        "remap": {"3": "three.1"},  # cv09, flat-top three
    },
    {
        "id": "montserrat",
        "family": "Montserrat TMT",
        "label": "Montserrat",
        "source": "montserrat/Montserrat[wght].ttf",
        "axes": {"wght": 500},
        "weight": 500,
    },
    {
        "id": "arsenal",
        "family": "Arsenal TMT",
        "label": "Arsenal",
        "source": "arsenal/Arsenal-Bold.ttf",
        "weight": 700,
    },
]


def glyph_height(font, char):
    """Top of the glyph above the baseline, as a share of the em."""
    glyphs = font.getGlyphSet()
    pen = BoundsPen(glyphs)
    glyphs[font.getBestCmap()[ord(char)]].draw(pen)
    return pen.bounds[3] / font["head"].unitsPerEm


def build(spec, sources):
    font = TTFont(sources / spec["source"])
    version = font["name"].getDebugName(5)
    if "fvar" in font:
        font = instancer.instantiateVariableFont(font, spec["axes"])
    for char, glyph in spec.get("remap", {}).items():
        for table in font["cmap"].tables:
            if ord(char) in table.cmap:
                table.cmap[ord(char)] = glyph

    options = subset.Options()
    options.layout_features = ["kern", "locl", "ccmp", "mark", "mkmk"]
    options.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
    options.notdef_outline = True
    options.hinting = False
    cutter = subset.Subsetter(options)
    cutter.populate(text=CHARS)
    cutter.subset(font)
    missing = [c for c in CHARS if ord(c) not in font.getBestCmap()]
    if missing:
        raise SystemExit(f"{spec['id']}: no glyphs for {''.join(missing)}")

    style = "Regular"
    for record in font["name"].names:
        if record.nameID in (1, 16):
            record.string = spec["family"]
        elif record.nameID in (2, 17):
            record.string = style
        elif record.nameID == 4:
            record.string = spec["family"]
        elif record.nameID == 6:
            record.string = spec["family"].replace(" ", "") + "-" + style
        elif record.nameID == 3:
            record.string = f"{spec['family']} {version}; subset for TMT-UA"

    font.flavor = "woff2"
    target = OUT / f"{spec['id']}.woff2"
    font.save(target)
    shutil.copy(sources / Path(spec["source"]).parent / "OFL.txt", OUT / f"{spec['id']}-OFL.txt")
    return {
        "id": spec["id"],
        "family": spec["family"],
        "label": spec["label"],
        "file": target.name,
        "weight": spec["weight"],
        "source_version": version,
        # Letter and digit height as a share of the font size: lets the app
        # set the size of the letters in mm (font size = height / cap).
        "cap": round(glyph_height(font, "Е"), 4),
        "digit": round(glyph_height(font, "1"), 4),
        "bytes": target.stat().st_size,
    }


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    OUT.mkdir(exist_ok=True)
    fonts = [build(spec, Path(argv[1])) for spec in FONTS]
    (OUT / "fonts.json").write_text(json.dumps({"fonts": fonts}, ensure_ascii=False, indent=1) + "\n")
    for font in fonts:
        print(font)


if __name__ == "__main__":
    main(sys.argv)
