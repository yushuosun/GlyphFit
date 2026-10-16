# Run full inference

Use Linux with fork support and the pinned [dependencies](DEPENDENCIES.md). The inference configuration is [ki_ocr_ab.json](../configs/ki_ocr_ab.json), SHA256 `f0101c8d7d70761c7a65179e87d7abee080339ae19fcae02cdd8ebf803ddb708`. Completed scores are in [results](../results/frozen_full1651.json).

The [configuration mapping](../metadata/configuration_equivalence.json) verifies that every runtime setting matches the original run configuration. [Release status](../metadata/RELEASE_STATUS.json) records completion separately from configuration metadata.

## Prepare inputs

After setting the paths in `runtime_binding.json`, prepare the complete image directory:

```bash
mkdir -p outputs
python -m ki_ocr prepare --binding runtime_binding.json --input /path/OmniDocBench/images --output outputs/prepared1651.json
```

Preparation runs in a fresh CPU interpreter, checks the dependency versions and generation settings, and prints the saved file's SHA256 as `prepared_manifest_SHA256`. This differs from `config_SHA256` and `binding_SHA256`. Set the shell variable from the saved bytes:

```bash
PREPARED_SHA256=$(python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('outputs/prepared1651.json').read_bytes()).hexdigest())")
```

## Dedicated machine

Set the binding's `execution_policy` to `standalone`. Supply the physical GPU index, UUID and total work window:

```bash
python -m ki_ocr run-standalone --prepared outputs/prepared1651.json --prepared-sha "$PREPARED_SHA256" --output outputs/run_001 --device GPU_INDEX --uuid EXACT_GPU_UUID --work-seconds EXPLICIT_BUDGET
```

The runner checks GPU identity and idle state, acquires a standalone lock and includes model loading in the work window. Use the managed entry below for shared clusters.

## Managed cluster

Within an existing worker admitted by the cluster's owner/resource controls, call:

```python
from ki_ocr.pipeline import validate_prepared, create_client
from ki_ocr.execution import run_with_admitted_client

prepared = validate_prepared(prepared_path, expected_sha)
client = create_client(prepared['binding_path'])
result = run_with_admitted_client(
    prepared_path, client, output_directory, owner_deadline,
    draining=owner_drain_callback, expected_prepared_sha=expected_sha)
```

Each arm runs rendering, layout, content generation, native post-processing and Markdown assembly. The outputs are `markdown/OFFICIAL_ORIGINAL/<image-stem>.md` and `markdown/GLYPHFIT_FULL/<image-stem>.md`. Completed records and failure records are retained when a run ends.

## Generation settings

Both arms share the full requested generation profiles, model, processor and consumer. TABLE presence/frequency penalties are 0/0. The original-input control uses these same generation settings; the upstream author default uses a separate 16k output setting.

The context window and requested output cap are 32768 tokens. Effective output allowance depends on prompt length. The 8192-token reserve is input admission headroom, with `prompt_tokens + 8192 <= 32768`. Full sampling profiles, renderer rules, glyph thresholds and scale candidates are in the configuration.
