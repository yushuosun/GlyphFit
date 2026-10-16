# Evaluate the predictions

From the Ki-OCR repository root, extract both release attachments and verify the predictions:

```bash
mkdir -p outputs/evaluation outputs/predictions/GLYPHFIT_FULL
python -m zipfile -e artifacts/submission/Ki-OCR_EVALUATION_CONFIG_AND_RESULTS_R6.zip outputs/evaluation
python -m zipfile -e artifacts/submission/Ki-OCR_OmniDocBench_v1.6_predictions.zip outputs/predictions/GLYPHFIT_FULL
python -m ki_ocr verify-predictions --predictions outputs/predictions/GLYPHFIT_FULL --manifest outputs/evaluation/metadata/PREDICTION_FILES_SHA256.json
```

Use the official [OmniDocBench evaluator](https://github.com/opendatalab/OmniDocBench) at `f133a71e9e91c3621c7ce8994200a7b394a06eb3` with its CDM/TeX/ImageMagick/Ghostscript environment. Obtain the official GT separately; its SHA256 is `a45cd84b04ad8b793e775089640e6b681209abea33ead54c1828ddca35fae496`. Version checks are recorded in [metadata](../metadata/current_official_version_check.json).

Edit **`outputs/evaluation/configs/end2end.yaml`**, created by the extraction above. Set `ground_truth.data_path` to the absolute GT path and `prediction.data_path` to the absolute path of `outputs/predictions/GLYPHFIT_FULL`. Use absolute paths so the evaluator working directory does not change which files are read. The supplied YAML uses `quick_match`, a 420-second match timeout, a 300-second truncated timeout, fallback maximum span 10, order penalty 0.1 and 8 match/CDM/TEDS workers. The scoring run used BLAS 1. Retain these settings for reproduction. Run in the evaluator checkout, replacing the example absolute paths:

```bash
cd /absolute/path/OmniDocBench
git checkout f133a71e9e91c3621c7ce8994200a7b394a06eb3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python pdf_validation.py --config /absolute/path/Ki-OCR/outputs/evaluation/configs/end2end.yaml
```

The full evaluation contains 1651 pages. Text ED uses 1557 valid pages, formula CDM 313, table TEDS 458 and reading order ED 1638. Overall is the equal-weight mean of text accuracy, formula CDM and table TEDS. In the exact result JSON, component metrics are raw ratios and Overall is a percentage.

The prediction archives contain Markdown only; referenced image crops are not included. The pinned evaluator parses the Markdown without loading these crop files.

The verifier checks file count, image-stem filenames, byte sizes, SHA256 and extra Markdown files. All 1,651 files must match.

## Control and numerical checks

The control uses original input scales with the same generation settings as Ki-OCR. Its requested output cap is 32,768; it is a distinct configuration from TeleOCR's upstream 16k default. The [control prediction ZIP](../artifacts/submission/Ki-OCR_same_generation_baseline_predictions.zip), [paired prediction manifest](../artifacts/evidence/prediction_manifest.json), [per-page scores and tokens](EVIDENCE.md), and [statistics script](../scripts/recompute_statistics.py) are published. To score the control, extract that ZIP into its own directory and change only the prediction path in a copy of the scoring YAML.

From the Ki-OCR root, using Python 3.11 or newer, reproduce aggregate metrics, content-token totals and the paired 20,000-replicate page bootstrap without a model or GT:

```bash
python -m pip install numpy==2.4.5
python scripts/recompute_statistics.py --output outputs/recomputed_statistics.json
```

This command uses the released numerical evidence; the official evaluator independently recomputes scores from predictions and GT. The page bootstrap does not account for document/source clustering. Content-token savings cover recognition inputs; they do not measure end-to-end latency, GPU time or total pipeline work. Full scope and run completion evidence are described in [EVIDENCE.md](EVIDENCE.md).
