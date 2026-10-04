import json
import os
import re
import struct
import sys
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path

ASSET_SUFFIXES = (".uasset", ".umap")
SKIPPED_DIRS = {"DerivedDataCache", "Intermediate", "Saved", "Binaries", ".git", ".diversion", ".vs", "__pycache__"}
HEADER_LIMIT = 16 * 1024 * 1024
PRINTABLE = re.compile(rb"[\x20-\x7e]{4,}")
SOURCE_FILE = re.compile(
    r"[A-Za-z]:[\\/][^\"'<>|*?]*?\.(?:fbx|obj|gltf|glb|abc|usd|wav|ogg|mp3|flac|png|tga|jpg|jpeg|psd|exr|hdr|tif|tiff|bmp|dds|mp4|ttf|otf)",
    re.IGNORECASE,
)
MEMBER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_ ]{3,80}$")
GUID = re.compile(r"[0-9A-F]{32}")
REGISTRY_NOISE = {"GeneratedClass", "ModuleRelativePath", "BlueprintType", "IsDataOnly"}
GRAPH_NOISE = {
    "Construction Script", "Event Graph", "Is Valid", "Is Not Valid", "Return Value", "Array Element",
    "Array Index", "Delta Seconds", "Other Actor", "Option 0", "Option 1", "End Play", "End Play Reason",
    "EEndPlayReason Enum", "Begin Play", "Actor Object Reference", "Vector 2D Structure", "Dimension 1",
}


def printable_strings(data):
    return [match.group().decode() for match in PRINTABLE.finditer(data)]


PACKAGE_TAG = 0x9E2A83C1
UE4_NON_OUTER_PACKAGE_IMPORT = 520
UE4_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
UE4_NAME_HASHES_SERIALIZED = 504
UE4_TEMPLATE_INDEX_IN_COOKED_EXPORTS = 508
UE5_OPTIONAL_RESOURCES = 1003
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_VERSE_CELLS = 1015
UE5_PACKAGE_SAVED_HASH = 1016
FILTER_EDITOR_ONLY = 0x80000000
HIDDEN_EXPORT_CLASSES = {"MetaData", "PackageMetaData", "Package"}


class Reader:
    def __init__(self, data, offset=0):
        self.data = data
        self.offset = offset

    def i32(self):
        value = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return value

    def u32(self):
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def skip(self, count):
        self.offset += count

    def fstring(self):
        length = self.i32()
        if length == 0:
            return ""
        if length < 0:
            raw = self.data[self.offset:self.offset - 2 * length]
            self.offset -= 2 * length
            return raw.decode("utf-16-le", "replace").rstrip("\0")
        if length > 4096:
            raise ValueError("string too long")
        raw = self.data[self.offset:self.offset + length]
        self.offset += length
        return raw.decode("latin-1").rstrip("\0")


def read_summary(data):
    reader = Reader(data)
    if reader.u32() != PACKAGE_TAG:
        return None
    legacy = reader.i32()
    if legacy > -2:
        return None
    if legacy != -4:
        reader.skip(4)
    ue4 = reader.i32()
    ue5 = reader.i32() if legacy <= -8 else 0
    reader.skip(4)
    if ue4 == 0:
        return None
    if ue5 >= UE5_PACKAGE_SAVED_HASH:
        reader.skip(24)
    custom_count = reader.i32()
    for _ in range(custom_count):
        if legacy < -5:
            reader.skip(20)
        elif legacy < -2:
            reader.skip(20)
            reader.fstring()
        else:
            reader.skip(8)
    if ue5 < UE5_PACKAGE_SAVED_HASH:
        reader.skip(4)
    reader.fstring()
    flags = reader.u32()
    name_count, name_offset = reader.i32(), reader.i32()
    if ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST:
        reader.skip(8)
    if not flags & FILTER_EDITOR_ONLY and ue4 >= UE4_PACKAGE_SUMMARY_LOCALIZATION_ID:
        reader.fstring()
    if ue4 >= UE4_SERIALIZE_TEXT_IN_PACKAGES:
        reader.skip(8)
    export_count, export_offset, import_count, import_offset = reader.i32(), reader.i32(), reader.i32(), reader.i32()
    later = []
    if ue5 >= UE5_VERSE_CELLS:
        later += [reader.i32(), reader.i32(), reader.i32(), reader.i32()][1::2]
    if ue5 >= UE5_METADATA_SERIALIZATION_OFFSET:
        later.append(reader.i32())
    later.append(reader.i32())
    return {
        "ue4": ue4, "ue5": ue5, "flags": flags,
        "names": (name_count, name_offset), "exports": (export_count, export_offset),
        "imports": (import_count, import_offset), "after_exports": [value for value in later if value > export_offset],
    }


def read_names(data, count, offset, ue4):
    reader = Reader(data, offset)
    hash_bytes = 4 if ue4 >= UE4_NAME_HASHES_SERIALIZED else 0
    names = []
    for _ in range(count):
        names.append(reader.fstring())
        reader.skip(hash_bytes)
    return names


def fname(names, data, offset):
    index, number = struct.unpack_from("<ii", data, offset)
    text = names[index] if 0 <= index < len(names) else ""
    return text if number == 0 else f"{text}_{number - 1}"


def table_class(data, stem):
    summary = read_summary(data)
    if not summary:
        return ""
    names = read_names(data, *summary["names"], summary["ue4"])
    import_count, import_offset = summary["imports"]
    import_size = 28
    if summary["ue4"] >= UE4_NON_OUTER_PACKAGE_IMPORT and not summary["flags"] & FILTER_EDITOR_ONLY:
        import_size += 8
    if summary["ue5"] >= UE5_OPTIONAL_RESOURCES:
        import_size += 4
    imports = [fname(names, data, import_offset + i * import_size + 20) for i in range(import_count)]
    export_count, export_offset = summary["exports"]
    if export_count <= 0 or not summary["after_exports"]:
        return ""
    span = min(summary["after_exports"]) - export_offset
    if span % export_count:
        return ""
    stride = span // export_count
    outer_at = 12 if summary["ue4"] >= UE4_TEMPLATE_INDEX_IN_COOKED_EXPORTS else 8
    candidates = []
    for i in range(export_count):
        base = export_offset + i * stride
        class_index, outer = struct.unpack_from("<i", data, base)[0], struct.unpack_from("<i", data, base + outer_at)[0]
        name = fname(names, data, base + outer_at + 4)
        if class_index < 0 and -class_index - 1 < len(imports):
            class_name = imports[-class_index - 1]
        elif 0 < class_index <= export_count:
            class_name = fname(names, data, export_offset + (class_index - 1) * stride + outer_at + 4)
        else:
            class_name = ""
        if outer <= 0 and class_name and class_name not in HIDDEN_EXPORT_CLASSES:
            candidates.append((outer != 0, name != stem, i, class_name))
    return min(candidates)[3] if candidates else ""


def asset_class(data, stem):
    try:
        found = table_class(data, stem)
    except (struct.error, ValueError, IndexError):
        found = ""
    if found:
        return found, "export_table"
    fallback = registry_class(data, stem)
    return fallback, "string_search" if fallback else ""



def registry_class(data, stem):
    name = stem.encode("ascii", "ignore")
    pattern = struct.pack("<i", len(name) + 1) + name + b"\0"
    position = data.find(pattern)
    while position != -1:
        cursor = position + len(pattern)
        length = struct.unpack_from("<i", data, cursor)[0] if cursor + 4 <= len(data) else 0
        if 1 < length < 256:
            raw = data[cursor + 4:cursor + 3 + length]
            if raw and all(32 <= byte < 127 for byte in raw):
                text = raw.decode().split(".")[-1]
                if text not in REGISTRY_NOISE:
                    return text
        position = data.find(pattern, position + 1)
    return ""


def tag_class(strings, tag):
    for index, text in enumerate(strings[:-1]):
        if text == tag and "'" in strings[index + 1]:
            value = strings[index + 1].split("'")[1].strip('"').split(".")[-1]
            return value[:-2] if value.endswith("_C") else value
    return ""


def game_path(text):
    return text.split(".")[0].rstrip()


def describe(path, content_root, with_refs, with_names):
    with open(path, "rb") as handle:
        data = handle.read(HEADER_LIMIT)
    strings = printable_strings(data)
    found_class, class_source = asset_class(data, path.stem)
    relative = path.relative_to(content_root).with_suffix("").as_posix()
    own = "/Game/" + relative
    saved_with = next((text for text in strings if text.startswith("++UE")), "")
    source = next((match.group() for match in map(SOURCE_FILE.search, strings) if match), "")
    record = {
        "asset": own,
        "class": found_class,
        "class_from": class_source,
        "parent": tag_class(strings, "ParentClass"),
        "native_parent": tag_class(strings, "NativeParentClass"),
        "skeleton": next((game_path(text) for text in strings if text.startswith("/Game/") and "keleton" in text.rsplit("/", 1)[-1] and game_path(text) != own), ""),
        "mixamo_bones": any(text.lower().startswith("mixamorig") for text in strings),
        "saved_with": saved_with.replace("++UE", "UE").replace("+Release-", " "),
        "source_file": source.replace("\\", "/"),
        "bytes": path.stat().st_size,
    }
    if with_refs:
        record["refs"] = sorted({game_path(text) for text in strings if text.startswith("/Game/") and game_path(text) != own})
    if with_names:
        record["names"] = sorted({
            text for text in strings
            if " " in text and MEMBER_NAME.match(text) and not GUID.search(text) and text not in GRAPH_NOISE
        })
    return record


def project_info(project_dir):
    for entry in os.scandir(project_dir):
        if entry.name.endswith(".uproject") and entry.is_file():
            try:
                association = json.loads(Path(entry.path).read_text(encoding="utf-8-sig")).get("EngineAssociation", "")
            except (OSError, ValueError):
                association = ""
            return entry.name[:-len(".uproject")], association
    return Path(project_dir).name, ""


def walk_assets(root):
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError as error:
            print(f"skip {current}: {error}", file=sys.stderr)
            continue
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                if entry.name not in SKIPPED_DIRS:
                    stack.append(entry.path)
            elif entry.name.endswith(ASSET_SUFFIXES):
                yield Path(entry.path)


def content_root_of(path):
    for parent in path.parents:
        if parent.name == "Content":
            return parent
    return path.parent


def already_scanned(out_path):
    done = set()
    if out_path.exists():
        with open(out_path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    done.add(json.loads(line)["file"])
                except (ValueError, KeyError):
                    continue
    return done


def scan(source, out, includes, with_refs, with_names):
    source = Path(source).resolve()
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done = already_scanned(out_path)
    projects = {}
    classes = Counter()
    written = 0
    failed = 0
    with open(out_path, "a", encoding="utf-8") as handle:
        for path in walk_assets(source):
            key = path.as_posix()
            if key in done:
                continue
            relative = path.relative_to(source).as_posix()
            if includes and not any(fnmatch(relative, pattern) for pattern in includes):
                continue
            content_root = content_root_of(path)
            project_dir = content_root.parent
            if project_dir not in projects:
                projects[project_dir] = project_info(project_dir)
            try:
                record = describe(path, content_root, with_refs, with_names)
            except (OSError, struct.error) as error:
                print(f"fail {key}: {error}", file=sys.stderr)
                failed += 1
                continue
            name, association = projects[project_dir]
            handle.write(json.dumps({"file": key, "project": name, "engine": association, **record}, ensure_ascii=False) + "\n")
            classes[record["class"] or "?"] += 1
            written += 1
    print(f"scanned {written}, skipped {len(done)} already in {out_path.name}, failed {failed}")
    for name, count in classes.most_common():
        print(f"  {count:7d}  {name}")
    return failed == 0
