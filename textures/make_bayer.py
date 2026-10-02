import argparse
import struct
import zlib
from pathlib import Path


def bayer(size):
    matrix = [[0]]
    while len(matrix) < size:
        n = len(matrix)
        grown = [[0] * (n * 2) for _ in range(n * 2)]
        for y in range(n):
            for x in range(n):
                value = matrix[y][x] * 4
                grown[y][x] = value
                grown[y][x + n] = value + 2
                grown[y + n][x] = value + 3
                grown[y + n][x + n] = value + 1
        matrix = grown
    return matrix


def write_png(path, rows):
    height, width = len(rows), len(rows[0])
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def main():
    parser = argparse.ArgumentParser(description="Write an ordered-dither (Bayer) threshold texture as a grayscale PNG.")
    parser.add_argument("--size", type=int, default=8, choices=[2, 4, 8, 16])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    matrix = bayer(args.size)
    levels = args.size * args.size
    rows = [[round((value + 0.5) / levels * 255) for value in row] for row in matrix]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_png(args.out, rows)
    print(f"wrote {args.out} ({args.size}x{args.size}, {levels} levels)")


if __name__ == "__main__":
    main()
