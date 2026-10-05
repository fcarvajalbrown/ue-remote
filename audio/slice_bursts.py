import argparse
import json
import os
import random
import sys

import numpy as np
import soundfile


def rms_envelope(mono, rate, hop_ms):
    hop = max(1, int(rate * hop_ms / 1000))
    frames = len(mono) // hop
    blocks = mono[: frames * hop].reshape(frames, hop)
    return np.sqrt(np.mean(blocks ** 2, axis=1)), hop


def decibels(values):
    return 20.0 * np.log10(np.maximum(values, 1e-9))


def find_bursts(mono, rate, rules):
    energy, hop = rms_envelope(mono, rate, rules["hop_ms"])
    if len(energy) == 0:
        return []
    level = decibels(energy) - decibels(np.array([energy.max()]))[0]
    active = level >= rules["threshold_db"]
    max_gap = int(rules["merge_gap_ms"] / rules["hop_ms"])
    regions = []
    start = None
    quiet = 0
    for index, on in enumerate(active):
        if on:
            if start is None:
                start = index
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet > max_gap:
                regions.append((start, index - quiet + 1))
                start, quiet = None, 0
    if start is not None:
        regions.append((start, len(active) - quiet))
    bursts = []
    for first, last in regions:
        length_ms = (last - first) * rules["hop_ms"]
        if rules["min_length_ms"] <= length_ms <= rules["max_length_ms"]:
            loudness = float(level[first:last].max())
            bursts.append((first * hop, last * hop, length_ms, loudness))
    return bursts


def voiced_fraction(segment, rate, voicing):
    window = int(rate * voicing["window_ms"] / 1000)
    hop = int(rate * voicing["hop_ms"] / 1000)
    shortest, longest = int(rate / voicing["max_pitch_hz"]), int(rate / voicing["min_pitch_hz"])
    overall = np.sqrt(np.mean(segment ** 2))
    scores = []
    for start in range(0, len(segment) - window, hop):
        frame = segment[start:start + window] - segment[start:start + window].mean()
        if np.sqrt(np.mean(frame ** 2)) < overall * voicing["min_relative_rms"]:
            continue
        correlation = np.correlate(frame, frame, "full")[window - 1:]
        scores.append(correlation[shortest:longest].max() / max(correlation[0], 1e-12))
    return float(np.mean(np.array(scores) > voicing["periodicity"])) if scores else 0.0


def finish(segment, rate, rules):
    padded = segment.copy()
    for edge, size in (("in", rules["fade_in_ms"]), ("out", rules["fade_out_ms"])):
        count = min(len(padded) // 2, int(rate * size / 1000))
        if count == 0:
            continue
        ramp = np.linspace(0.0, 1.0, count)
        if edge == "in":
            padded[:count] *= ramp
        else:
            padded[-count:] *= ramp[::-1]
    return padded


def momentary_max(audio, rate, level, meters):
    window = int(level["momentary_window_s"] * rate)
    hop = max(1, int(level["momentary_hop_s"] * rate))
    if len(audio) < window:
        audio = np.concatenate([audio, np.zeros(window - len(audio))])
    return max(meters.integrated_lufs(audio[start:start + window], rate) for start in range(0, len(audio) - window + 1, hop))


def level_burst(audio, rate, level, meters):
    wanted = level["target_lufs"] - momentary_max(audio, rate, level, meters)
    gain = min(wanted, level["ceiling_dbtp"] - meters.true_peak_db(audio, rate))
    return meters.apply_gain_db(audio, gain)


def slice_set(name, entry, spec, generator, out_dir, plan, meters):
    rules = {**spec["defaults"], **entry.get("rules", {})}
    candidates = []
    for source in entry["sources"]:
        path = os.path.join(spec["source_root"], source)
        samples, rate = soundfile.read(path, always_2d=True)
        mono = samples.mean(axis=1)
        if rate != spec["output"]["sample_rate"]:
            raise SystemExit(f"{source}: {rate} Hz, expected {spec['output']['sample_rate']}")
        bursts = find_bursts(mono, rate, rules)
        if "voicing" in rules:
            unvoiced = [burst for burst in bursts if voiced_fraction(mono[burst[0]:burst[1]], rate, rules["voicing"]) <= rules["voicing"]["max_voiced_fraction"]]
            print(f"{name} {source}: {len(bursts) - len(unvoiced)} voiced bursts rejected")
            bursts = unvoiced
        if plan:
            print(f"{name} {source}: {len(bursts)} bursts, lengths ms {[b[2] for b in bursts]}")
        candidates.extend((source, mono, start, end, loudness) for start, end, _, loudness in bursts)
    generator.shuffle(candidates)
    candidates.sort(key=lambda candidate: -candidate[4])
    chosen = candidates[: entry["count"]]
    print(f"{name}: {len(candidates)} bursts found, {len(chosen)} kept")
    if plan:
        return []
    os.makedirs(out_dir, exist_ok=True)
    records = []
    rate = spec["output"]["sample_rate"]
    subtype = {16: "PCM_16", 24: "PCM_24"}[spec["output"]["bit_depth"]]
    for number, (source, mono, start, end, loudness) in enumerate(chosen, start=1):
        pre = int(rate * rules["pre_roll_ms"] / 1000)
        post = int(rate * rules["post_roll_ms"] / 1000)
        segment = finish(mono[max(0, start - pre): min(len(mono), end + post)], rate, rules)
        audio = level_burst(segment, rate, spec["level"], meters)
        file_name = f"{entry['prefix']}_{number:02d}.wav"
        soundfile.write(os.path.join(out_dir, file_name), audio, rate, subtype=subtype)
        records.append({"file": file_name, "set": name, "source": source, "start_seconds": round(max(0, start - pre) / rate, 4), "length_seconds": round(len(audio) / rate, 4)})
    return records


def main():
    parser = argparse.ArgumentParser(description="Cut continuous takes (cloth, breathing) into one-shot bursts per set, from a spec, levelled with Keel's BS.1770-4 meters.")
    parser.add_argument("--spec", required=True, help="burst spec JSON")
    parser.add_argument("--out", required=True, help="output folder, one subfolder per set")
    parser.add_argument("--set", action="append", help="only these sets")
    parser.add_argument("--plan", action="store_true", help="list the bursts without writing audio")
    parser.add_argument("--keel", required=True, help="Keel checkout; run with Keel's venv Python")
    args = parser.parse_args()
    sys.path.insert(0, args.keel)
    import meters
    spec = json.load(open(args.spec, encoding="utf-8"))
    generator = random.Random(spec["seed"])
    manifest = []
    for name, entry in spec["sets"].items():
        if args.set and name not in args.set:
            continue
        manifest.extend(slice_set(name, entry, spec, generator, os.path.join(args.out, name), args.plan, meters))
    if not args.plan:
        manifest_path = os.path.join(args.out, "manifest.json")
        if args.set and os.path.exists(manifest_path):
            kept = [record for record in json.load(open(manifest_path, encoding="utf-8")) if record["set"] not in args.set]
            manifest = kept + manifest
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        print(f"{len(manifest)} bursts -> {args.out}")


if __name__ == "__main__":
    main()
