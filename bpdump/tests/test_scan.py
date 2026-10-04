import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bpdump import scan


def fstring(text):
    raw = text.encode() + b"\0"
    return struct.pack("<i", len(raw)) + raw


def fake_blueprint(stem):
    return b"".join([
        b"\x00\x00++UE5+Release-5.5\x00",
        fstring("/Game/Props/" + stem),
        fstring("/Game/Characters/Mannequin/SK_Mannequin_Skeleton"),
        fstring("/Game/Audio/SC_Click"),
        fstring("ParentClass"),
        fstring("/Script/Engine.BlueprintGeneratedClass'/Game/Props/BP_Base.BP_Base_C'"),
        fstring("NativeParentClass"),
        fstring("/Script/CoreUObject.Class'/Script/Engine.Actor'"),
        fstring("Click Sound"),
        fstring("Event Graph"),
        fstring("mixamorig:Hips"),
        fstring("C:/Art/props/button.fbx"),
        b"\x01\x00\x00\x00",
        fstring(stem),
        fstring("/Script/Engine.Blueprint"),
        b"\x00" * 8,
    ])


class ScanTest(unittest.TestCase):
    def test_describe_reads_class_parent_and_source(self):
        with tempfile.TemporaryDirectory() as folder:
            content = Path(folder) / "Game" / "Content"
            asset = content / "Props" / "BP_Button.uasset"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(fake_blueprint("BP_Button"))
            record = scan.describe(asset, content, True, True)
        self.assertEqual(record["asset"], "/Game/Props/BP_Button")
        self.assertEqual(record["class"], "Blueprint")
        self.assertEqual(record["class_from"], "string_search")
        self.assertEqual(record["parent"], "BP_Base")
        self.assertEqual(record["native_parent"], "Actor")
        self.assertEqual(record["skeleton"], "/Game/Characters/Mannequin/SK_Mannequin_Skeleton")
        self.assertTrue(record["mixamo_bones"])
        self.assertEqual(record["saved_with"], "UE5 5.5")
        self.assertEqual(record["source_file"], "C:/Art/props/button.fbx")
        self.assertIn("/Game/Audio/SC_Click", record["refs"])
        self.assertEqual(record["names"], ["Click Sound"])

    def test_mixamo_bones_without_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            content = Path(folder) / "Content"
            asset = content / "SK_Hero.uasset"
            content.mkdir()
            asset.write_bytes(b"".join(fstring(bone) for bone in ["Hips", "Spine1", "Spine2", "HeadTop_End", "LeftUpLeg", "LeftHandIndex1"]))
            record = scan.describe(asset, content, False, False)
        self.assertTrue(record["mixamo_bones"])

    def test_scan_resumes_and_tags_project(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "Demo"
            (project / "Content" / "Props").mkdir(parents=True)
            (project / "Saved").mkdir()
            (project / "Demo.uproject").write_text(json.dumps({"EngineAssociation": "5.5"}))
            (project / "Content" / "Props" / "BP_Button.uasset").write_bytes(fake_blueprint("BP_Button"))
            (project / "Saved" / "BP_Ignored.uasset").write_bytes(fake_blueprint("BP_Ignored"))
            out = Path(folder) / "scan.jsonl"
            self.assertTrue(scan.scan(folder, out, [], False, False))
            self.assertTrue(scan.scan(folder, out, [], False, False))
            lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["project"], "Demo")
        self.assertEqual(lines[0]["engine"], "5.5")
        self.assertNotIn("refs", lines[0])


if __name__ == "__main__":
    unittest.main()
