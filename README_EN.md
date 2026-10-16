# Ki-OCR

[简体中文](README.md) · [Method](#why-input-scale-matters) · [Full results and evaluation protocol](docs/EVALUATE.md) · [Release materials](docs/RELEASE.md)

Ki-OCR is a training-free inference-time adaptation method built on a frozen TeleOCR-1.2B. Without modifying TeleOCR's architecture or model weights, Ki-OCR adaptively adjusts the input scales of document pages and detected layout regions according to the visual scale of the input document. This allows different regions to be parsed at scales better suited to recognition while improving visual budget utilization.

On **OmniDocBench v1.6_full (1,651 pages)**, the released Ki-OCR configuration achieves **98.40951 Overall**. The recorded statistics show that, compared with TeleOCR, Ki-OCR reduces average content-recognition visual tokens per page from 4268.23 to 2055.27, a reduction of 51.85%.

## Why input scale matters

A document page may contain large headings, dense body text, tables and formulas. The input passes through page rendering, region preprocessing and the model's image processor, each of which can change the scale that the model actually sees. A uniform page-level setting may spend visual tokens on unnecessary enlargement while still presenting small text at a scale that is difficult to recognize.

Ki-OCR comprises two complementary modules:

- **Source-aware Rendering:** Aligns the page-rendering scale with the source document resolution to reduce redundant visual computation.
- **Region-adaptive Scaling:** Adaptively selects suitable input scales based on the visual characteristics of text and table regions, within the model's visual and context budgets.

The two modules allocate input detail at the page and region levels, respectively. TeleOCR performs layout analysis, content recognition, post-processing and Markdown assembly.

## Released results

The table compares Ki-OCR with the five highest Overall scores on the [official OmniDocBench v1.6_full leaderboard](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/README.md#end-to-end-evaluation), checked on 2026-10-16. Ki-OCR's local evaluation score exceeds the current leading score; Ki-OCR has not yet been included in the official leaderboard.

| Method | Overall ↑ | Text ED ↓ | Formula CDM ↑ | Table TEDS ↑ | Table TEDS-S ↑ | Reading order ED ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **Ki-OCR** | 98.40951 | 0.02542364 | 98.94488 | 98.82602 | 99.35003 | 0.11870026 |
| TeleOCR | 96.91 | 0.0267 | 96.5895 | 96.8183 | 98.1806 | 0.1184 |
| OvisOCR2 | 96.47 | 0.0265 | 97.4854 | 94.5842 | 96.9768 | 0.1120 |
| PaddleOCR-VL-1.6 | 96.34 | 0.0326 | 97.5304 | 94.7619 | 97.1002 | 0.1278 |
| MinerU2.5-Pro | 95.75 | 0.036 | 97.45 | 93.42 | 95.92 | 0.120 |
| GLM-OCR | 95.22 | 0.044 | 97.18 | 92.83 | 95.39 | 0.133 |

Overall, CDM, TEDS and TEDS-S are percentages; ED values are ratios. Both arms' per-page metrics, token counts and recomputation script are available in the [released evidence](docs/EVIDENCE.md).

This evaluation covers all 1,651 pages of OmniDocBench v1.6_full, using the official scorer at commit `f133a71e9e91c3621c7ce8994200a7b394a06eb3` and the accompanying quick_match configuration. The [evaluation protocol](docs/EVALUATE.md) describes the control settings, metric coverage and released materials.

## Quick start

Install the CPU interfaces with Python 3.10 or later:

```bash
git clone https://github.com/yushuosun/Ki-OCR.git
cd Ki-OCR
git checkout ki-ocr-repro-r6
python -m pip install -e .
python -m ki_ocr --help
```

Compute the source-aware rendering scale without loading a model:

```bash
python -m ki_ocr a-scale \
    --page-points 612 792 --source-pixels 1224 1584
```

The command returns `{"pre_render_scale": 2.0}`.

To measure glyphs in images, install the vision dependencies:

```bash
python -m pip install -e ".[vision]"
```

`ki_ocr.api` provides `source_render_scale`, `candidate_scales` and `select_measured_candidates`. The original `glyphfit` API and CLI remain available as compatibility interfaces.

## Run the released pipeline

Full inference uses Linux and pinned versions of the TeleOCR source, model and runtime dependencies. Configure the local paths in `runtime_binding.json`, then prepare the input images before loading the model. The repository includes the three runtime helper modules used by this version.

The [inference guide](docs/REPRODUCE.md) provides a dedicated-machine CLI and a managed-cluster Python entry, including GPU admission and work-window settings. See the [dependency documentation](docs/DEPENDENCIES.md) for the pinned environment.

## Reproduce evaluation

The release includes predictions for all 1,651 pages and the accompanying evaluation package:

- [Markdown predictions](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_OmniDocBench_v1.6_predictions.zip)
- [Evaluation configuration, results and manifests](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_EVALUATION_CONFIG_AND_RESULTS_R6.zip)
- [Release inference configuration](https://github.com/yushuosun/Ki-OCR/blob/ki-ocr-repro-r6/configs/ki_ocr_ab.json)
- [Same-generation control predictions](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_same_generation_baseline_predictions.zip)
- [Per-page scores, tokens and completion records](docs/EVIDENCE.md)
- [Exact evaluation scores](https://github.com/yushuosun/Ki-OCR/blob/ki-ocr-repro-r6/results/frozen_full1651.json)

The prediction archives contain Markdown only; referenced image crops are not included.

Verify the released predictions against the supplied manifest:

```bash
mkdir -p outputs/evaluation outputs/predictions/GLYPHFIT_FULL

python -m zipfile -e \
    artifacts/submission/Ki-OCR_EVALUATION_CONFIG_AND_RESULTS_R6.zip \
    outputs/evaluation

python -m zipfile -e \
    artifacts/submission/Ki-OCR_OmniDocBench_v1.6_predictions.zip \
    outputs/predictions/GLYPHFIT_FULL

python -m ki_ocr verify-predictions \
    --predictions outputs/predictions/GLYPHFIT_FULL \
    --manifest outputs/evaluation/metadata/PREDICTION_FILES_SHA256.json
```

When all files match, the command reports `status: MATCH` with a matching count of 1,651.

Follow the [evaluation guide](docs/EVALUATE.md) to verify the prediction files and run the official OmniDocBench evaluator.

## Acknowledgments

Ki-OCR builds on TeleOCR-1.2B and uses OmniDocBench for document parsing evaluation. We thank the authors and maintainers for their open-source work.

## License

Project source code is licensed under [MIT](LICENSE). See [THIRD_PARTY.md](THIRD_PARTY.md) for external components and document-content rights.
