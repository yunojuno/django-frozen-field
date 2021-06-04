# mypy hints
ModelName = str
ModelKlass = str
AttributeName = str
AttributeList = list[AttributeName]
IsoTimestamp = str
MetaFields = dict[AttributeName, ModelKlass]


def klass_str(klass: object) -> ModelKlass:
    """Return fully-qualified (namespaced) name for a class."""
    return f"{klass.__class__.__module__}.{klass.__class__.__qualname__}"
