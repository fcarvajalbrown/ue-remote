import base64
import json
import struct
from pathlib import Path

from bpdump.kismet import Resolver, short_type, statements


def property_value(properties, name):
    if not isinstance(properties, list):
        return None
    for entry in properties:
        if isinstance(entry, dict) and entry.get("Name") == name:
            return entry
    return None


def struct_fields(entry):
    return {field.get("Name"): field for field in entry.get("Value", []) if isinstance(field, dict)}


CONTAINER_NAMES = {0: "", 1: "Array", 2: "Set", 3: "Map"}
NAME_BYTES = 8
OBJECT_BYTES = 4


def read_name(raw, offset, resolver):
    index, number = struct.unpack_from("<ii", raw, offset)
    text = resolver.name_at(index)
    return text if number == 0 else f"{text}_{number - 1}"


def raw_pin_type_text(blob, resolver):
    raw = base64.b64decode(blob)
    category = read_name(raw, 0, resolver)
    object_offset = 2 * NAME_BYTES
    sub_object = struct.unpack_from("<i", raw, object_offset)[0]
    container = raw[object_offset + OBJECT_BYTES]
    text = category + (":" + resolver.name_of(sub_object) if sub_object else "")
    if container == 3:
        value_offset = object_offset + OBJECT_BYTES + 1
        value_category = read_name(raw, value_offset, resolver)
        value_object = struct.unpack_from("<i", raw, value_offset + 2 * NAME_BYTES)[0]
        value = value_category + (":" + resolver.name_of(value_object) if value_object else "")
        return f"Map<{text}, {value}>"
    label = CONTAINER_NAMES.get(container, "")
    return f"{label}<{text}>" if label else text


def pin_type_text(pin_type, resolver):
    if isinstance(pin_type.get("Value"), str):
        return raw_pin_type_text(pin_type["Value"], resolver)
    fields = struct_fields(pin_type)
    category = fields.get("PinCategory", {}).get("Value", "?")
    sub_object = fields.get("PinSubCategoryObject", {}).get("Value", 0)
    container = fields.get("ContainerType", {}).get("Value", "None")
    text = category
    if sub_object:
        text += ":" + resolver.name_of(sub_object)
    if str(container) not in ("None", "0"):
        text = f"{container}<{text}>"
    return text


def variables_section(blueprint, resolver):
    lines = []
    entry = property_value(blueprint.get("Data", []), "NewVariables")
    for variable in (entry or {}).get("Value", []):
        fields = struct_fields(variable)
        name = fields.get("VarName", {}).get("Value", "?")
        pin_type = fields.get("VarType")
        kind = pin_type_text(pin_type, resolver) if pin_type else "?"
        default = fields.get("DefaultValue", {}).get("Value")
        suffix = f" = {default}" if default else ""
        lines.append(f"- {name}: {kind}{suffix}")
    return lines


def function_section(function, resolver):
    flags = str(function.get("FunctionFlags", "")).replace("FUNC_", "")
    parameters = [prop.get("Name", "?") + ":" + short_type(prop).replace("Property", "") for prop in function.get("LoadedProperties", []) if is_parameter(prop)]
    lines = [f"### {function.get('ObjectName')}", "", f"Flags: {flags}"]
    if parameters:
        lines.append("Parameters: " + ", ".join(parameters))
    lines += ["", "```"]
    lines += statements(function.get("ScriptBytecode", []), resolver)
    lines.append("```")
    return lines


def is_parameter(prop):
    return "CPF_Parm" in str(prop.get("PropertyFlags", ""))


def summarize(json_path):
    package = json.loads(Path(json_path).read_text(encoding="utf-8-sig"))
    resolver = Resolver(package)
    exports = package.get("Exports", [])
    blueprint = next((e for e in exports if property_value(e.get("Data", []), "NewVariables") is not None), None)
    functions = [e for e in exports if short_type(e) == "FunctionExport"]
    lines = [f"# {Path(json_path).stem}", ""]
    if blueprint:
        parent = property_value(blueprint["Data"], "ParentClass")
        if parent:
            lines += [f"Parent class: {resolver.name_of(parent.get('Value', 0))}", ""]
        variables = variables_section(blueprint, resolver)
        if variables:
            lines += ["## Variables", ""] + variables + [""]
    lines += ["## Functions", ""]
    for function in functions:
        lines += function_section(function, resolver) + [""]
    return "\n".join(lines).rstrip() + "\n"
