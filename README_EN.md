# Ki-OCR

[简体中文](README.md) · [Method](#why-input-scale-matters) · [Full results and evaluation protocol](docs/EVALUATE.md) · [Release materials](docs/RELEASE.md) · [Run the pipeline](#run-the-pipeline)

Ki-OCR is a training-free inference-time adaptation method built on a frozen TeleOCR-1.2B. Without modifying TeleOCR's architecture or model weights, Ki-OCR adaptively adjusts the input scales of document pages and detected layout regions according to the visual scale of the input document. This allows different regions to be parsed at scales better suited to recognition while improving visual budget utilization.

On **OmniDocBench v1.6_full (1,651 pages)**, the released Ki-OCR configuration achieves **98.40951 Overall**. The recorded statistics show that, compared with TeleOCR, Ki-OCR reduces average content-recognition visual tokens per page from 4268.23 to 2055.27, a reduction of 51.85%.

## Why input scale matters

A document page may contain large headings, dense body text, tables and formulas. The input passes through page rendering, region preprocessing and the model's image processor, each of which can change the scale that the model actually sees. A uniform page-level setting may spend visual tokens on unnecessary enlargement while still presenting small text at a scale that is difficult to recognize.

Ki-OCR comprises two complementary modules:

- **Source-aware Rendering:** Aligns the page-rendering scale with the source document resolution to reduce redundant visual computation.
- **Region-adaptive Scaling:** Adaptively selects suitable input scales based on the visual characteristics of text and table regions, within the model's visual and context budgets.

The two modules allocate input detail at the page and region levels, respectively. TeleOCR performs layout analysis, content recognition, post-processing and Markdown assembly.

## Run the pipeline

The steps below run full inference on a dedicated Linux machine with an NVIDIA GPU. For shared clusters, see the [cluster integration instructions](docs/REPRODUCE.md#managed-cluster).

### 1. Install the code and inference environment

```bash
git clone https://github.com/yushuosun/Ki-OCR.git
cd Ki-OCR
git checkout ki-ocr-repro-r6
```

Obtain the pinned [TeleOCR source](https://github.com/caipeng328/TeleOCR/tree/9921cffe380efe4e2fa010258b3d0c3cb70bab2d) and [TeleOCR-1.2B model](https://huggingface.co/XingChen-AGI/TeleOCR/tree/e92585356c0d0b7b7a65938f3da035c6593cc9a6), then set up the inference environment following the [TeleOCR installation instructions](https://github.com/caipeng328/TeleOCR/blob/9921cffe380efe4e2fa010258b3d0c3cb70bab2d/README.md). The release uses vLLM 0.11.0, torch 2.8.0+cu128, transformers 4.57.6 and pypdfium2 4.30.0. See [environment/requirements-tele.lock](environment/requirements-tele.lock) for the full version list and the [dependency documentation](docs/DEPENDENCIES.md) for component and file checks.

Install Ki-OCR and its image-processing dependencies in that environment:

```bash
python -m pip install -e ".[vision]"
```

### 2. Configure source and model paths

```bash
cp configs/runtime_binding.example.json runtime_binding.json
```

Edit `runtime_binding.json`: replace `source` and `model` with local absolute paths and set `execution_policy` to `standalone`:

```json
{
  "source": "/absolute/path/to/TeleOCR",
  "model": "/absolute/path/to/TeleOCR-1.2B",
  "runtime_helpers": "bundled",
  "execution_policy": "standalone"
}
```

Check dependency versions, source files and model weights:

```bash
python -m ki_ocr doctor --binding runtime_binding.json --verify-weight
```

### 3. Prepare input images

Replace the input path below with your image directory. To reproduce the released results, use all 1,651 page images from OmniDocBench v1.6_full.

```bash
mkdir -p outputs
python -m ki_ocr prepare \
    --binding runtime_binding.json \
    --input /absolute/path/to/OmniDocBench/images \
    --output outputs/prepared1651.json

PREPARED_SHA256=$(python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('outputs/prepared1651.json').read_bytes()).hexdigest())")
```

This CPU step checks the inputs and writes the run manifest. If you subsequently change the configuration or paths, repeat this step and calculate the new SHA256.

### 4. Run inference

Inspect GPU physical indices, UUIDs and current usage:

```bash
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu --format=csv
```

The example below selects GPU 0 and a four-hour runtime limit; adjust both for your machine and workload. The limit includes model loading and is not an estimate of the time required for 1,651 pages. The standalone runner requires the selected GPU to report zero memory usage and zero utilization.

```bash
GPU_INDEX=0
GPU_UUID=$(nvidia-smi -i "$GPU_INDEX" --query-gpu=uuid --format=csv,noheader)
WORK_SECONDS=14400

python -m ki_ocr run-standalone \
    --prepared outputs/prepared1651.json \
    --prepared-sha "$PREPARED_SHA256" \
    --output outputs/run_001 \
    --device "$GPU_INDEX" \
    --uuid "$GPU_UUID" \
    --work-seconds "$WORK_SECONDS"
```

The pipeline runs both Ki-OCR and the original-input baseline with the same generation settings. Markdown outputs are saved to:

- Ki-OCR: `outputs/run_001/markdown/GLYPHFIT_FULL/`
- Original-input baseline: `outputs/run_001/markdown/OFFICIAL_ORIGINAL/`

Check the returned `status` and `completed_page_arm_N`. A complete two-configuration run over 1,651 pages contains 3,302 completed items; process exit alone does not establish completion. Use a new output directory for each new run.

The inference settings are in [configs/ki_ocr_ab.json](configs/ki_ocr_ab.json). Both configurations use the same model and generation settings, with a requested output cap and context window of 32,768 tokens; the effective output allowance depends on input length. See “Reproduce evaluation” below for scoring, or the [inference guide](docs/REPRODUCE.md) for additional interfaces and configuration details.

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
