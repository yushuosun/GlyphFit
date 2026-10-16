# SWOCR

以尺度感知输入减少文档解析的内容识别视觉 token

[English](README_EN.md) · [方法说明](#为什么输入尺度重要) · [完整结果与评测协议](docs/EVALUATE.md) · [发布材料](docs/RELEASE.md)

SWOCR 是一种基于 frozen TeleOCR-1.2B 的 training-free inference-time adaptation 方法。SWOCR 不修改 TeleOCR 的模型架构和模型权重，而是根据输入文档的视觉尺度，自适应调整整页及检测到的 layout region 的输入尺度，使不同区域以更适合 TeleOCR 识别的尺度进行解析，并且提高视觉预算的使用效率。

在 **OmniDocBench v1.6_full（1,651 页）** 上，已发布的 SWOCR + TeleOCR-1.2B 配置取得 **98.40951 Overall**，比采用相同生成设置的原始输入对照提高 **0.79246 个百分点**，同时将每页内容识别视觉 token 减少 **51.85%**。

## 为什么输入尺度重要

一页文档可能同时包含大标题、密集正文、表格和公式。输入会依次经过整页渲染、区域预处理和模型的图像处理器，每个环节都可能改变模型实际看到的尺度。统一的整页设置可能将视觉 token 花在不必要的放大上，同时仍让小字处于不利于识别的尺度。

SWOCR 包含两个互补模块：

- **Source-aware Rendering：** 使整页渲染尺度与源文档分辨率相协调，减少冗余视觉计算。
- **Region-adaptive Scaling：** 根据文本和表格区域的视觉特征，在模型的视觉与上下文预算内选择适合的输入尺度。


## 已发布结果

OmniDocBench v1.6_full · 1,651 页 · TeleOCR-1.2B

| 配置 | Overall ↑ | 每页内容识别视觉 token ↓ |
|---|---:|---:|
| 原始输入，相同生成设置 | 97.61705 | 4268.23 |
| SWOCR A+B | **98.40951** | **2055.27** |

| 文本 ED ↓ | 公式 CDM ↑ | 表格 TEDS ↑ | 表格 TEDS-S ↑ | 阅读顺序 ED ↓ |
|---:|---:|---:|---:|---:|
| 0.02542364 | 98.94488 | 98.82602 | 99.35003 | 0.11870026 |

Overall、CDM、TEDS 和 TEDS-S 为百分数，ED 为比例值。上述 token 统计覆盖内容识别输入，不包含版面分析、预热和候选尺度测量开销，也不代表端到端耗时下降。两组的逐页指标、token 记录及复算脚本见[公开证据](docs/EVIDENCE.md)。

本次评测覆盖 OmniDocBench v1.6_full 的全部 1,651 页，采用官方 scorer 的 `f133a71e9e91c3621c7ce8994200a7b394a06eb3` 版本及配套 quick_match 配置。[评测协议](docs/EVALUATE.md)集中说明对照设置、指标覆盖范围与已发布材料。

## 快速开始

使用 Python 3.10 或更高版本安装 CPU 接口：

```bash
git clone https://github.com/yushuosun/SWOCR.git
cd SWOCR
git checkout swocr-repro-r5
python -m pip install -e .
python -m swocr --help
```

无需加载模型即可计算源感知渲染尺度：

```bash
python -m swocr a-scale \
    --page-points 612 792 --source-pixels 1224 1584
```

命令返回 `{"pre_render_scale": 2.0}`。

如需对图像进行字形测量，安装视觉依赖：

```bash
python -m pip install -e ".[vision]"
```

`swocr.api` 提供 `source_render_scale`、`candidate_scales` 和 `select_measured_candidates` 接口。原有 `glyphfit` API 与 CLI 作为兼容入口保留。

## 运行已发布流程

完整推理使用 Linux，以及固定版本的 TeleOCR 源码、模型和运行依赖。在 `runtime_binding.json` 中配置本地路径，再于加载模型前准备输入图像。仓库已包含该版本使用的三个运行时辅助模块。

[推理指南](docs/REPRODUCE.md)提供专用机器 CLI 和受管集群 Python 入口，包括 GPU 准入与工作时间窗口设置。固定环境见[依赖说明](docs/DEPENDENCIES.md)。

## 复现评测

发布材料包括全部 1,651 页的预测及配套评测包：

- [Markdown 预测](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_OmniDocBench_v1.6_predictions.zip)
- [评测配置、结果和清单](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_EVALUATION_CONFIG_AND_RESULTS_R5.zip)
- [发布推理配置](https://github.com/yushuosun/SWOCR/blob/swocr-repro-r5/configs/swocr_ab.json)
- [同生成设置对照预测](https://github.com/yushuosun/SWOCR/raw/swocr-repro-r5/artifacts/submission/SWOCR_same_generation_baseline_predictions.zip)
- [逐页分数、token 与完成记录](docs/EVIDENCE.md)
- [精确评测分数](https://github.com/yushuosun/SWOCR/blob/swocr-repro-r5/results/frozen_full1651.json)

预测压缩包仅包含 Markdown；文中的图片引用不附配图。

使用随附清单核验已发布预测：

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

全部文件匹配时，命令报告 `status: MATCH`，匹配数量为 1,651。

按[评测指南](docs/EVALUATE.md)核验预测文件，运行 OmniDocBench 官方评测器。

## 致谢

SWOCR 基于 TeleOCR-1.2B，并使用 OmniDocBench 进行文档解析评测。感谢作者与维护者的开源工作。

## 许可证

项目源码采用 [MIT 许可证](LICENSE)。外部组件及文档内容的权利说明见 [THIRD_PARTY.md](THIRD_PARTY.md)。
