"""CPU utilities plus explicit dispatch to the unchanged full inference entry."""
import argparse
import json
import subprocess
import sys

from ._resources import resource_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("doctor", help="Check external file pins and version metadata without model imports")
    p.add_argument("--binding", required=True)
    p.add_argument("--verify-weight", action="store_true")
    p = commands.add_parser("verify-predictions", help="Verify local MD bytes against a separate manifest")
    p.add_argument("--predictions", required=True)
    p.add_argument("--manifest", required=True)
    p = commands.add_parser("a-scale", help="Compute the source-aware pre-render scale")
    p.add_argument("--page-points", nargs=2, type=float, required=True, metavar=("WIDTH", "HEIGHT"))
    p.add_argument("--source-pixels", nargs=2, type=float, required=True, metavar=("WIDTH", "HEIGHT"))
    p.add_argument("--dpi", type=float, default=200)
    p.add_argument("--max-edge", type=float, default=3500)
    commands.add_parser("prepare", help="Forward arguments to the frozen CPU preparation entry", add_help=False)
    commands.add_parser("run-standalone", help="Forward arguments to the frozen explicit private-machine GPU entry", add_help=False)
    args, rest = parser.parse_known_args(argv)
    if args.command in ("prepare", "run-standalone"):
        entry = resource_path("inference_ab.py")
        return subprocess.run([sys.executable, str(entry), args.command, *rest], check=False).returncode
    if rest:
        parser.error("Unrecognized arguments: " + " ".join(rest))
    if args.command == "a-scale":
        from .api import source_render_scale
        result = {"pre_render_scale": source_render_scale(args.page_points, args.source_pixels, args.dpi, args.max_edge)}
    elif args.command == "doctor":
        from .diagnostics import doctor
        result = doctor(args.binding, verify_weight=args.verify_weight)
    else:
        from .diagnostics import verify_predictions
        result = verify_predictions(args.predictions, args.manifest)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("status", "MATCH") in ("MATCH", "DEPENDENCY_METADATA_MATCH") else 2
