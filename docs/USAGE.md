# llm_infra 使用手册（uv 篇）

> 面向对象：初次接触本项目的开发者
> 核心工具：[uv](https://docs.astral.sh/uv/) —— 一个用 Rust 编写的 Python 包与环境管理器，替代 `pip + venv + pip-tools` 的组合
> 阅读方式：每一步操作均附"原理"说明，理解后可以举一反三

---

## 0. 前置条件：安装 uv

```bash
# 官方安装脚本（Linux/macOS）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或通过 pip 安装
pip install uv
```

**原理**：uv 是单一二进制程序，不依赖 Python 本体即可运行。它内置了 Python 版本管理、依赖解析（PubGrub 算法）、虚拟环境创建、包安装四件事，速度比 pip 快一个数量级（并行下载 + 全局缓存 + 硬链接安装）。

验证安装：

```bash
uv --version   # 输出 uv 0.13.1 或更高
```

---

## 1. 首次搭建：克隆并安装依赖

```bash
git clone <本项目仓库地址>
cd llm_infra
uv sync --all-extras
```

**这一条命令背后发生了什么（原理拆解）**：

1. **确定 Python 版本**：uv 读取项目根目录的 [.python-version](../.python-version)（内容为 `3.12`）。若本机没有 3.12，uv 会自动下载一份托管的 CPython（存放在 `~/.local/share/uv/python/`），不污染系统 Python。
   > 本机系统 Python 是 3.14（太新，torch/transformers 生态兼容性差），所以我们显式锁定 3.12 —— 稳定版本优先。

2. **创建虚拟环境**：在项目根目录生成 `.venv/`（Linux 下即 `~/.venv/bin/python` 指向 3.12）。虚拟环境把项目依赖与系统、与其他项目隔离开，互不干扰。

3. **按锁文件精确安装**：uv 读取 [pyproject.toml](../pyproject.toml) 声明的依赖 + [uv.lock](../uv.lock) 锁定的**精确版本**，从清华镜像下载并安装。
   > 为什么不直接 `pip install`？—— pyproject 里只写了 `torch>=2.0` 这类**范围约束**，不同时间安装会得到不同版本，导致"我这能跑你那不能跑"。uv.lock 把解析结果（含每个包的哈希值）固化下来，任何人在任何机器上执行 `uv sync` 都得到**完全一致**的环境。这就是"可复现构建"，也是 uv.lock 必须提交进 git 的原因。

4. **安装项目自身**：因为 pyproject.toml 定义了 `[build-system]`，uv 会把 `src/llm_infra` 包以 **editable（可编辑）模式**安装进 `.venv`。
   > editable 意味着 `.venv` 里的包只是指向 `src/llm_infra/` 的引用——你改源码后**无需重新安装**，`import llm_infra` 立即生效。src 布局（代码放 `src/` 下而非项目根）则强制你必须"安装后使用"，避免误从当前目录 import 未安装版本。

5. **`--all-extras` 的含义**：pyproject.toml 里把依赖分了组——基础依赖（torch/transformers 等）、`server` 组（fastapi/uvicorn）、`dev` 组（pytest）。`--all-extras` 表示全装；若只 `uv sync` 则只装基础组。
   > extras 适合"可选功能"：不部署服务的人不必下载 uvicorn。

> **镜像说明**：pyproject.toml 末尾的 `[[tool.uv.index]]` 把默认源指向清华 TUNA（`default = true`）。原理是所有包的**解析与下载**都走该镜像。本机实测：PyPI 直连约 180KB/s（2.5GB 要 4 小时），清华镜像约 15MB/s（3 分钟）。如果你在海外或有代理，删掉这段配置即可恢复直连。

---

## 2. 下载模型权重

```bash
# 可选：国内网络设置 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com

uv run python scripts/download_model.py
```

**原理**：

- **`uv run` 而非 `python`**：`uv run` 执行前会先校验 `.venv` 与 uv.lock 是否一致（不一致自动补齐），然后**在 `.venv` 环境里**运行命令。直接敲 `python` 用的是系统 Python（可能没有装依赖），敲 `.venv/bin/python` 则要求你先手动激活环境——`uv run` 一步到位。
- **脚本做的事**：调用 `huggingface_hub.snapshot_download`，把 `Qwen/Qwen3-0.6B` 整仓（权重 + 分词器 + 配置）下载到 `models/Qwen3-0.6B/`。
- **权重不入 git**：`.gitignore` 已忽略 `models/` 与 `*.safetensors`。1.5GB 的二进制放进 git 会让仓库永久膨胀（git 对历史中的大文件无能为力），换机器时重新下载即可。

---

## 3. 日常开发命令速查

| 场景 | 命令 | 原理 |
|---|---|---|
| 运行任意脚本 | `uv run python xxx.py` | 自动同步环境后在 .venv 中执行 |
| 运行测试 | `uv run pytest` | 同上；pytest 在 dev extras 中 |
| 新增依赖 | `uv add numpy` | 写入 pyproject.toml → 重新解析 → 更新 uv.lock → 装入 .venv，三步原子完成 |
| 新增到某组 | `uv add --optional server xxx` | 加进 `[project.optional-dependencies].server` |
| 移除依赖 | `uv remove xxx` | 同 add，反向操作 |
| 升级单个包 | `uv lock --upgrade-package torch` | 只重新解析该包的版本约束 |
| 升级全部 | `uv lock --upgrade` 后 `uv sync` | lock 只改锁文件，sync 才落盘 |
| 查看 Python | `uv python list` | 列出 uv 可见的所有解释器 |

> 注意：**永远不要**手动 `pip install` 进 `.venv`——绕过 lock 后环境与锁文件不一致，下次 `uv sync` 会被"纠正"回锁定版本，你的包会莫名消失。

---

## 4. 关键文件一览

```
llm_infra/
├── .python-version    # uv 据此选择 Python 版本（原理见 §1.1）
├── pyproject.toml      # 依赖"范围"声明 + 构建配置 + 镜像配置 → 提交 git
├── uv.lock             # 依赖"精确"锁定（含哈希）→ 提交 git
├── .venv/              # 虚拟环境（uv 生成）→ .gitignore 忽略，可随时删掉重建
├── src/llm_infra/      # 源码（editable 安装，改动即时生效）
├── scripts/            # 工具脚本
├── models/             # 模型权重 → 不入 git
└── docs/               # 文档（本手册所在）
```

**删了 `.venv` 怎么办？** 重新 `uv sync --all-extras` 即可——安装包都在 `~/.cache/uv` 全局缓存里（按内容寻址，硬链接到各项目 venv），重装几乎不耗流量、秒级完成。这也解释了为什么 uv 装第二遍同样的包会非常快。

---

## 5. 换机器 / CI 场景

```bash
git clone <repo> && cd llm_infra
uv sync --all-extras          # 有网即可，Python/依赖/包自身全自动
uv run python scripts/download_model.py   # 拉权重
uv run pytest                 # 验证环境正确
```

**原理**：uv.lock + .python-version + pyproject.toml 三件套完整描述了环境，`.venv` 只是可再生的派生物。环境即代码（environment as code）。

---

## 6. 常见问题

**Q1：为什么 `python xxx.py` 报 `ModuleNotFoundError: No module named 'llm_infra'`？**
因为直接敲 `python` 用的是 shell 当前 PATH 里的解释器（如 miniconda），不是项目 `.venv`。用 `uv run python xxx.py`，或先 `source .venv/bin/activate` 再用 `python`。

**Q2：`uv run` 很慢？**
它每次会校验环境同步。若只是反复跑同一个脚本，可 `uv run --no-sync` 跳过校验。

**Q3：如何确认当前环境里装了什么版本？**
`uv pip list`（uv 提供的 pip 兼容接口）或 `uv tree`（看依赖树）。

**Q4：torch 装的是 GPU 版还是 CPU 版？**
本项目未特殊配置，Linux 下 PyPI 源默认安装 CUDA 版（`2.14.1+cu130`）。验证：`uv run python -c "import torch; print(torch.cuda.is_available())"`。

---

## 附：本项目开发路线

环境就绪后，按 [PLAN.md](PLAN.md) 的三阶段推进：模型结构从零实现 → 推理引擎 → 性能优化。
