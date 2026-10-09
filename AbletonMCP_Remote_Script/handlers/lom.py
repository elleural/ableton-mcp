"""Lead-owned generic object-model commands: reach any property or function by path."""
from .. import lom
from ..core import command
from ..errors import CommandError


@command("lom_get", readonly=True)
def lom_get(ctx, path, properties=None, offset=0, limit=lom.LIST_LIMIT):
    """Read an object at path: all property values, or only the named properties.

    Every list of objects in the answer (and a path that is one) shows the names of `limit` items from `offset`.
    """
    offset, limit = lom.check_window(offset, limit)
    obj, normalized = lom.resolve(ctx.song, ctx.app, path)
    if properties is None:
        if not lom._is_live_object(obj):
            out = {"path": normalized}
            out.update(lom.summarize(obj, offset, limit))
            return out
        return lom.describe(obj, normalized, offset=offset, limit=limit)
    if isinstance(properties, str):
        properties = [properties]
    out = {"path": normalized, "values": {}}
    for name in properties:
        try:
            out["values"][name] = lom.summarize(getattr(obj, name), offset, limit)
        except Exception as error:
            out["values"][name] = {"error": str(error)}
    return out


@command("lom_set")
def lom_set(ctx, path, property, value):
    """Set a settable property of the object at path. {"path": ...} values refer to objects."""
    obj, normalized = lom.resolve(ctx.song, ctx.app, path)
    properties, _ = lom.members(obj)
    descriptor = properties.get(property)
    if descriptor is None:
        raise CommandError("not_found", "'{0}' has no property '{1}'. Properties: {2}".format(normalized, property, ", ".join(sorted(properties))))
    if descriptor.fset is None:
        raise CommandError("unsupported", "'{0}.{1}' is read-only".format(normalized, property))
    setattr(obj, property, lom.convert_argument(ctx.song, ctx.app, value))
    return {"path": normalized, "property": property, "value": lom.summarize(getattr(obj, property))}


@command("lom_call", timeout=30.0)
def lom_call(ctx, path, method, args=None):
    """Call a function of the object at path with positional args ({"path": ...} for objects)."""
    obj, normalized = lom.resolve(ctx.song, ctx.app, path)
    _, methods = lom.members(obj)
    if method not in methods:
        raise CommandError("not_found", "'{0}' has no function '{1}'. Functions: {2}".format(normalized, method, ", ".join(sorted(methods))))
    if (type(obj).__name__, method) in lom.BLOCKED_METHODS:
        raise CommandError("unsupported", "{0}.{1} opens a modal dialog and would block Live".format(type(obj).__name__, method))
    arguments = [lom.convert_argument(ctx.song, ctx.app, item) for item in (args or [])]
    result = getattr(obj, method)(*arguments)
    return {"path": normalized, "method": method, "result": lom.result_out(ctx.song, ctx.app, result)}


@command("lom_describe", readonly=True)
def lom_describe(ctx, path="live_set"):
    """Properties (with settability) and functions available at path, with Live's docstrings."""
    obj, normalized = lom.resolve(ctx.song, ctx.app, path)
    if not lom._is_live_object(obj):
        raise CommandError("invalid_argument", "'{0}' is a value, not an object".format(normalized))
    return lom.documentation(obj, normalized)
