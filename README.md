# Ki-OCR

[English](README_EN.md) · [方法说明](#为什么输入尺度重要) · [完整结果与评测协议](docs/EVALUATE.md) · [发布材料](docs/RELEASE.md) · [运行流程](#运行流程)

Ki-OCR 是一种基于 frozen TeleOCR-1.2B 的 training-free inference-time adaptation 方法。Ki-OCR 不修改 TeleOCR 的模型架构和模型权重，而是根据输入文档的视觉尺度，自适应调整整页及检测到的 layout region 的输入尺度，使不同区域以更适合识别的尺度进行解析，并且提高视觉预算的使用效率。

在 **OmniDocBench v1.6_full（1,651 页）** 上，已发布的 Ki-OCR 配置取得 **98.40951 Overall**。统计来看，相比于 TeleOCR，Ki-OCR 的平均每页内容识别视觉 token 从 4268.23 降至 2055.27，减少 51.85%。

## 为什么输入尺度重要

一页文档可能同时包含大标题、密集正文、表格和公式。输入会依次经过整页渲染、区域预处理和模型的图像处理器，每个环节都可能改变模型实际看到的尺度。统一的整页设置可能将视觉 token 花在不必要的放大上，同时仍让小字处于不利于识别的尺度。

Ki-OCR 包含两个互补模块：

- **Source-aware Rendering：** 使整页渲染尺度与源文档分辨率相协调，减少冗余视觉计算。
- **Region-adaptive Scaling：** 根据文本和表格区域的视觉特征，在模型的视觉与上下文预算内自适应选择适合的输入尺度。


## 运行流程

以下步骤用于在独立 Linux 机器上运行完整推理，需要 NVIDIA GPU。共享集群的接入方式见[集群运行说明](docs/REPRODUCE.md#managed-cluster)。

### 1. 安装代码与推理环境

```bash
git clone https://github.com/yushuosun/Ki-OCR.git
cd Ki-OCR
git checkout ki-ocr-repro-r6
```

准备固定版本的 [TeleOCR 源码](https://github.com/caipeng328/TeleOCR/tree/9921cffe380efe4e2fa010258b3d0c3cb70bab2d)和 [TeleOCR-1.2B 模型](https://huggingface.co/XingChen-AGI/TeleOCR/tree/e92585356c0d0b7b7a65938f3da035c6593cc9a6)，按 [TeleOCR 安装说明](https://github.com/caipeng328/TeleOCR/blob/9921cffe380efe4e2fa010258b3d0c3cb70bab2d/README.md)建立推理环境。发布配置使用 vLLM 0.11.0、torch 2.8.0+cu128、transformers 4.57.6 和 pypdfium2 4.30.0；完整版本列表见 [environment/requirements-tele.lock](environment/requirements-tele.lock)，组件与文件校验说明见[依赖文档](docs/DEPENDENCIES.md)。

在该推理环境中安装 Ki-OCR 及图像处理依赖：

```bash
python -m pip install -e ".[vision]"
```

### 2. 配置源码与模型路径

```bash
cp configs/runtime_binding.example.json runtime_binding.json
```

编辑 `runtime_binding.json`，将 `source` 和 `model` 替换为本机的绝对路径，并将 `execution_policy` 设为 `standalone`：

```json
{
  "source": "/absolute/path/to/TeleOCR",
  "model": "/absolute/path/to/TeleOCR-1.2B",
  "runtime_helpers": "bundled",
  "execution_policy": "standalone"
}
```

检查依赖版本、源码文件和模型权重：

```bash
python -m ki_ocr doctor --binding runtime_binding.json --verify-weight
```

### 3. 准备输入图像

将下面的输入路径替换为待处理图像目录。复现发布结果时，使用 OmniDocBench v1.6_full 的全部 1,651 页图像。

```bash
mkdir -p outputs
python -m ki_ocr prepare \
    --binding runtime_binding.json \
    --input /absolute/path/to/OmniDocBench/images \
    --output outputs/prepared1651.json

PREPARED_SHA256=$(python -c "import hashlib; from pathlib import Path; print(hashlib.sha256(Path('outputs/prepared1651.json').read_bytes()).hexdigest())")
```

该步骤在 CPU 上检查输入并生成运行清单。准备完成后如需修改配置或路径，请重新执行此步骤并计算新的 SHA256。

### 4. 运行推理

先查看可用 GPU 的物理编号、UUID 和占用情况：

```bash
nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu --format=csv
```

下面以 GPU 0 和 4 小时运行上限为例，请按实际设备和任务规模修改。运行上限包含模型加载时间，不是处理 1,651 页所需时间的估计。独立机器入口要求选定 GPU 的显存占用和利用率均为 0。

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

该流程会运行 Ki-OCR 和采用相同生成设置的原始输入对照。Markdown 分别保存在：

- Ki-OCR：`outputs/run_001/markdown/GLYPHFIT_FULL/`
- 原始输入对照：`outputs/run_001/markdown/OFFICIAL_ORIGINAL/`

运行结束后检查返回的 `status` 和 `completed_page_arm_N`。完整的双组 1,651 页运行应包含 3,302 个完成项；程序退出并不一定表示所有页面均已完成。每次新运行请使用新的输出目录。

推理配置见 [configs/ki_ocr_ab.json](configs/ki_ocr_ab.json)。两组使用相同模型和生成设置，请求输出上限与上下文窗口均为 32,768 tokens，实际可生成长度受输入长度约束。结果评分步骤见下方“复现评测”，更多运行接口和配置说明见[推理指南](docs/REPRODUCE.md)。

## 已发布结果

以下选取 [OmniDocBench v1.6_full 官方榜单](https://github.com/opendatalab/OmniDocBench/blob/f133a71e9e91c3621c7ce8994200a7b394a06eb3/README.md#end-to-end-evaluation)中 Overall 最高的五项，与 Ki-OCR 对照（核对日期：2026-10-16）。Ki-OCR 的本地评测分数高于当前榜首，尚未被官方榜单收录。

| 方法 | Overall ↑ | 文本 ED ↓ | 公式 CDM ↑ | 表格 TEDS ↑ | 表格 TEDS-S ↑ | 阅读顺序 ED ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **Ki-OCR** | 98.40951 | 0.02542364 | 98.94488 | 98.82602 | 99.35003 | 0.11870026 |
| TeleOCR | 96.91 | 0.0267 | 96.5895 | 96.8183 | 98.1806 | 0.1184 |
| OvisOCR2 | 96.47 | 0.0265 | 97.4854 | 94.5842 | 96.9768 | 0.1120 |
| PaddleOCR-VL-1.6 | 96.34 | 0.0326 | 97.5304 | 94.7619 | 97.1002 | 0.1278 |
| MinerU2.5-Pro | 95.75 | 0.036 | 97.45 | 93.42 | 95.92 | 0.120 |
| GLM-OCR | 95.22 | 0.044 | 97.18 | 92.83 | 95.39 | 0.133 |

Overall、CDM、TEDS 和 TEDS-S 为百分数，ED 为比例值。两组的逐页指标、token 记录及复算脚本见[公开证据](docs/EVIDENCE.md)。

本次评测覆盖 OmniDocBench v1.6_full 的全部 1,651 页，采用官方 scorer 的 `f133a71e9e91c3621c7ce8994200a7b394a06eb3` 版本及配套 quick_match 配置。[评测协议](docs/EVALUATE.md)集中说明对照设置、指标覆盖范围与已发布材料。

## 复现评测

发布材料包括全部 1,651 页的预测及配套评测包：

- [Markdown 预测](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_OmniDocBench_v1.6_predictions.zip)
- [评测配置、结果和清单](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_EVALUATION_CONFIG_AND_RESULTS_R6.zip)
- [发布推理配置](https://github.com/yushuosun/Ki-OCR/blob/ki-ocr-repro-r6/configs/ki_ocr_ab.json)
- [同生成设置对照预测](https://github.com/yushuosun/Ki-OCR/raw/ki-ocr-repro-r6/artifacts/submission/Ki-OCR_same_generation_baseline_predictions.zip)
- [逐页分数、token 与完成记录](docs/EVIDENCE.md)
- [精确评测分数](https://github.com/yushuosun/Ki-OCR/blob/ki-ocr-repro-r6/results/frozen_full1651.json)

预测压缩包仅包含 Markdown；文中的图片引用不附配图。

使用随附清单核验已发布预测：

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

全部文件匹配时，命令报告 `status: MATCH`，匹配数量为 1,651。

按[评测指南](docs/EVALUATE.md)核验预测文件，运行 OmniDocBench 官方评测器。

## 致谢

Ki-OCR 基于 TeleOCR-1.2B，并使用 OmniDocBench 进行文档解析评测。感谢作者与维护者的开源工作。

## 许可证

项目源码采用 [MIT 许可证](LICENSE)。外部组件及文档内容的权利说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。
