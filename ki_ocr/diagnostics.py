"""Read-only dependency and prediction checks. Never import a GPU framework."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

from ._resources import read_binding, resource_path

ROOT = Path(__file__).resolve().parents[1]


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def doctor(binding_path, *, verify_weight=False):
    binding = read_binding(binding_path)
    expected = {"source", "model", "runtime_helpers", "execution_policy"}
    if set(binding) != expected or binding["execution_policy"] not in ("managed", "standalone"):
        raise ValueError("Binding needs source/model/runtime_helpers/execution_policy")
    cfg = json.loads(resource_path("configs/ki_ocr_ab.json").read_text(encoding="utf8"))
    files = []
    for root_key, pins_key in [("source", "consumer_code_pins"), ("model", "model_config_pins"),
                               ("model", "processor_asset_pins"), ("runtime_helpers", "private_runtime_pins")]:
        base = Path(binding[root_key]).resolve()
        for name, expected_sha in cfg[pins_key].items():
            path = (base / name).resolve()
            if not path.is_relative_to(base):
                raise ValueError("Dependency pin escapes its root")
            actual = file_sha(path) if path.is_file() else None
            files.append({"group": root_key, "file": name, "status": "MATCH" if actual == expected_sha else ("MISSING" if actual is None else "DIFFERENT")})
    if verify_weight:
        path = Path(binding["model"]) / "model.safetensors"
        actual = file_sha(path) if path.is_file() else None
        files.append({"group": "model", "file": path.name, "status": "MATCH" if actual == cfg["model_weight_SHA256"] else ("MISSING" if actual is None else "DIFFERENT")})
    versions = []
    packages = {k: v for k, v in cfg["processor_runtime_versions"].items() if k not in ("torch_build", "opencv")}
    for name, expected_version in packages.items():
        try:
            actual = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            actual = None
        versions.append({"package": name, "expected": expected_version, "installed": actual, "match": actual == expected_version})
    ok = all(x["status"] == "MATCH" for x in files) and all(x["match"] for x in versions)
    return {"status": "DEPENDENCY_METADATA_MATCH" if ok else "DEPENDENCIES_NOT_READY", "files": files,
            "package_versions": versions, "weights_hashed": verify_weight,
            "heavy_framework_imports": False, "GPU_calls": 0,
            "full_runtime_execution_verified": False}


def verify_predictions(directory, manifest_path):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise ValueError("Prediction directory does not exist")
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf8"))
    rows = manifest["files"]
    names = [r["filename"] for r in rows]
    if len(names) != manifest["count"] or len({n.casefold() for n in names}) != len(names):
        raise ValueError("Prediction manifest count or duplicate names differ")
    failures = []
    for row in rows:
        name = row["filename"]
        if Path(name).name != name or not name.endswith(".md") or "\\" in name or ":" in name:
            raise ValueError("Unsafe prediction filename")
        path = directory / name
        if not path.is_file():
            failures.append({"filename": name, "reason": "MISSING"})
        elif path.stat().st_size != row["bytes"] or file_sha(path) != row["SHA256"]:
            failures.append({"filename": name, "reason": "BYTES_OR_SHA_DIFFER"})
    actual = {p.name for p in directory.glob("*.md")}
    extra = sorted(actual - set(names))
    return {"status": "MATCH" if not failures and not extra else "DIFFERENT", "expected_count": len(rows),
            "actual_MD_count": len(actual), "matching_count": len(rows) - len(failures),
            "failures": failures, "extra_MD": extra, "GT_reads": 0, "GPU_calls": 0}
