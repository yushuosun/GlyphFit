# Dependencies

## External components

Full inference uses the following pinned components:

| Component | Frozen identity |
|---|---|
| TeleOCR source | https://github.com/caipeng328/TeleOCR, commit `9921cffe380efe4e2fa010258b3d0c3cb70bab2d` |
| TeleOCR model | revision `e92585356c0d0b7b7a65938f3da035c6593cc9a6`; weight SHA256 `9817b18041bd96403f75e38a33b28ed0cd5fb2641f67eead673afabd3c408109` |
| GPU stack | vLLM 0.11.0, torch 2.8.0+cu128, transformers 4.57.6 |
| Renderer | pypdfium2 4.30.0; renderer/helper hashes in the configuration |
| CPU images | NumPy 2.2.6, OpenCV 4.14.0, Pillow 11.3.0 |

Follow the [TeleOCR installation instructions](https://github.com/caipeng328/TeleOCR/blob/9921cffe380efe4e2fa010258b3d0c3cb70bab2d/README.md) for the original source and GPU dependencies, and obtain the [model snapshot](https://huggingface.co/XingChen-AGI/TeleOCR/tree/e92585356c0d0b7b7a65938f3da035c6593cc9a6) separately. The `environment/` lock files record the complete inference and scoring environments, including transitive packages. Source and model terms are linked in [THIRD_PARTY.md](../THIRD_PARTY.md).

## Included runtime helpers

These project modules are included at their original frozen hashes:

| Path | Role | SHA256 |
|---|---|---|
| [runtime_helpers/context_runtime.py](../runtime_helpers/context_runtime.py) | Validate the fresh engine configuration, bind the context-budget hook and validate returned outputs. | `aebf427a5ff1f77bceb66776376b0dda4eb052fd161f4addc35247bde0865330` |
| [runtime_helpers/context_budget.py](../runtime_helpers/context_budget.py) | Count expanded prompt tokens and enforce the output reserve before queuing a request. | `0d13007a788abbc021172b8caf13cec6ae8033ed46cf79a728eb2d5300ab60ef` |
| [runtime_helpers/telemetry.py](../runtime_helpers/telemetry.py) | Record request metadata, raw outputs and local table crops without changing request content or sampling. | `5453e070c3284c1ab32fc7dfd1ba55bff904375cbb388ac6a99b8cd3c1c7d31d` |

The helper modules import the Python standard library and each other. The runtime adapter operates on the separately installed, pinned vLLM engine.

From the repository root, copy `configs/runtime_binding.example.json` to `runtime_binding.json` and set the external `source` and `model` directory paths. The example uses `"runtime_helpers": "bundled"` to select the included helper files in either a checkout or an installed wheel. Relative external paths resolve from the binding file's directory. Select `managed` or `standalone` according to [the inference instructions](REPRODUCE.md).

`python -m ki_ocr doctor --binding runtime_binding.json` checks file hashes and installed package versions before model loading. Add `--verify-weight` to hash the model weights as well. The CPU scale/selection interfaces and prediction verifier can be used separately from the inference backend.
