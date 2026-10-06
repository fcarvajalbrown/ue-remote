import argparse
import os
import struct


def riff_spans(data):
    spans = []
    start = 0
    while True:
        idx = data.find(b"RIFF", start)
        if idx < 0:
            break
        start = idx + 4
        if len(data) < idx + 12 or data[idx + 8:idx + 12] != b"WAVE":
            continue
        declared = struct.unpack_from("<I", data, idx + 4)[0]
        end = idx + 8 + declared
        if end > len(data) or declared < 36:
            continue
        if data[idx + 12:idx + 16] != b"fmt ":
            continue
        spans.append((idx, end))
        start = end
    return spans


def wav_info(data, begin):
    fmt_size = struct.unpack_from("<I", data, begin + 16)[0]
    audio_format, channels, rate, _, _, bits = struct.unpack_from("<HHIIHH", data, begin + 20)
    return audio_format, channels, rate, bits, fmt_size


def walk_uassets(root):
    for dirpath, _, names in os.walk(root):
        for name in names:
            if name.lower().endswith(".uasset"):
                yield os.path.join(dirpath, name)


def main():
    ap = argparse.ArgumentParser(description="Cut embedded PCM WAV files out of Unreal .uasset sound waves without a decoder.")
    ap.add_argument("source", help="folder of extracted .uasset files")
    ap.add_argument("out", help="folder to write .wav files into")
    args = ap.parse_args()

    written = 0
    skipped = []
    for path in walk_uassets(args.source):
        with open(path, "rb") as fh:
            data = fh.read()
        spans = riff_spans(data)
        if not spans:
            continue
        rel = os.path.relpath(os.path.dirname(path), args.source)
        stem = os.path.splitext(os.path.basename(path))[0]
        dest_dir = os.path.join(args.out, rel)
        for i, (begin, end) in enumerate(spans):
            audio_format, channels, rate, bits, _ = wav_info(data, begin)
            if audio_format != 1:
                skipped.append(f"{stem} audioFormat={audio_format}")
                continue
            os.makedirs(dest_dir, exist_ok=True)
            name = stem if len(spans) == 1 else f"{stem}_{i}"
            with open(os.path.join(dest_dir, name + ".wav"), "wb") as out:
                out.write(data[begin:end])
            written += 1
    print(f"wav written: {written}")
    for s in skipped:
        print(f"skipped (not PCM): {s}")


if __name__ == "__main__":
    main()
