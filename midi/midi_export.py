import argparse
import json
import math
import random
import re
import struct
import sys
from pathlib import Path

NOTE_OFFSETS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
NOTE_PATTERN = re.compile(r"^([A-Ga-g])([#b]*)(-?\d+)$")
DEFAULT_PPQ = 480
DEFAULT_VELOCITY = 80
DEFAULT_LFO_STEP = 0.125
META_TRACK_NAME = 0x03
META_TEMPO = 0x51
META_TIME_SIGNATURE = 0x58
META_MARKER = 0x06
META_END_OF_TRACK = 0x2F


def note_number(pitch):
    if isinstance(pitch, int):
        number = pitch
    else:
        match = NOTE_PATTERN.match(pitch.strip())
        if not match:
            raise ValueError(f"unreadable pitch: {pitch!r}")
        letter, accidentals, octave = match.groups()
        number = NOTE_OFFSETS[letter.upper()] + accidentals.count("#") - accidentals.count("b")
        number += (int(octave) + 1) * 12
    if not 0 <= number <= 127:
        raise ValueError(f"pitch out of MIDI range: {pitch!r}")
    return number


def variable_length(value):
    buffer = [value & 0x7F]
    value >>= 7
    while value:
        buffer.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(buffer))


def meta_event(kind, payload):
    return bytes([0xFF, kind]) + variable_length(len(payload)) + payload


def ticks(beats, ppq):
    return round(beats * ppq)


def tempo_payload(bpm):
    return struct.pack(">I", round(60_000_000 / bpm))[1:]


def time_signature_payload(numerator, denominator):
    return bytes([numerator, denominator.bit_length() - 1, 24, 8])


def encode_track(events):
    events.sort(key=lambda event: (event[0], event[1]))
    body = bytearray()
    previous = 0
    for time, _, data in events:
        body += variable_length(time - previous) + data
        previous = time
    body += variable_length(0) + meta_event(META_END_OF_TRACK, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def conductor_events(spec, ppq):
    events = [(0, 0, meta_event(META_TRACK_NAME, spec.get("title", "untitled").encode("utf-8")))]
    numerator, denominator = spec.get("time_signature", [4, 4])
    events.append((0, 0, meta_event(META_TIME_SIGNATURE, time_signature_payload(numerator, denominator))))
    tempo_changes = spec.get("tempo_changes", [])
    events.append((0, 0, meta_event(META_TEMPO, tempo_payload(spec.get("tempo_bpm", 120)))))
    for change in tempo_changes:
        events.append((ticks(change["at"], ppq), 0, meta_event(META_TEMPO, tempo_payload(change["bpm"]))))
    for marker in spec.get("markers", []):
        events.append((ticks(marker["at"], ppq), 0, meta_event(META_MARKER, marker["text"].encode("utf-8"))))
    return events


def lfo_shape(shape, phase, rng):
    phase %= 1.0
    if shape == "sine":
        return 0.5 - 0.5 * math.cos(2 * math.pi * phase)
    if shape == "triangle":
        return 1 - abs(2 * phase - 1)
    if shape == "square":
        return 1.0 if phase < 0.5 else 0.0
    if shape == "random":
        return rng.random()
    raise ValueError(f"unknown lfo shape: {shape!r}")


def lfo_values(lfo):
    rng = random.Random(lfo.get("seed", 0))
    step = lfo.get("step", DEFAULT_LFO_STEP)
    low, high = lfo.get("low", 0), lfo.get("high", 127)
    shape = lfo.get("shape", "sine")
    position, held, held_cycle = lfo["start"], 0.0, None
    while position <= lfo["end"] + 1e-9:
        phase = (position - lfo["start"]) / lfo["period"] + lfo.get("phase", 0.0)
        if shape == "random":
            cycle = math.floor(phase * 2)
            if cycle != held_cycle:
                held, held_cycle = rng.random(), cycle
            level = held
        else:
            level = lfo_shape(shape, phase, rng)
        yield position, max(0, min(127, round(low + (high - low) * level)))
        position += step


def instrument_events(track, ppq):
    channel = track.get("channel", 0)
    if not 0 <= channel <= 15:
        raise ValueError(f"channel out of range in track {track.get('name')!r}")
    events = [(0, 0, meta_event(META_TRACK_NAME, track.get("name", "track").encode("utf-8")))]
    if "program" in track:
        events.append((0, 1, bytes([0xC0 | channel, track["program"]])))
    for move in track.get("cc", []):
        events.append((ticks(move["at"], ppq), 1, bytes([0xB0 | channel, move["controller"], move["value"]])))
    for lfo in track.get("cc_lfo", []):
        for at, value in lfo_values(lfo):
            events.append((ticks(at, ppq), 1, bytes([0xB0 | channel, lfo["controller"], value])))
    for bend in track.get("pitch_bend", []):
        value = max(0, min(16383, bend["value"] + 8192))
        events.append((ticks(bend["at"], ppq), 1, bytes([0xE0 | channel, value & 0x7F, value >> 7])))
    for note in track.get("notes", []):
        pitch = note_number(note["pitch"])
        start = ticks(note["start"], ppq)
        end = start + max(1, ticks(note["duration"], ppq))
        velocity = note.get("velocity", DEFAULT_VELOCITY)
        events.append((start, 2, bytes([0x90 | channel, pitch, velocity])))
        events.append((end, 0, bytes([0x80 | channel, pitch, 0])))
    return events


def build_midi(spec):
    ppq = spec.get("ppq", DEFAULT_PPQ)
    chunks = [encode_track(conductor_events(spec, ppq))]
    chunks += [encode_track(instrument_events(track, ppq)) for track in spec["tracks"]]
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), ppq)
    return header + b"".join(chunks)


def export(spec_path, out_path=None):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    out_path = Path(out_path) if out_path else Path(spec_path).with_suffix(".mid")
    out_path.write_bytes(build_midi(spec))
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Write a Type 1 MIDI file from a JSON spec.")
    parser.add_argument("specs", nargs="+", help="JSON spec files")
    parser.add_argument("--out", help="output path, only with a single spec")
    args = parser.parse_args()
    if args.out and len(args.specs) > 1:
        sys.exit("--out takes a single spec")
    for spec_path in args.specs:
        print(export(spec_path, args.out))


if __name__ == "__main__":
    main()
