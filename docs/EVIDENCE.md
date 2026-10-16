# Released evidence and record scope

The 2026-10-16 evidence recovery checked the original terminal records, both official-score outputs and all 3,302 page-arm prediction hashes against the final binding. It did not run model inference or the official scorer again.

| Evidence | Contents |
|---|---|
| [run_completion.json](../artifacts/evidence/run_completion.json) | Five completed runs, source result/end/journal hashes, inference configuration and model identity |
| [prediction_manifest.json](../artifacts/evidence/prediction_manifest.json) | SHA256 and byte size for both arms on all 1,651 pages |
| [per_page_metrics.json](../artifacts/evidence/per_page_metrics.json) | Seven recorded metrics per page and arm, with null for inapplicable metrics |
| [per_page_tokens.json](../artifacts/evidence/per_page_tokens.json) | Content and layout image-token counts, ROI counts and producing run per page-arm |
| [recomputed_statistics.json](../results/recomputed_statistics.json) | Reconstructed macros, content-token totals and paired page-bootstrap interval |
| [statistics script](../scripts/recompute_statistics.py) | CPU-only calculation from the released per-page records |

The first four pages contribute eight page-arm outputs from the initial completed smoke run. The remaining runs contribute 824, 824, 824 and 822 outputs. The final binding contains all 3,302 distinct page-arm slots, with zero unresolved slots and zero failed-attempt slots recorded in that binding.

Token counts were recovered by counting the model's image token ID `151655` in the actual engine `prompt_token_ids`. The pinned model configuration hash is recorded with the export. Each page-arm has a layout request followed by content ROI requests; zero-ROI pages contribute zero content tokens. Layout tokens are stored separately. The Ki-OCR counts also match its recorded selected-processor-token totals. The baseline's selected-token summary fields were empty, so its counts were recovered from engine requests rather than imputed.

Content totals are **7,046,845** tokens for the control and **3,393,255** for Ki-OCR: **4,268.228346456693** and **2,055.272562083586** per page, a **51.84717416091882%** reduction. This scope excludes layout, warmup and CPU candidate measurement work. No end-to-end speedup is established by these counts.

Recomputing the recorded finite-page metrics reproduces Overall **97.61704895861511** and **98.40951176937257**, and the **0.7924628107574563** percentage-point difference. A paired page bootstrap with PCG64 seed 20261014 and 20,000 replicates reproduces the 95% percentile interval **[0.5310502903871427, 1.083471136802443]** percentage points. Document/source clusters are unavailable; the interval describes uncertainty conditional on these evaluated pages. Reading-order ED increases from **0.11836990858561101** to **0.11870025939656478**; Overall does not include that metric.

## Configuration and completion

The release configuration is [configs/ki_ocr_ab.json](../configs/ki_ocr_ab.json). Every runtime value is exactly equal to the configuration used for the recorded run. Only three descriptive metadata fields were changed or removed; the [mapping and hashes](../metadata/configuration_equivalence.json) allow this to be verified. The original file is retained byte-for-byte under `metadata/history/`.

The [release status](../metadata/RELEASE_STATUS.json) records 1,651 pages and 3,302 completed page-arm outputs, linked to the original configuration hash and the terminal evidence. Configuration identity, execution completion and publication identity are recorded separately.

The public records contain numerical measurements, terminal states, prediction identities and source hashes. Request text and internal machine paths are excluded.

This repair was validated on CPU. A fresh-checkout GPU inference run and independent leaderboard acceptance have not been verified.
