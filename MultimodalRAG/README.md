# 小罗Bot · 开罗论坛的 AI 搜索引擎 Agent

> 本项目是**开罗论坛内置的 AI 搜索引擎 Agent**：多智能体协作 + 多模态 RAG，
> 先在论坛里找答案，论坛里没有（且用户允许）时再联网找。

它是论坛整体架构里的一环：

```
 vue-ui（Vue 2 + Ant Design Vue）
   │  页面：/bot  →  src/components/index/BotIndex.vue
   │  请求：POST /api/bbs/ai/chat/stream（SSE，同源）
   ▼
 springboot bbs-rest（REST 网关，:7010，context-path=/api）
   │  控制器：com.liang.bbs.rest.controller.AiBotController
   │  客户端：com.liang.bbs.rest.controller.ai.AiAgentClient
   │  配置：  ai.agent.base-url=http://127.0.0.1:7861
   ▼
 【本服务】小罗Bot AI 服务（FastAPI，:7861，仅监听本机）
   │
   ├── Agent 层：agent/        多智能体图（LangGraph）
   ├── 检索层：milvus_db/      多模态混合检索（Milvus Lite）
   ├── 索引层：ingestion/      论坛内容接入 + 分块 + 向量化
   └── 外部依赖：DashScope（多模态嵌入）/ DeepSeek（对话）/ 智谱（联网搜索）
```

浏览器**永远只跟 bbs-rest 打交道**：论坛的 devServer 只代理 `/api`，且 bbs-rest 没有
配置全局 CORS，所以直连 7861 会被浏览器拦掉；走网关还能复用论坛统一的
`{code, desc, data}` 响应信封与登录态。

---

## 1. 一条问答是怎么被回答出来的

一次提问会经过六个职责单一的智能体，由**调度智能体**动态编排：

```
                        ┌─────────────┐
       用户提问 ───────▶ │  prepare    │ 清空上一轮调度状态（保留多轮对话历史）
                        └──────┬──────┘
                               ▼
                     ┌───────────────────┐
              ┌─────▶│    supervisor     │◀──────────────┐
              │      │  调度智能体（规划） │               │
              │      └─────────┬─────────┘               │
              │                │ 按计划派发               │
              │  ┌────────┬────┼─────────┬──────────┐    │
              │  ▼        ▼    ▼         ▼          ▼    │
              │ vision  forum  web    compose   evaluate │
              │ 多模态  论坛   联网    答案      质量      │
              │ 理解    检索   搜索    合成      评估      │
              │  └────────┴────┴─────────┴──────────┘    │
              │                │                          │
              │                └── rewrite（补联网 / 重写）┘
              │                           │
              └───────────────────────────┴──────▶ END
```

| 智能体 | 职责 | 产出 |
|--------|------|------|
| **调度** `supervisor` | 用大模型规划本轮要跑哪些智能体，并按上游结论自适应改计划 | `plan` |
| **多模态理解** `vision` | 读懂用户上传的图片，产出可检索的关键词与可直接回答的部分 | `vision_note` |
| **论坛检索** `forum` | 改写检索式 → 多模态混合检索 → **判定论坛里到底有没有** | `forum_hits`、`forum_sufficient` |
| **联网搜索** `web` | 论坛不足且用户开启开关时，改写搜索词 → 智谱搜索 → 整理材料 | `web_results` |
| **答案合成** `compose` | 把材料写成带来源说明的 Markdown，**流式**输出 | `answer` |
| **质量评估** `evaluate` | 规则层 + 模型层双层打分，不通过则触发补搜/重写（各限一次） | `answer_score` |

关键设计：**"论坛里有没有相关内容"是被显式判定的**。
判据有两层 —— 大模型判断"这些片段能不能回答问题"（主判据），
以及稠密向量的余弦相似度（兜底判据，实测相关 ≈0.78~0.93、无关 ≈0.44~0.60，阈值 0.70）。
只有判定为"不足"时才会走联网，这就是需求里"论坛内得不到相关内容才联网"的落点。

---

## 2. 快速开始

### 2.1 前置条件

| 组件 | 用途 | 必需 |
|------|------|------|
| Python 3.10+ | 运行 AI 服务 | ✅ |
| MySQL（`open_bbs`） | 论坛数据源（网关不可用时的兜底） | 二选一 |
| springboot bbs-rest + ZooKeeper | 论坛数据源（推荐通道） | 二选一 |
| DashScope API Key | 多模态嵌入（图文统一向量空间） | ✅ |
| DeepSeek 兼容 API Key | 对话与规划 | ✅ |
| 智谱 API Key | 联网搜索 | 只有用联网功能时需要 |

### 2.2 装依赖

```powershell
cd MultimodalRAG
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2.3 改配置

所有配置都在 `config.yml`（唯一配置源，代码不读环境变量；示例文件为`config_example.yml`）：

```yaml
llm:
  openai:      { api_key: "...", base_url: "https://api.deepseek.com", model: "deepseek-flash" }
  multimodal:  { api_key: "...", base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1" }
  embedding:   { api_key: "...", model: "text-embedding-v4" }
  zhipu:       { api_key: "..." }        # 联网搜索用

forum:
  base_url: "http://127.0.0.1:7010/api"   # springboot 网关
  mysql:    { user: "root", password: "..." }   # 兜底数据源

ocr:
  enabled: false             # ★ OCR 总开关：配好 DotsOCR 权重/vLLM 之后才改成 true
  use_hf:  true              # true=本地权重（hf_model_path），false=远程 vLLM
  hf_model_path: "weights/DotsOCR"

server: { host: "127.0.0.1", port: 7861 }  # AI 服务监听地址
```

### 2.4 建知识库（必须先做，否则论坛检索永远为空）

```powershell
.\start_kb_sync.ps1                 # 全量同步（含图片理解）
.\start_kb_sync.ps1 -NoImages       # 跳过图片理解，快很多
.\start_kb_sync.ps1 -Status         # 只看数据源与知识库状态
```

数据源会自动降级：**springboot 网关 → 直连 MySQL → 本地快照目录**。

### 2.5 启动

```powershell
# ① AI 服务（本服务）
.\start_bot.ps1
或者启动server文件夹下的app.py（FastAPI后台）

# ② 论坛后端（另开终端；需要 ZooKeeper + MySQL + Redis）
#    在 springboot/ 目录下启动 bbs-rest（:7010）

# ③ 论坛前端（另开终端）
cd ..\vue-ui
npm run serve        # http://localhost:8082

# ④ 浏览器打开
#    http://localhost:8082/bot
```

### 2.6 只想调前端 / 没有 ZooKeeper 的时候

bbs-rest 依赖一整套中间件。如果只想把页面跑起来，可以用内置的**网关桩**
（同路径、同响应信封，直接把请求转给 AI 服务）：

```powershell
python tools\dev_gateway.py      # 监听 7010，前端配置不用改
```

于是链路变成 `vue-ui → 网关桩:7010 → AI 服务:7861`，前端代码一行都不用动。
**它不做鉴权，只用于本地联调。**

---

## 3. HTTP 接口

### 3.1 浏览器侧（经 bbs-rest 网关，统一信封 `{code, desc, data}`）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/bbs/ai/chat` | 对话（非流式，一次性返回） |
| POST | `/api/bbs/ai/chat/stream` | 对话（**SSE 流式**，页面用的就是它） |
| GET | `/api/bbs/ai/health` | 健康检查：模型 / 知识库 / 论坛数据源 |
| GET | `/api/bbs/ai/kb/status` | 知识库条目数与按来源分类（所有人可读，非管理员看不到「向量集合」） |
| POST | `/api/bbs/ai/kb/sync` | 触发论坛知识库同步（后台任务）—— **仅管理员** |
| GET | `/api/bbs/ai/kb/sync/status` | 同步进度 —— **仅管理员** |
| GET | `/api/bbs/ai/kb/upload/limits` | 上传限制（允许的扩展名、大小上限）—— **仅管理员** |
| POST | `/api/bbs/ai/kb/upload` | **上传文档附件并入库**（multipart，异步）—— **仅管理员** |
| GET | `/api/bbs/ai/kb/upload/status/{taskId}` | 附件解析/入库进度 —— **仅管理员** |
| GET | `/api/bbs/ai/kb/attachments` | 已入库的文档附件列表 —— **仅管理员** |
| DELETE | `/api/bbs/ai/kb/attachments/{docId}` | 删除附件及其知识条目 —— **仅管理员** |
| GET | `/api/bbs/ai/sessions` | 会话列表 |
| GET | `/api/bbs/ai/about` | 能力说明（页面侧栏用），附带 `currentUserIsAdmin` |

### 3.1.1 上传文档附件

去服务器上执行 `python main.py` 或 `.\start_knowledge.ps1`。
或者成为管理员在小罗Bot 页面的「知识库」面板里直接拖拽上传即可：

```
页面拖拽文件 → /api/bbs/ai/kb/upload（multipart）
            → AI 服务落盘 → 后台解析 → 分块 → 向量化 → 写入 t_knowledge_collection
            → 返回 taskId，前端轮询 /kb/upload/status/{taskId} 显示进度
```

| 格式 | 解析方式 | 依赖 |
|------|----------|------|
| `.pdf` | PyMuPDF 抽文字层；抽不到的页在 `ocr.enabled=true` 时交给 DotsOCR | 已有 |
| `.txt` / `.md` | 直接读取 | 无 |
| `.json` | 展开成 `key.path: value` 便于按字段名检索 | 无 |
| `.csv` | 逐行转成「列名: 值」；只取前 `csv_max_rows` 行 | 无 |
| `.docx` | python-docx 抽段落（标题转成 `#`）+ 表格 | `python-docx` |
| `.png/.jpg/.jpeg/.webp/.bmp` | 多模态模型生成描述，图片与描述一起向量化 | 已有 |

要点：

- **扫描件走不走 OCR，取决于 `config.yml → ocr.enabled`**（详见「3.1.3」）：
  关闭时这些页被跳过，整份文件都没有文字层就明确返回
  「很可能是扫描件或纯图片型 PDF，而 OCR 当前未启用」——**不静默入库、也不假装成功**；
  开启后这些页会用 PyMuPDF 渲染成图交给 DotsOCR 识别，结果与文字层拼进同一份正文。
- **同一个文件重复上传不会重复入库**：主键是内容摘要（`attachment:<sha1前16位>`），
  重复上传是覆盖。
- **上传者会记进知识条目的 `author` 字段**，便于溯源；列表里可以按附件删除
  （连同它的全部知识块与落盘原文件一起清掉）。
- 原文件落在 `output/attachments/`，文件名前缀是内容摘要。
- 限额都在 `config.yml → attachment`：单文件 20MB、PDF 最多 200 页、
  单次图片最多 5 张等。**网关这一层另有一道**（`ai.agent.upload-max-bytes`），
  避免大请求被打进内存再转发。
- `attachment.admin_only` 可以改成 `false` 让所有登录用户都能上传 ——
  注意那是往**大家共用的**向量库里写内容，请谨慎。

### 3.1.2 知识库面板的角色可见性

「向量集合」（`t_knowledge_collection`）属于内部实现细节，「同步论坛内容」与
「上传文档附件」都会改动**大家共用的**向量库，所以这三样**只对管理员开放**：

| 内容 | 游客 / 非管理员 | 管理员 |
|------|----------------|--------|
| 向量集合（`collection`） | 前端不渲染，**服务端也不下发该字段** | 显示 |
| 同步论坛内容（`kb/sync`） | 前端不渲染，**服务端返回 `code=1 只有管理员可以同步知识库`** | 显示 |
| 上传文档附件（`kb/upload`） | 前端不渲染，**服务端返回 `code=1 只有管理员可以上传文档到知识库`** | 显示 |
| 知识条目 / 按来源 / 论坛数据源 / 刷新 | 显示（只读） | 显示 |

- 前端判定：`isLogin && isManage`（与论坛既有约定一致，`isManage` 由
  `App.vue` 的 `getAccess()` 在角色含 `NS_SUPER_ADMIN_ROLE` 时置真）；
- 服务端判定：`AiBotController.isAdmin()`，接受 `NS_SUPER_ADMIN_ROLE`
  与 `NS_ORDINARY_ADMIN_ROLE`（普通管理员）。
  两者不完全对称是有意的 —— 普通管理员"看不到按钮但调接口不会被拒"，
  不会出现"看得见却调不通"，也不构成越权。

隐藏前端拦不住直接调接口的人，所以**服务端必须再挡一道**：改这里的权限规则时，
三处要同时改，`tools/dev_gateway.py` 的 `ADMIN_ONLY_PATHS` / `ADMIN_ONLY_PREFIXES`
/ `SANITIZE_FOR_GUEST` 就是联调桩上对应的实现。

`attachment.admin_only: false` 可以把上传放开给所有登录用户，
但要同时改前端 `BotChat.vue` 的上传区 `v-if` 与网关的 `ADMIN_ONLY_PATHS`。

### 3.1.3 扫描件与 OCR 总开关（`ocr.enabled`）

一份 PDF 能不能抽到字，取决于它**有没有文字层**：文字型 PDF 直接读文字层就行，
扫描件/纯图片型 PDF 只有像素，必须靠 OCR 识别。这两件事由
`config.yml → ocr.enabled` 一个开关统管，它代表**"你有没有把 OCR 配好"**：

| `ocr.enabled` | 解析引擎 | 扫描件 | 需要准备什么 |
|---------------|----------|--------|--------------|
| `false`（默认） | 纯 PyMuPDF | ❌ 明确报错，不静默入库 | 什么都不用配，不占显存 |
| `true` | PyMuPDF + DotsOCR | ✅ 渲染成图交给 DotsOCR 识别 | 权重放好，或 vLLM 起好 |

两条解析入口都听这个开关：

| 入口 | `false` 时 | `true` 时 |
|------|-----------|-----------|
| 页面「知识库」面板上传 | PyMuPDF 抽文字层，没有文字层的页跳过并说明原因 | 这些页走 DotsOCR，结果与文字层拼进同一份正文 |
| `.\start_knowledge.ps1`（Gradio） | PyMuPDF 抽文字层，生成同构的 `<文件名>_page_N.md` | 整份文档走 DotsOCR |

**是逐页判断，不是二选一**：能抽到文字层的页一律用 PyMuPDF（原文照搬、最快、
不占显存），只有抽不到文字的页才交给 OCR —— 所以开不开 OCR，文字型 PDF 的解析
结果完全一样。

开 `true` 之前请确认：

1. `ocr.use_hf: true` 时，权重放到 `ocr.hf_model_path`（默认 `weights/DotsOCR`）——
   仓库自带下载脚本 `tools/download_model.py`（默认拉 `rednote-hilab/dots.ocr`，
   加 `-t modelscope` 可走 ModelScope），下载目标正好是这个目录；
   再按 `requirements.txt` 里被注释掉的那三行装上 `transformers` / `torch` /
   `qwen-vl-utils`。`ocr.use_hf: false` 时，vLLM 要起在 `ocr.ip:ocr.port`
   （默认 `localhost:6006`），且 `--served-model-name` 与 `ocr.model_name` 一致。
2. **配错了不会把上传搞崩**：OCR 起不来时该页按"无文字"处理，接口会返回具体原因；
   渲染出的页面图与模型原始输出留在 `output/ocr_pages/` 下，便于排查。
3. HF 模式下权重只加载一次并常驻显存，`ocr.num_thread` 被强制为 1；
   想让整份文档并行解析，得用 vLLM 模式再调大 `ocr.num_thread`。

### 3.2 SSE 事件协议

前端按事件名分别处理：`agent`/`plan` 渲染"智能体协作过程"，
`delta` 做打字机追加，`done` 拿引用与统计。

```
event: meta      {"sessionId":"...","agents":{...},"webSearchEnabled":false}
event: plan      {"plan":["forum","web","compose"],"reason":"..."}
event: agent     {"agent":"forum","label":"论坛检索智能体","status":"start|done|skipped","detail":"..."}
event: sources   {"forum":[{...}],"web":[{...}]}
event: delta     {"text":"## 结论\n"}
event: done      {"answer":"...","usedWebSearch":true,"answerScore":0.85,
                  "citations":[...],"images":[...],"plan":[...],"trace":[...],"elapsedMs":19019}
event: error     {"message":"..."}
event: end       {}
```

### 3.3 AI 服务自身（仅内网，供网关反向代理）

`/health`、`/agent/chat`、`/agent/chat/stream`、`/agent/sessions`、
`/kb/status`、`/kb/sync`、`/kb/sync/async`、`/kb/sync/status`；
交互式文档：<http://127.0.0.1:7861/docs>

---

## 4. 多模态 RAG 是怎么做的

### 4.1 索引阶段

```
论坛内容（文章 / 评论 / 资源 / 标签）        PDF 文档
        │                                      │
        │  ingestion/forum_source.py           │  ocr.enabled ? DotsOCR : PyMuPDF
        │  REST 网关 → MySQL → 本地快照         │  splitters/（四层分块）
        ▼                                      ▼
   统一数据结构 ForumDocument ────────────────┘
        │
        │  ingestion/forum_ingest.py
        │  ① 清洗 & 分块（标题成块 / 段落 / 句末切分 + 重叠）
        │  ② 图片理解：多模态 LLM 结合上下文生成可检索的中文描述
        │  ③ 统一向量化：文本与图片都走 multimodal-embedding-v1（1024 维，L2 归一化）
        │  ④ 按 chunk_id 先删后插（幂等，支持增量重新同步）
        ▼
   Milvus Lite · t_knowledge_collection
   （text + sparse(BM25) + dense(1024) + 来源元信息）
```

**为什么图文能互相检索**：文本和图片都送进 `multimodal-embedding-v1`，
落在同一个向量空间里，所以"用一段文字搜出一张图"成立，
`KnowledgeRetriever.search(image=...)` 也就能实现以图搜库。

**幂等**：每条知识的主键是 `chunk_id`（如 `article:43#2`、`article:43#img0`），
写入前先按主键删除，所以重复同步不会产生重复数据，
论坛文章更新后重新同步即可覆盖。

### 4.2 检索阶段

`milvus_db/forum_retriever.py` 的 `KnowledgeRetriever`：

- **文本查询** → BM25 稀疏 + 稠密向量混合检索，`WeightedRanker` 融合重排；
- **图片查询** → 纯稠密检索（图片无法参与 BM25）；
- **相关性探针** `relevance_probe()` → 向量已归一化，IP 距离即余弦相似度，
  给出"库里到底有没有相关内容"的量化信号；
- **命中结构** → 自带 `sourceType / title / sourceUrl / author / labels / imagePath`，
  可以直接生成站内可点开的引用。

### 4.3 长期记忆

`t_context_collection` 存历次回答，按 `user` 过滤后可跨会话召回高度相似的历史回答，
作为补充材料交给合成智能体（不参与"论坛有没有"的判定，也不产生引用）。

> 顺带修掉了原项目的一个隐患：写入用的是 `text-embedding-v4`、检索用的是
> `multimodal-embedding-v1`，两个向量空间不可比，稠密那一路其实一直是失效的。
> 现在写入与检索统一走多模态嵌入。

---

## 5. 目录结构

```
MultimodalRAG/
├── config.yml                    ★ 唯一配置源（API Key / 端口 / 检索参数 / 开关）
├── config_example.yml            脱敏配置模板（api_key 全为空，复制改名为 config.yml 再用）
├── requirements.txt
├── README.md                     本文档
├── my_llm.py                     全局大模型实例（对话 / 多模态 / 嵌入 / 智谱客户端）
├── start_bot.ps1                 ★ 启动 AI 服务（FastAPI）
├── start_kb_sync.ps1             ★ 同步论坛内容到知识库
├── start_chat.ps1                启动 Gradio 调试界面
├── start_knowledge.ps1           启动 PDF 知识库构建界面（实为拉起 main.py）
├── main.py                       ★ 文档知识库构建入口（Gradio，受 ocr.enabled 控制）
├── save_existing.py              把已有的 MD 目录直接入库
├── check_milvus.py               查看知识库数据（需先停 AI 服务，Milvus Lite 独占锁）
├── clear_milvus.py               清空向量库
├── evaluate_full.py              离线 RAG 评估
│
├── agent/                        ★ 多智能体核心
│   ├── graph.py                    多智能体图装配（Supervisor 模式 + prepare 清场）
│   ├── routing.py                  条件边：路由 + 联网/重写预算判定（不调 LLM）
│   ├── nodes/                      ★ 图上的 8 个节点，一节点一个文件
│   │   ├── prepare.py                每轮开头清空单轮状态
│   │   ├── supervisor.py             调度智能体：LLM 规划（产出执行计划）
│   │   ├── vision.py                 多模态理解智能体：图片 → 可检索信息
│   │   ├── forum.py                  论坛检索智能体：多模态 RAG + 相关性判定
│   │   ├── web.py                    联网搜索智能体：可开关的外部信息通道
│   │   ├── compose.py                答案合成智能体：流式产出带引用的回答
│   │   ├── evaluate.py               质量评估智能体：规则 + 模型双层把关
│   │   └── rewrite.py                补救准备：补联网 / 重写，把步骤置回待执行
│   ├── session.py                  运行时：会话管理 + 事件流（SSE）
│   ├── state.py                    共享状态（智能体之间的通信总线）
│   ├── events.py                   事件协议 + SSE 编码
│   ├── prompts.py                  全部提示词（人设与各智能体角色）
│   ├── llm_utils.py                稳健的 JSON 解析 / 流式 / 多模态调用
│   └── cli.py                      命令行问答（调试用）
│
├── server/                       ★ FastAPI 服务层
│   ├── app.py                      HTTP 接口 + SSE 流式
│   └── schemas.py                  请求/响应模型
│
├── ingestion/                    ★ 论坛知识接入
│   ├── forum_source.py             数据源：REST 网关 / MySQL / 本地快照
│   ├── forum_ingest.py             分块 + 图片理解 + 批量向量化 + 幂等写入
│   ├── attachment_ingest.py        ★ 页面上传的文档附件：PDF/txt/md/json/csv/docx/图片
│   └── cli.py                      python -m ingestion.cli sync|status|sync-pdf
│
├── utils/                        配置、嵌入、日志、图片理解、★ OCR 开关
│   ├── config.py                   唯一配置源读取（不读环境变量 / .env）
│   ├── embeddings_utils.py         DashScope 多模态嵌入 + 限流 / 429 重试
│   ├── image_utils.py              图片理解（不依赖向量库，可单独复用）
│   ├── ocr_utils.py                ★ OCR 总开关 + 两条解析引擎（PyMuPDF / DotsOCR）
│   ├── common_utils.py             MD 文件排序 / 目录清理等通用工具
│   └── log_utils.py                日志
│
├── milvus_db/
│   ├── collections_operator.py     集合定义（统一知识库 / 长期记忆 / 旧版 PDF 库）
│   └── forum_retriever.py          多模态混合检索器 + 长期记忆检索器
│
├── tools/
│   ├── dev_gateway.py              本地联调网关桩（模拟 bbs-rest）
│   └── download_model.py           下载 DotsOCR 权重到 weights/DotsOCR
│
├── dots_ocr/                     PDF/图片解析（DotsOCR，沿用原项目；受 ocr.enabled 控制）
├── splitters/splitter_md.py      Markdown 四层分块器（沿用原项目）
├── evaluate/                     RAGAS 评估器封装
├── graph/                        共享 LangGraph 组件（长期记忆写入、调试打印、流程图）
├── gradio/                       （预留目录，当前为空）
├── weights/DotsOCR               本地 OCR 权重（当前为空；用 tools/download_model.py 拉取）
├── output/                       解析产物（attachments/ 上传原件、images/、ocr_pages/ OCR 中间产物）
├── logs/                         运行日志（app.log）
├── forum_snapshot/               离线数据源目录（**按需自建**，目录不存在时该数据源自动跳过）
├── milvus_local.db               Milvus Lite 数据文件
└── 其它（old）/                   改造前的旧文档与架构图（小罗Bot-架构与设计.md、面试项目文档.md、
                                   graph_rag.png、存储流程图.png 等，当前流程已不引用）
```

### 相比改造前的删减

原先的**单智能体流水线**（`graph/graph_builder.py`、`graph/all_router.py`、
`graph/search_node.py`、`graph/my_state.py`、`graph/tools.py`、`graph/evaluate_node.py`）
以及它专用的写入/检索器（`milvus_db/db_operator.py`、`milvus_db/db_retriever.py`）
已被 `agent/` + `ingestion/` + `milvus_db/forum_retriever.py` 取代并删除，
避免同一份能力存在两套实现。

`main.py`（PDF 知识库构建）、`save_existing.py`、`check_milvus.py`、`clear_milvus.py`、
`evaluate_full.py` 都做了对接到统一知识库的改造；`dots_ocr/`、`splitters/`、`utils/`、
`evaluate/` 基本沿用。

---

## 6. 常用命令

| 目的 | 命令 |
|------|------|
| 启动 AI 服务 | `.\start_bot.ps1` |
| 同步论坛内容到知识库 | `.\start_kb_sync.ps1` |
| 查看数据源与知识库状态 | `.\start_kb_sync.ps1 -Status` |
| **加文档到知识库** | **在页面「知识库」面板里直接拖拽上传（管理员）** |
| 批量导入 PDF 文档（命令行，仍可用） | `.\start_knowledge.ps1` → 上传 → 存入知识库 |
| 下载 DotsOCR 权重（启用 OCR 前） | `python tools\download_model.py`（加 `-t modelscope` 走 ModelScope） |
| 已有 MD 直接入库 | `python save_existing.py <output子目录名>` |
| 命令行问答 | `python -m agent.cli "论坛里有哪些标签？" --web` |
| 交互式多轮问答 | `python -m agent.cli -i` |
| 查看知识库数据 | `python check_milvus.py` |
| 清理数据库 | `python clear_milvus.py` |
| 离线 RAG 评估 | `python evaluate_full.py` |
| Gradio 调试界面 | `.\start_chat.ps1` |
| 本地联调网关桩 | `python tools\dev_gateway.py` |

---

## 7. 常见问题

**Q：页面能打开，但一问就报"小罗Bot 服务暂不可用"？**
A：AI 服务没起来。先跑 `.\start_bot.ps1`，确认 <http://127.0.0.1:7861/health> 返回 `status: ok`。

**Q：回答总是"论坛里没有相关内容"？**
A：知识库是空的。跑一次 `.\start_kb_sync.ps1`，再用页面的「知识库」按钮确认条目数不为 0。

**Q：同步时提示"没有可用的论坛数据源"？**
A：三种数据源都不可用。要么把 springboot 的 bbs-rest 起来，要么确认
`config.yml → forum.mysql` 的账号密码能连上，要么往 `forum_snapshot/` 放几个 md/json。

**Q：联网开关打开了还是没联网？**
A：联网是**兜底**通道，只有论坛检索判定为"不足"时才会真正触发
（这是需求里"论坛内得不到相关内容才获取网络内容"的设计）。另外确认 `llm.zhipu.api_key` 有效。

**Q：一次问答要十几秒？**
A：一次完整问答包含规划 + 检索 + 判定 + 生成 + 评估，约 10~20 秒属正常。
网络较慢或触发联网时会更久。想更快可以关掉质量评估：
`config.yml → agent.enable_evaluator: false`。

**Q：同一会话追问时，回答像是复读了上一轮？**
A：这是状态跨轮残留导致的（已修）。修复方式是图入口的 `prepare` 节点每轮把
`plan` / `agent_status` / `citations` 等**单轮字段**清零，同时保留 `messages` 里的多轮历史。
如果你改了状态字段，记得一并加进 `prepare_node` 的返回里。

**Q：多轮对话里，新一轮的回答夹带了上一轮的内容？**
A：合成智能体如果拿到自己前几轮的长回答，容易把它们当成"没写完的内容"续写进来
（实测出现过问 Flink 的回答里混进论坛标签清单）。所以交给它历史时**只保留用户问过的话**
（`agent/llm_utils.history_for_composer`），既能接住"这些标签里哪个最多"这类指代，
又不会把旧答案带进新答案；真正要复用旧答案时走的是长期记忆检索那条路。

**Q：回答里偶尔冒出一个坏掉的图片？**
A：模型在材料里没有图时也会凭"图片"这个词自己编一个 `![图片](image)` 或 `<img src="...">`。
合成智能体在收尾时会用 `sanitize_answer_images()` 把不在白名单（论坛命中图片 + 用户上传图片）
里的图片引用删掉，宁可不显示图也不显示坏图。同理，多模态历史消息不能直接喂给纯文本模型
（会把图片块降级成占位文本混进正文），`sanitize_history()` 负责替换成一句说明。

**Q：跑了 `check_milvus.py` 报 `Open local milvus failed`？**
A：Milvus Lite 是**嵌入式单进程**数据库，同一时刻只能被一个进程打开。
AI 服务正在运行时它已经持有锁，先停掉 AI 服务再看；
反过来，调试脚本跑着的时候 AI 服务也起不来。

**Q：知识库明明同步过，页面却显示 0 条 / 小罗Bot 什么都检索不到？**
A：先看知识库面板顶部有没有一条黄色告警——有的话是**统计读取失败**，
不是"知识库空了"（`/kb/status` 的 `ok` 字段会区分这两种情况）。
真丢了的话，八成是 **Milvus Lite 的 WAL 被写坏**了：
写入先进 WAL 再合并成 parquet，进程被**强杀**（任务管理器结束进程、`kill -9`）
会损坏正在写的那段 WAL，下次打开时 Milvus 丢弃它，
极端情况下整个集合查询为 0 条 —— 而 `milvus_local.db/.../data/*.parquet` 里的数据其实还在。

处理办法：

1. **先备份**：把 `milvus_local.db` 整个目录复制一份；
2. **重新同步**：`.\start_kb_sync.ps1` —— 论坛内容本来就以 MySQL 为准，重建即可；
3. 页面上传的附件需要重新上传（它们的主键是内容摘要，重传同一个文件就是覆盖）。

**预防**（已经做了两道）：

- 每次写入后立即 `flush()`，把"可能丢失的窗口"压到最小；
- 服务收到 Ctrl+C 时会先把向量库落盘再退出。
  **所以停服务请用一次 Ctrl+C，不要直接强杀进程。**

**Q：改了 `agent/` 里的状态字段后报 `Invalid update`？**
A：LangGraph 要求节点返回的键必须在 `BotState` 里声明。加字段时同步改
`agent/state.py`，需要累加的列表/字典要用带 `None` 重置语义的 reducer。

**Q：`npm run serve` 后直接打开 `/bot` 显示 404？**
A：多半是用了不带 `Accept: text/html` 的工具去请求。浏览器的请求头是正常的，
vue-cli 自带的 history fallback 会把 `/bot` 回退到 `index.html`；
生产环境记得在 nginx 配 `try_files $uri $uri/ /index.html`。

**Q：游客打开「知识库」看不到「向量集合」，也没有「同步论坛内容」「上传文档附件」，是坏了吗？**
A：不是，是有意为之。这三样只对管理员开放（判定见「3.1 知识库面板的角色可见性」）。
游客仍然能看到「知识条目 / 按来源 / 论坛数据源」这些统计，页面统计也照常工作。
想在自己机器上联调管理员视图：用联调桩时在浏览器控制台执行
`document.cookie='devRole=admin;path=/'` 再刷新即可。

**Q：我上传了 PDF，但提示"抽不到文字"？**
A：那份 PDF 没有文字层（扫描件/纯图片型），而 `config.yml → ocr.enabled` 是 `false`，
纯 PyMuPDF 自然读不到内容。三个办法：
① **启用 OCR**：配好 DotsOCR 权重（或起好 vLLM）后把 `ocr.enabled` 改成 `true`，
扫描页会被渲染成图交给 DotsOCR 识别，详见「3.1.3」；
② **绕开 OCR**：把扫描页导出成图片（png/jpg）再上传——图片走多模态描述入库；
③ 换成可复制文字的 PDF。
解析器**不会假装成功**，这种情况会明确告诉你原因。

**Q：`start_knowledge.ps1` 里点"解析文件"失败？**
A：Gradio 那条链路完全看 `ocr.enabled`：
`false` 时用的是纯 PyMuPDF，**扫描件会被拒绝**（提示会写明原因），图片文件也会被拒绝
（PyMuPDF 读不了独立图片，请改用页面「知识库」面板上传）；
`true` 时用的是 DotsOCR，权重没放好或 vLLM 没起就会失败，界面上会直接显示原始错误，
同时提示你检查 `ocr.hf_model_path` 或 `ocr.ip:ocr.port`。
界面顶部会显示当前实际生效的引擎，不用猜。

**Q：开了 OCR 之后，文字型 PDF 的解析结果会变吗？**
A：不会。解析是**逐页判断**的：能抽到文字层的页一律走 PyMuPDF（原文照搬），
只有抽不到文字的页才走 DotsOCR（见「3.1.3」）。
反过来，如果你发现某页明显该走 OCR 却没走，多半是那一页有少量文字（页眉/水印）达到了
`attachment.pdf_min_chars_per_page`（默认 20 字）的门槛，可以把该值调大一点。

**Q：页面上传文档报"只有管理员可以上传文档到知识库"？**
A：附件入库是往**大家共用的**向量库写内容，所以默认只对管理员开放
（`config.yml → attachment.admin_only`）。想放开成"登录用户都能传"就把它改成
`false`，但同时要放开前端与网关两处判断，改动点见「3.1.1」与「6.2」（架构文档）。

**Q：上传后小罗Bot 还是答不上来？**
A：先看知识库面板里「上传文档」的数量有没有 +1。如果上传成功但检索不到，
多半是问题与文档用词差异较大（向量检索基于语义相似度），
试试直接用文档里出现过的关键词提问。

**Q：改了知识库面板的权限后，联调通过但上线被拒（或反过来）？**
A：权限规则有三处实现，必须同时改：
① `AiBotController` 的 `requireAdmin()` / `kbStatus()` 脱敏；
② `tools/dev_gateway.py` 的 `ADMIN_ONLY_PATHS` / `SANITIZE_FOR_GUEST`；
③ 前端 `BotChat.vue` 的 `isAdmin` 与两处 `v-if`。
建议改完对照检查一遍（这三处的对应关系在 3.1.1 节有列表）。

---

## 8. 接口与配置速查

| 配置段 | 关键项 | 说明 |
|--------|--------|------|
| `app` | `bot_name`, `welcome` | 展示名与欢迎语 |
| `llm.openai` | 对话模型 | 规划 / 判定 / 合成 / 评估 |
| `llm.multimodal` | 多模态模型 + DashScope Key | 图片理解、多模态嵌入（共用 Key） |
| `llm.embedding` | 文本嵌入 | RAGAS 评估用 |
| `llm.zhipu` | 联网搜索 Key | 联网搜索智能体 |
| `forum` | `base_url` / `endpoints` / `mysql` / `chunk_size` | 论坛数据接入 |
| `attachment` | `admin_only` / `max_size_mb` / `allowed_extensions` / `pdf_max_pages` / `csv_max_rows` | 文档附件上传入库 |
| `ocr` | `enabled`（★ 总开关，配好 OCR 才改 `true`）/ `use_hf` / `hf_model_path` / `ip` / `port` / `dpi` / `num_thread` | 扫描件 OCR（DotsOCR）；关闭时纯 PyMuPDF |
| `web_search` | `enabled_by_default` / `max_results` | 联网搜索行为 |
| `agent` | `max_handoffs` / `forum_relevance_threshold` / `answer_score_threshold` / `enable_evaluator` / `memory_*` | 多智能体调度 |
| `milvus` | `knowledge_collection` / `context_collection` / `dim` | 向量库 |
| `retrieval` | `agent_top_k` / `sparse_weight` / `dense_weight` | 混合检索 |
| `server` | `host` / `port` / `cors_origins` | AI 服务 |

---

## License

MIT
