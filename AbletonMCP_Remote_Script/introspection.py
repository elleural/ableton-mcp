"""Reflection over Live's embedded Python API (the ``Live`` module).

Produces a JSON-serialisable description of every module, class, enum,
property and function Live exposes to Remote Scripts, including the
Boost.Python docstrings that carry each function's signature. This is the
ground truth for what the running Live version can actually do.
"""
from __future__ import absolute_import, print_function, unicode_literals

import inspect
import json
import types

_CPP_SIGNATURE_MARKER = "C++ signature :"


def _clean_doc(doc):
    """Strip Boost.Python's trailing C++ signature block from a docstring."""
    if not doc:
        return None
    doc = doc.split(_CPP_SIGNATURE_MARKER)[0]
    lines = [line.strip() for line in doc.strip().splitlines()]
    return "\n".join(line for line in lines if line) or None


def _is_enum(cls):
    return isinstance(getattr(cls, "values", None), dict) and issubclass(cls, int)


def _describe_enum(cls):
    return {
        "kind": "enum",
        "values": {str(name): int(value) for name, value in sorted(cls.names.items(), key=lambda kv: int(kv[1]))},
    }


def _describe_class(cls):
    if _is_enum(cls):
        return _describe_enum(cls)
    info = {
        "kind": "class",
        "bases": [base.__name__ for base in cls.__bases__],
        "doc": _clean_doc(cls.__doc__),
        "properties": {},
        "methods": {},
        "nested": {},
    }
    for name, attr in sorted(cls.__dict__.items()):
        if name.startswith("_"):
            continue
        if isinstance(attr, property):
            info["properties"][name] = {
                "settable": attr.fset is not None,
                "doc": _clean_doc(attr.__doc__),
            }
        elif inspect.isclass(attr):
            info["nested"][name] = _describe_class(attr)
        elif callable(attr):
            info["methods"][name] = _clean_doc(getattr(attr, "__doc__", None))
        else:
            info["properties"][name] = {"settable": False, "doc": None, "constant": repr(attr)[:200]}
    return info


def _describe_module(module, seen):
    info = {"classes": {}, "functions": {}, "submodules": {}, "other": {}}
    for name in sorted(dir(module)):
        if name.startswith("__"):
            continue
        try:
            attr = getattr(module, name)
        except Exception as error:  # Lazily-bound attributes can raise on access.
            info["other"][name] = "<error: {0}>".format(error)
            continue
        if isinstance(attr, types.ModuleType):
            if id(attr) not in seen:
                seen.add(id(attr))
                info["submodules"][name] = _describe_module(attr, seen)
        elif inspect.isclass(attr):
            info["classes"][name] = _describe_class(attr)
        elif callable(attr):
            info["functions"][name] = _clean_doc(getattr(attr, "__doc__", None))
        else:
            info["other"][name] = type(attr).__name__
    return info


def dump_live_api(output_path, application=None):
    """Write the full Live API description to ``output_path`` as JSON."""
    import Live

    api = {
        "live_version": application.get_version_string() if application else None,
        "live_module_dir": sorted(dir(Live)),
        "modules": _describe_module(Live, {id(Live)}),
    }
    with open(output_path, "w") as handle:
        json.dump(api, handle, indent=1, sort_keys=True)
    modules = api["modules"]["submodules"]
    return {
        "output_path": output_path,
        "module_count": len(modules),
        "class_count": sum(len(m["classes"]) for m in modules.values()),
    }
