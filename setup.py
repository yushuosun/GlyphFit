"""Include the frozen runtime resources in ordinary wheels."""
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

RESOURCES = (
    "inference_ab.py",
    "configs/ki_ocr_ab.json",
    "configs/runtime_binding.example.json",
    "runtime_helpers/context_runtime.py",
    "runtime_helpers/context_budget.py",
    "runtime_helpers/telemetry.py",
)


class BuildPy(build_py):
    def resource_pairs(self):
        source_root = Path(__file__).resolve().parent
        target_root = Path(self.build_lib) / "ki_ocr" / "_data"
        return [(source_root / name, target_root / name) for name in RESOURCES]

    def run(self):
        super().run()
        pairs = self.resource_pairs()
        target_root = (Path(self.build_lib) / "ki_ocr" / "_data").resolve()
        expected = {target.resolve() for _, target in pairs}
        # Setuptools may reuse a previous build directory after a resource rename.
        # Only remove obsolete files from this package's generated resource tree.
        if target_root.exists():
            for path in target_root.rglob("*"):
                resolved = path.resolve()
                if path.is_file() and resolved.is_relative_to(target_root) and resolved not in expected:
                    path.unlink()
        for source, target in pairs:
            self.mkpath(str(target.parent))
            self.copy_file(str(source), str(target))

    def get_outputs(self, include_bytecode=1):
        return super().get_outputs(include_bytecode) + [str(target) for _, target in self.resource_pairs()]


setup(cmdclass={"build_py": BuildPy})
