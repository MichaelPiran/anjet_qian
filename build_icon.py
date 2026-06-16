from __future__ import annotations

import argparse
import struct
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un file ICO partendo da un PNG esistente."
    )
    parser.add_argument("source", type=Path, help="Percorso del PNG sorgente.")
    parser.add_argument("target", type=Path, help="Percorso del file ICO di output.")
    return parser.parse_args()


def read_png_size(payload: bytes) -> tuple[int, int]:
    if not payload.startswith(PNG_SIGNATURE):
        raise SystemExit("Il file sorgente deve essere un PNG valido.")
    if payload[12:16] != b"IHDR":
        raise SystemExit("Chunk IHDR mancante nel PNG sorgente.")
    width, height = struct.unpack(">II", payload[16:24])
    return width, height


def png_to_ico(source: Path, target: Path) -> None:
    payload = source.read_bytes()
    width, height = read_png_size(payload)
    if width > 256 or height > 256:
        raise SystemExit("L'icona PNG deve avere larghezza e altezza massime di 256 pixel.")

    icon_width = 0 if width == 256 else width
    icon_height = 0 if height == 256 else height

    header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack(
        "<BBBBHHII",
        icon_width,
        icon_height,
        0,
        0,
        1,
        32,
        len(payload),
        6 + 16,
    )

    target.write_bytes(header + directory + payload)


def main() -> None:
    args = parse_args()
    args.target.parent.mkdir(parents=True, exist_ok=True)
    png_to_ico(args.source, args.target)


if __name__ == "__main__":
    main()
