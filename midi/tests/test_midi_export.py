import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from midi_export import build_midi, lfo_values, note_number


def read_variable_length(data, position):
    value = 0
    while True:
        byte = data[position]
        position += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, position


def parse(data):
    kind, track_count, ppq = struct.unpack(">HHH", data[8:14])
    position = 14
    tracks = []
    for _ in range(track_count):
        assert data[position:position + 4] == b"MTrk"
        length = struct.unpack(">I", data[position + 4:position + 8])[0]
        end = position + 8 + length
        position += 8
        time = 0
        events = []
        while position < end:
            delta, position = read_variable_length(data, position)
            time += delta
            status = data[position]
            if status == 0xFF:
                meta_kind = data[position + 1]
                size, position = read_variable_length(data, position + 2)
                events.append((time, "meta", meta_kind, data[position:position + size]))
                position += size
            else:
                size = 2 if status & 0xF0 in (0xC0, 0xD0) else 3
                events.append((time, "channel", status, data[position + 1:position + size]))
                position += size
        tracks.append(events)
    return kind, ppq, tracks


SPEC = {
    "title": "probe",
    "tempo_bpm": 72,
    "time_signature": [3, 4],
    "markers": [{"at": 3, "text": "denial 0.5"}],
    "tracks": [
        {
            "name": "drone",
            "channel": 1,
            "program": 89,
            "cc": [{"at": 0, "controller": 1, "value": 20}],
            "pitch_bend": [{"at": 1, "value": -400}],
            "notes": [
                {"pitch": "D2", "start": 0, "duration": 6, "velocity": 50},
                {"pitch": "Eb3", "start": 1.5, "duration": 0.5},
            ],
        }
    ],
}


class MidiExportTest(unittest.TestCase):
    def test_note_names(self):
        self.assertEqual(note_number("C4"), 60)
        self.assertEqual(note_number("A4"), 69)
        self.assertEqual(note_number("Eb3"), 51)
        self.assertEqual(note_number("F#-1"), 6)
        self.assertEqual(note_number(42), 42)
        with self.assertRaises(ValueError):
            note_number("H2")
        with self.assertRaises(ValueError):
            note_number("G#9")
        self.assertEqual(note_number("G9"), 127)

    def test_round_trip(self):
        data = build_midi(SPEC)
        self.assertEqual(data[:4], b"MThd")
        kind, ppq, tracks = parse(data)
        self.assertEqual((kind, ppq, len(tracks)), (1, 480, 2))

        conductor = tracks[0]
        tempo = next(e for e in conductor if e[1] == "meta" and e[2] == 0x51)
        self.assertEqual(int.from_bytes(tempo[3], "big"), round(60_000_000 / 72))
        meter = next(e for e in conductor if e[1] == "meta" and e[2] == 0x58)
        self.assertEqual(tuple(meter[3][:2]), (3, 2))
        marker = next(e for e in conductor if e[1] == "meta" and e[2] == 0x06)
        self.assertEqual((marker[0], marker[3]), (1440, b"denial 0.5"))

        drone = tracks[1]
        channel_events = [e for e in drone if e[1] == "channel"]
        self.assertIn((0, "channel", 0xC1, bytes([89])), channel_events)
        self.assertIn((0, "channel", 0xB1, bytes([1, 20])), channel_events)
        bend = next(e for e in channel_events if e[2] == 0xE1)
        self.assertEqual((bend[3][0] | bend[3][1] << 7) - 8192, -400)
        note_ons = [(e[0], e[3][0], e[3][1]) for e in channel_events if e[2] == 0x91]
        note_offs = [(e[0], e[3][0]) for e in channel_events if e[2] == 0x81]
        self.assertEqual(note_ons, [(0, 38, 50), (720, 51, 80)])
        self.assertEqual(sorted(note_offs), [(960, 51), (2880, 38)])
        self.assertEqual(drone[-1][1:3], ("meta", 0x2F))

    def test_pan_lfo(self):
        sweep = list(lfo_values({"controller": 10, "start": 0, "end": 8, "period": 8, "shape": "sine", "step": 1}))
        self.assertEqual(sweep[0], (0, 0))
        self.assertEqual(sweep[4], (4, 127))
        self.assertEqual(sweep[8], (8, 0))
        self.assertEqual(len(sweep), 9)
        triangle = dict(lfo_values({"controller": 10, "start": 0, "end": 4, "period": 4, "shape": "triangle", "step": 1, "low": 20, "high": 100}))
        self.assertEqual((triangle[0], triangle[2], triangle[4]), (20, 100, 20))
        held = [v for _, v in lfo_values({"controller": 10, "start": 0, "end": 3.75, "period": 2, "shape": "random", "step": 0.25, "seed": 7})]
        self.assertEqual(len(set(held[:4])), 1)
        self.assertEqual(held, [v for _, v in lfo_values({"controller": 10, "start": 0, "end": 3.75, "period": 2, "shape": "random", "step": 0.25, "seed": 7})])

        spec = {"tracks": [{"name": "pad", "channel": 2, "cc_lfo": [{"controller": 10, "start": 0, "end": 2, "period": 2, "step": 1}]}]}
        _, _, tracks = parse(build_midi(spec))
        pans = [(e[0], e[3][1]) for e in tracks[1] if e[1] == "channel" and e[2] == 0xB2 and e[3][0] == 10]
        self.assertEqual(pans, [(0, 0), (480, 127), (960, 0)])


if __name__ == "__main__":
    unittest.main()
