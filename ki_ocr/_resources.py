"""Locate frozen resources in a checkout or an installed wheel."""
import json
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
BUNDLED_ROOT = PACKAGE_ROOT / "_data"
RESOURCE_ROOT = BUNDLED_ROOT if BUNDLED_ROOT.is_dir() else PACKAGE_ROOT.parent


def resource_path(relative):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Resource path must stay relative to Ki-OCR resources")
    return RESOURCE_ROOT / relative


def read_binding(path):
    path = Path(path).resolve()
    binding = json.loads(path.read_text(encoding="utf-8"))
    expected = {"source", "model", "runtime_helpers", "execution_policy"}
    if set(binding) != expected or binding["execution_policy"] not in ("managed", "standalone"):
        raise ValueError("Binding needs source/model/runtime_helpers/execution_policy")
    for name in ("source", "model", "runtime_helpers"):
        value = binding[name]
        if not isinstance(value, str) or not value:
            raise ValueError("Binding paths must be nonempty strings")
        if name == "runtime_helpers" and value == "bundled":
            target = resource_path("runtime_helpers")
        else:
            target = Path(value).expanduser()
            if not target.is_absolute():
                target = path.parent / target
        binding[name] = str(target.resolve())
    return binding
