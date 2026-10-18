# llm_infra 开发计划

> 项目方向：大语言模型结构、推理引擎构建、性能推理优化
> 基准模型：Qwen3-0.6B（已下载至 `models/Qwen3-0.6B`）

---

## 一、项目目标

基于本地 Qwen3-0.6B 模型，按以下三个方向逐步构建完整的 LLM 推理基础设施：

1. **模型结构**：深入理解并动手实现 LLM 核心组件，做到"手写可跑、跑得正确"。
2. **推理引擎**：构建具备请求调度、动态批处理、KV Cache 的推理引擎，并提供服务化接口。
3. **性能优化**：在正确性的基础上做吞吐/延迟优化，与 vLLM 基线做对比并产出数据。

---

## 二、总体路线图（三阶段）

```
阶段一 模型结构理解与实现
   │
   ▼
阶段二 推理引擎构建
   │
   ▼
阶段三 性能推理优化
```

三个阶段顺序推进，每个阶段结束时有可验证的交付物与基准数据。

---

## 三、阶段一：大语言模型结构

**目标**：用 PyTorch 从零实现 Qwen3-0.6B 的完整前向推理（不使用 transformers 的模型类，仅复用其权重与分词器）。

### 任务清单

- [ ] T1.1 阅读 `config.json`，梳理 Qwen3-0.6B 架构参数（28 层、hidden 1024、GQA 8 组 KV、RoPE、SwiGLU、RMSNorm、tie_word_embeddings）
- [ ] T1.2 实现分词与 Embedding 层（复用 `tokenizer.json` / `vocab.json` / `merges.txt`）
- [ ] T1.3 实现 RMSNorm 与 SwiGLU Feed-Forward 网络
- [ ] T1.4 实现旋转位置编码 RoPE（含高频/低频维度计算）
- [ ] T1.5 实现 GQA 分组查询注意力（含 causal mask）
- [ ] T1.6 组装 Qwen3 解码器层与完整 `Qwen3ForCausalLM` 前向
- [ ] T1.7 从 `model.safetensors` 加载权重并完成权重映射（含 tie 权重处理）
- [ ] T1.8 实现自回归生成循环 + 采样策略（top-k / top-p / temperature）
- [ ] T1.9 **验证**：与 HuggingFace Transformers 输出做数值对比（同 seed 下 logits 误差 < 1e-4，生成文本一致）

### 交付物

- `src/model/` 下完整可运行的从零实现代码
- `tests/` 数值对比测试
- 阶段报告：架构图 + 各组件实现说明

---

## 四、阶段二：推理引擎构建

**目标**：在阶段一正确实现的基础上，构建具备工程能力的推理引擎并服务化。

### 任务清单

- [ ] T2.1 引入 **KV Cache**，消除 prefill 阶段的重复计算
- [ ] T2.2 实现 **Continuous Batching（连续动态批处理）**：请求随时加入、完成的请求随时退出
- [ ] T2.3 实现请求调度器（FCFS / 带优先级），支持并发请求队列
- [ ] T2.4 实现 **Prefill / Decode 分离** 的两阶段执行
- [ ] T2.5 提供 OpenAI 兼容的 HTTP API（`/v1/chat/completions`），支持流式输出（SSE）
- [ ] T2.6 支持并发安全与多请求隔离；加入基础日志与监控指标（QPS、延迟分位数、吞吐）
- [ ] T2.7 **验证**：并发请求下吞吐与正确性（与单请求结果一致）

### 交付物

- `src/engine/` 推理引擎核心（scheduler、batch、kv_cache）
- `src/server/` 服务化接口
- 阶段报告：调度策略说明 + 并发基准数据

---

## 五、阶段三：性能推理优化

**目标**：以吞吐（tokens/s）与延迟（TTFT/TPOT）为核心指标持续优化，并给出与 vLLM 的对比。

### 任务清单

- [ ] T3.1 **KV Cache 内存优化**：实现 PagedAttention 思想的分页缓存，降低碎片与显存占用
- [ ] T3.2 **量化**：对模型做 INT8 / INT4（GPTQ 或 AWQ）量化，评估精度损失与加速比
- [ ] T3.3 **算子层面优化**：fused RMSNorm+QKV、fused attention、GQA 高效实现、算子融合
- [ ] T3.4 **CUDA Graph** 捕获解码阶段，减少 kernel launch 开销（如有 GPU）
- [ ] T3.5 **投机采样 Speculative Decoding**（可选，作为进阶项）
- [ ] T3.6 **分布式**：张量并行（TP）/ 流水线并行（PP）扩展（多卡场景）
- [ ] T3.7 **基准测试**：建立 benchmark 脚本，对比优化前后与 vLLM 基线

### 交付物

- 各优化项的独立实现与开关（可通过配置启用）
- benchmark 报告（吞吐 / 延迟 / 显存 / 精度损失对比表）

---

## 六、里程碑

| 里程碑 | 内容 | 完成标志 |
|---|---|---|
| M1 | 模型结构实现 | 与 Transformers 输出一致，测试通过 |
| M2 | 推理引擎可用 | 服务化 API 并发请求吞吐正确 |
| M3 | 首轮性能优化 | 吞吐相对基线 ≥ 2x（或达到 vLLM 的 60%+） |
| M4 | 量化落地 | 精度可接受（损失 < 1%），加速显著 |
| M5 | 分布式扩展 | 多卡吞吐近线性扩展 |

---

## 七、测试与验证策略

- 每个阶段有独立 `tests/`，核心是**正确性**（与 Transformers / vLLM 输出对比）
- 数值对比规则：同 seed、同参数下 logits 相对误差阈值、生成文本一致性
- 性能测试：固定 prompt 长度与并发数的标准化脚本，记录 TTFT / TPOT / 吞吐 / 显存
- 所有优化必须有"关闭优化也能跑通"的开关，保证可回退

---

## 八、目录结构规划

```
llm_infra/
├── docs/                    # 文档与阶段报告
├── models/                  # 权重目录（.gitignore 忽略，不入库）
│   └── Qwen3-0.6B/
├── src/
│   └── llm_infra/           # 唯一包名，避免顶层包冲突
│       ├── model/           # 阶段一：从零模型实现
│       ├── engine/          # 阶段二：推理引擎（scheduler/batch/kv_cache）
│       └── server/          # 阶段二：HTTP 服务
├── scripts/
│   └── download_model.py    # 模型获取方式（可复现）
├── benchmarks/              # 基准测试脚本与结果
├── tests/                   # 正确性与性能测试（镜像 src 结构）
├── pyproject.toml           # src 布局打包 + 依赖声明
└── .gitignore               # 含 models/、*.safetensors 等规则
```

> 说明：`models/` 与权重文件不入 git 仓库，换环境时执行 `python scripts/download_model.py` 重新获取。

---

## 九、环境与依赖（uv 管理）

本项目使用 [uv](https://docs.astral.sh/uv/) 进行项目管理（依赖解析、锁文件、虚拟环境一体化）。

- Python 3.12（由 `.python-version` 指定，uv 自动下载管理）
- PyTorch（CUDA 版，RTX 3060 12GB 可用；如无 GPU 先以 CPU 验证正确性）
- `transformers` / `tokenizers`（仅用于加载权重、分词器与数值对比基线）
- `safetensors`（权重加载）
- `fastapi` / `uvicorn`（服务化，extras：`server`）
- vLLM 源码（`/home/lvlang/workspace/vllm`）作为优化参考与对比基线

### 常用命令

```bash
uv sync --all-extras          # 创建 .venv 并安装全部依赖（含 uv.lock 锁定）
uv run python <script.py>     # 在项目环境中运行脚本
uv run pytest                 # 运行测试
uv add <package>              # 新增依赖（自动写入 pyproject.toml 并锁定）
uv run python scripts/download_model.py  # 下载模型权重
```

---

## 十、执行顺序建议

1. 先完成阶段一全部任务（这是后续一切的地基，务必保证正确性）
2. 阶段二在阶段一正确实现上迭代，先单线程跑通再上并发
3. 阶段三优先做 KV Cache 分页与算子融合（收益最直接），量化与分布式视硬件条件推进
4. 每阶段结束更新 `docs/` 下阶段报告，沉淀 benchmark 数据
