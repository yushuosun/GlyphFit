# Repository contents

The repository includes the source render cap, glyph estimator, scale menu/selector, full page-processing loop and runtime binding interfaces. `swocr.api` provides CPU scale/selection functions; the `swocr` CLI provides preparation, inference, dependency checks and prediction verification.

The frozen configuration is in `configs/`, completed numerical results are in `results/`, and version identities are in `metadata/`. Public prediction and evaluation ZIPs are in `artifacts/submission/`.

The three context/runtime/journal helpers are included in `runtime_helpers/`. The TeleOCR source/model and GPU packages remain external [dependencies](DEPENDENCIES.md). [Inference commands](REPRODUCE.md), [evaluation commands](EVALUATE.md) and [evidence scope](EVIDENCE.md) describe their use.
