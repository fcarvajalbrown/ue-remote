import json

HIDDEN_STATEMENTS = {
    "EX_Tracepoint",
    "EX_WireTracepoint",
    "EX_Nothing",
    "EX_EndOfScript",
    "EX_PushExecutionFlow",
}
FUNCTION_CALLS = {"EX_CallMath", "EX_FinalFunction", "EX_LocalFinalFunction"}
VIRTUAL_CALLS = {"EX_VirtualFunction", "EX_LocalVirtualFunction"}
VARIABLES = {"EX_LocalVariable", "EX_InstanceVariable", "EX_LocalOutVariable", "EX_DefaultVariable"}
LITERALS = {"EX_IntConst", "EX_FloatConst", "EX_ByteConst", "EX_Int64Const", "EX_UInt64Const", "EX_DoubleConst"}
KEYWORDS = {
    "EX_Self": "self",
    "EX_True": "true",
    "EX_False": "false",
    "EX_NoObject": "None",
    "EX_Nothing": "None",
}


def short_type(node):
    return node.get("$type", "").split(",")[0].split(".")[-1]


class Resolver:
    def __init__(self, package):
        self.imports = package.get("Imports", [])
        self.exports = package.get("Exports", [])
        self.names = package.get("NameMap", [])

    def name_at(self, index):
        if 0 <= index < len(self.names):
            return self.names[index]
        return f"name#{index}"

    def name_of(self, index):
        if index == 0:
            return "None"
        if index < 0:
            position = -index - 1
            if position >= len(self.imports):
                return f"import#{index}"
            entry = self.imports[position]
            outer = entry.get("OuterIndex", 0)
            name = entry.get("ObjectName", "?")
            if outer < 0 and -outer - 1 < len(self.imports):
                outer_name = self.imports[-outer - 1].get("ObjectName", "")
                if outer_name and not outer_name.startswith("/"):
                    return f"{outer_name}::{name}"
            return name
        position = index - 1
        if position >= len(self.exports):
            return f"export#{index}"
        return self.exports[position].get("ObjectName", "?")


def variable_name(pointer):
    path = pointer.get("New", {}).get("Path", [])
    return ".".join(path) if path else "?"


def render(node, resolver):
    if node is None:
        return "None"
    kind = short_type(node)
    if kind in KEYWORDS:
        return KEYWORDS[kind]
    if kind in VARIABLES:
        prefix = "self." if kind == "EX_InstanceVariable" else ""
        return prefix + variable_name(node.get("Variable", {}))
    if kind in LITERALS:
        return str(node.get("Value"))
    if kind in ("EX_StringConst", "EX_UnicodeStringConst"):
        return json.dumps(node.get("Value"))
    if kind == "EX_NameConst":
        return "name(" + str(node.get("Value")) + ")"
    if kind == "EX_TextConst":
        return "text(" + text_value(node.get("Value")) + ")"
    if kind == "EX_ObjectConst":
        return "object(" + resolver.name_of(node.get("Value", 0)) + ")"
    if kind in FUNCTION_CALLS:
        return call(resolver.name_of(node.get("StackNode", 0)), node, resolver)
    if kind in VIRTUAL_CALLS:
        return call(str(node.get("VirtualFunctionName")), node, resolver)
    if kind in ("EX_Context", "EX_Context_FailSilent", "EX_ClassContext"):
        target = render(node.get("ObjectExpression"), resolver)
        return target + "." + render(node.get("ContextExpression"), resolver)
    if kind == "EX_InterfaceContext":
        return render(node.get("InterfaceValue"), resolver)
    if kind == "EX_StructMemberContext":
        return render(node.get("StructExpression"), resolver) + "." + member_name(node.get("StructMemberExpression"))
    if kind in ("EX_DynamicCast", "EX_ObjToInterfaceCast", "EX_CrossInterfaceCast", "EX_InterfaceToObjCast"):
        return f"cast<{resolver.name_of(node.get('ClassPtr', 0))}>({render(node.get('Target'), resolver)})"
    if kind == "EX_PrimitiveCast":
        return f"convert<{node.get('ConversionType')}>({render(node.get('Target'), resolver)})"
    if kind == "EX_StructConst":
        values = ", ".join(render(item, resolver) for item in node.get("Value", []))
        return f"{resolver.name_of(node.get('Struct', 0))}{{{values}}}"
    if kind == "EX_SetArray":
        values = ", ".join(render(item, resolver) for item in node.get("Elements", []))
        return f"[{values}]"
    if kind == "EX_MapConst":
        return "map{" + ", ".join(render(item, resolver) for item in node.get("Elements", [])) + "}"
    if kind in ("EX_VectorConst", "EX_RotationConst", "EX_TransformConst"):
        return kind[3:-5].lower() + json.dumps(node.get("Value"), separators=(",", ":"))[:80]
    if kind in ("EX_Let", "EX_LetBool", "EX_LetObj", "EX_LetWeakObjPtr", "EX_LetDelegate", "EX_LetMulticastDelegate"):
        return assignment(node, resolver)
    if kind == "EX_LetValueOnPersistentFrame":
        destination = variable_name(node.get("DestinationProperty", {}))
        return f"{destination} = {render(node.get('AssignmentExpression'), resolver)}"
    return generic(node, kind, resolver)


def text_value(value):
    if not isinstance(value, dict):
        return json.dumps(value)
    parts = []
    for key in ("SourceString", "LocalizedSource", "StringTableId", "StringTableKey"):
        field = value.get(key)
        if isinstance(field, dict):
            field = field.get("Value")
        if field:
            parts.append(str(field))
    return json.dumps(" | ".join(parts)) if parts else json.dumps(value)[:80]


def member_name(node):
    if node is None:
        return "?"
    if isinstance(node, dict) and "New" in node:
        return variable_name(node)
    return "?"


def call(name, node, resolver):
    arguments = ", ".join(render(item, resolver) for item in node.get("Parameters", []))
    return f"{name}({arguments})"


def assignment(node, resolver):
    if "Variable" in node and "Expression" in node:
        return f"{render(node['Variable'], resolver)} = {render(node['Expression'], resolver)}"
    target = render(node.get("VariableExpression"), resolver)
    return f"{target} = {render(node.get('AssignmentExpression'), resolver)}"


def generic(node, kind, resolver):
    parts = []
    for key, value in node.items():
        if key == "$type":
            continue
        if isinstance(value, dict) and "$type" in value:
            parts.append(render(value, resolver))
        elif isinstance(value, list):
            parts.extend(render(item, resolver) for item in value if isinstance(item, dict) and "$type" in item)
    return kind[3:] + "(" + ", ".join(parts) + ")"


def statements(bytecode, resolver):
    lines = []
    for node in bytecode:
        kind = short_type(node)
        if kind in HIDDEN_STATEMENTS:
            continue
        if kind == "EX_Return":
            lines.append("return " + render(node.get("ReturnExpression"), resolver))
        elif kind == "EX_Jump":
            lines.append(f"goto @{node.get('CodeOffset')}")
        elif kind == "EX_JumpIfNot":
            lines.append(f"if not ({render(node.get('BooleanExpression'), resolver)}) goto @{node.get('CodeOffset')}")
        elif kind == "EX_PopExecutionFlow":
            lines.append("end of flow")
        elif kind == "EX_PopExecutionFlowIfNot":
            lines.append(f"if not ({render(node.get('BooleanExpression'), resolver)}) end of flow")
        elif kind == "EX_ComputedJump":
            lines.append("goto computed")
        else:
            lines.append(render(node, resolver))
    return lines
