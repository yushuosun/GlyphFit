# SWOCR

Reducing content-recognition visual tokens with scale-aware inputs

[简体中文](README.md) · [Method](#why-input-scale-matters) · [Full results and evaluation protocol](docs/EVALUATE.md) · [Release materials](docs/RELEASE.md)

SWOCR is a training-free inference-time adaptation method built on a frozen TeleOCR-1.2B. Without modifying TeleOCR's architecture or model weights, SWOCR adaptively adjusts the input scales of document pages and detected layout regions according to the visual scale of the input document. This allows different regions to be parsed at scales better suited to TeleOCR while improving visual budget utilization.

On **OmniDocBench v1.6_full (1,651 pages)**, the released SWOCR + TeleOCR-1.2B configuration achieves **98.40951 Overall**, improving on the original-input control with the same generation settings by **0.79246 percentage points**, while reducing content-recognition visual tokens per page by **51.85%**.

## Why input scale matters

A document page may contain large headings, dense body text, tables and formulas. The input passes through page rendering, region preprocessing and the model's image processor, each of which can change the scale that the model actually sees. A uniform page-level setting may spend visual tokens on unnecessary enlargement while still presenting small text at a scale that is difficult to recognize.

SWOCR comprises two complementary modules:

- **Source-aware Rendering:** Aligns the page-rendering scale with the source document resolution to reduce redundant visual computation.
- **Region-adaptive Scaling:** Selects suitable input scales based on the visual characteristics of text and table regions, within the model's visual and context budgets.

The two modules allocate input detail at the page and region levels, respectively. TeleOCR performs layout analysis, content recognition, post-processing and Markdown assembly.

## Released results

OmniDocBench v1.6_full · 1,651 pages · TeleOCR-1.2B

| Configuration | Overall ↑ | Content-recognition visual tokens/page ↓ |
|---|---:|---:|
| Original input, same generation settings | 97.61705 | 4268.23 |
| SWOCR A+B | **98.40951** | **2055.27** |

| Text ED ↓ | Formula CDM ↑ | Table TEDS ↑ | Table TEDS-S ↑ | Reading order ED ↓ |
|---:|---:|---:|---:|---:|
| 0.02542364 | 98.94488 | 98.82602 | 99.35003 | 0.11870026 |

Overall, CDM, TEDS and TEDS-S are percentages; ED values are ratios. The token statistics cover content-recognition inputs, excluding layout, warmup and candidate-scale measurement work; they do not establish an end-to-end latency reduction. Both arms' per-page metrics, token counts and recomputation script are available in the [released evidence](docs/EVIDENCE.md).

This evaluation covers all 1,651 pages of OmniDocBench v1.6_full, using the official scorer at commit `f133a71e9e91c3621c7ce8994200a7b394a06eb3` and the accompanying quick_match configuration. The [evaluation protocol](docs/EVALUATE.md) describes the control settings, metric coverage and released materials.

## Quick start

Install the CPU interfaces with Python 3.10 or later:

```bash
git clone https://github.com/yushuosun/SWOCR.git
cd SWOCR
git checkout swocr-repro-r5
python -m pip install -e .
python -m swocr --help
```

Compute the source-aware rendering scale without loading a model:

```bash
python -m swocr a-scale \
    --page-points 612 792 --source-pixels 1224 1584
```

The command returns `{"pre_render_scale": 2.0}`.

To measure glyphs in images, install the vision dependencies:

```bash
python -m pip install -e ".[vision]"
```

`swocr.api` provides `source_render_scale`, `candidate_scales` and `select_measured_candidates`. The original `glyphfit` API and CLI remain available as compatibility interfaces.

## Run the released pipeline

Full inference uses Linux and pinned versions of the TeleOCR source, model and runtime dependencies. Configure the local paths in `runtime_binding.json`, then prepare the input images before loading the model. The repository includes the three runtime helper modules used by this version.

The [inference guide](docs/REPRODUCE.md) provides a dedicated-machine CLI and a managed-cluster Python entry, including GPU admission and work-window settings. See the [dependency documentation](docs/DEPENDENCIES.md) for the pinned environment.

## Reproduce evaluation

The release includes predictions for all 1,651 pages and the accompanying evaluation package:

- [Markdown predictions](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_OmniDocBench_v1.6_predictions.zip)
- [Evaluation configuration, results and manifests](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip)
- [Release inference configuration](https://github.com/yushuosun/SWOCR/blob/swocr-repro-r5/configs/swocr_ab.json)
- [Same-generation control predictions](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_same_generation_baseline_predictions.zip)
- [Per-page scores, tokens and completion records](docs/EVIDENCE.md)
- [Exact evaluation scores](https://github.com/yushuosun/SWOCR/blob/swocr-repro-r5/results/frozen_full1651.json)

The prediction archives contain Markdown only; referenced image crops are not included.

Verify the released predictions against the supplied manifest:

```bash
mkdir -p outputs/evaluation outputs/predictions/GLYPHFIT_FULL

python -m zipfile -e \
    artifacts/submission/SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip \
    outputs/evaluation

python -m zipfile -e \
    artifacts/submission/SWOCR_OmniDocBench_v1.6_predictions.zip \
    outputs/predictions/GLYPHFIT_FULL

python -m swocr verify-predictions \
    --predictions outputs/predictions/GLYPHFIT_FULL \
    --manifest outputs/evaluation/metadata/PREDICTION_FILES_SHA256.json
```

When all files match, the command reports `status: MATCH` with a matching count of 1,651.

Follow the [evaluation guide](docs/EVALUATE.md) to verify the prediction files and run the official OmniDocBench evaluator.

## Acknowledgments

SWOCR builds on TeleOCR-1.2B and uses OmniDocBench for document parsing evaluation. We thank the authors and maintainers for their open-source work.

## License

Project source code is licensed under [MIT](LICENSE). See [THIRD_PARTY.md](THIRD_PARTY.md) for external components and document-content rights.
