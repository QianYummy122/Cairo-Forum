# 开罗论坛（Cairo Forum）· 项目文档

> 版本：1.0　|　文档性质：全栈项目说明（架构 / 接口 / 数据库 / 部署 / 维护）
> 项目根目录：`C:\Users\DELL\Desktop\Cairo Forum`

---

## 目录

- [一、项目概览](#一项目概览)
- [二、技术栈与版本清单](#二技术栈与版本清单)
- [三、系统架构与部署拓扑](#三系统架构与部署拓扑)
- [四、后端工程结构（springboot）](#四后端工程结构springboot)
- [五、核心运行机制](#五核心运行机制)
- [六、REST 接口全清单](#六rest-接口全清单)
- [七、前端工程结构（vue-ui）](#七前端工程结构vue-ui)
- [八、数据库设计](#八数据库设计)
- [九、小罗Bot AI 服务（MultimodalRAG）](#九小罗bot-ai-服务multimodalrag)
- [十、部署与启动](#十部署与启动)
- [十一、配置项速查](#十一配置项速查)
- [十二、安全与已知问题](#十二安全与已知问题)
- [十三、开发与维护指南](#十三开发与维护指南)
- [附录](#附录)

---

## 一、项目概览

### 1.1 这是什么

**开罗论坛（Cairo Forum）** 是一个功能完整的现代化技术社区论坛系统，包含**文章发布与审核、评论（多级回复）、点赞、关注、用户等级成长体系、标签管理、资源导航、轮播图、消息通知、站内动态**等完整社交能力，并在其上集成了一个**多智能体 + 多模态 RAG 的 AI 搜索引擎助手「小罗Bot」**。

项目采用 **前后端分离 + Dubbo RPC 微服务** 架构：

- **后端**：Spring Boot 3.5 + Apache Dubbo 3.3 + ZooKeeper，Maven 多模块，拆分为 4 个可独立部署进程；
- **前端**：Vue 2.6 + Ant Design Vue 1.7 单页应用，支持主题色动态切换与中英双语；
- **AI 服务**：Python FastAPI + LangGraph 多智能体 + Milvus Lite 多模态向量库；
- **存储**：MySQL（业务主库 + 鉴权库）、Redis（登录态/验证码/缓存）、本地磁盘（图片/附件）。

### 1.2 三个子项目

| 目录 | 类型 | 说明 |
|------|------|------|
| `springboot/` | Java 后端 | Maven 多模块，4 个可部署进程（REST 网关 + 3 个微服务） |
| `vue-ui/` | Web 前端 | Vue 2 单页应用，73 个 Vue 组件，11 个 API 服务模块 |
| `MultimodalRAG/` | Python AI 服务 | 「小罗Bot」，多智能体 + 多模态 RAG，经网关反向代理接入 |

### 1.3 谁在什么端口上

| 组件 | 技术 | 监听地址 | 对外 |
|------|------|---------|------|
| `vue-ui` 前端 | Vue CLI devServer | `:8082` | ✅ 浏览器入口 |
| `bbs-rest` REST 网关 | Spring Boot | `:7010`（context-path `/api`） | ✅ 论坛唯一后端入口 |
| `bbs-article-service` | Spring Boot + Dubbo | `:7011` / Dubbo `:22002` | ❌ 内部 |
| `bbs-user-service` | Spring Boot + Dubbo | `:7013` / Dubbo `:22003` | ❌ 内部 |
| `bbs-auth` 鉴权服务 | Spring Boot + Dubbo | `:7014` / Dubbo `:22004` | ⚠️ 兼作 `/static/**` 文件服务 |
| 小罗Bot AI 服务 | FastAPI (uvicorn) | `:7861`（仅 `127.0.0.1`） | ❌ 仅内网 |
| ZooKeeper | — | `:2181` | ❌ 内部 |
| MySQL | 8.0 | `:3306` | ❌ 内部 |
| Redis | — | `:6379` | ❌ 内部 |

### 1.4 一次请求的完整链路

```
浏览器 (http://localhost:8082)
   │  ① 前端 axios /api/bbs/article/getList
   ▼
vue.config.js devServer 代理  /api  →  http://localhost:7010
   │
   ▼
bbs-rest  (:7010, context-path=/api)  ← REST 网关，唯一对外入口
   │  ② 6 个拦截器依次执行（监控→登录→权限→头像→访问记录→通知）
   │  ③ Controller 通过 @DubboReference 发起 RPC
   ▼
ZooKeeper (:2181) 服务发现
   │
   ├──▶ bbs-article-service (:22002)  ──▶ MySQL open_bbs (fs_*)
   ├──▶ bbs-user-service    (:22003)  ──▶ MySQL open_bbs (fs_*)
   └──▶ bbs-auth            (:22004)  ──▶ MySQL ns_auth (ns_*) + Redis + 本地磁盘
   │  ④ 统一响应信封 {code, desc, data}
   ▼
浏览器渲染
```

AI 问答是这条链路上的一个**旁路分支**：

```
浏览器 ──/api/bbs/ai/chat/stream──▶ bbs-rest ──HTTP 反向代理──▶ 小罗Bot (:7861)
                                       (SSE 透传)                  (多智能体 + Milvus)
```

---

## 二、技术栈与版本清单

### 2.1 后端依赖（父 POM `springboot/pom.xml` 统一管理）

| 类别 | 组件 | 版本 |
|------|------|------|
| 基础框架 | Spring Boot（parent） | **3.5.11** |
| JDK | Java | **17**（`maven-compiler-plugin` 强制 `release=17`） |
| RPC | Apache Dubbo (`dubbo-spring-boot-starter`) | **3.3.2** |
| 注册中心 | `dubbo-dependencies-zookeeper-curator5` | 3.3.2 |
| ORM | MyBatis | 3.5.19 |
| ORM | `mybatis-spring-boot-starter` | 3.0.4 |
| ORM | MyBatis Generator（逆向工程） | 1.4.2 |
| 分页 | PageHelper (`pagehelper-spring-boot-starter`) | 2.1.0 |
| 数据库 | MySQL (`mysql-connector-j`) | 9.6.0 |
| 连接池 | Druid (`druid-spring-boot-starter`) | 1.2.24 |
| 缓存 | `spring-boot-starter-data-redis` | 3.5.11 |
| 缓存 | Redisson | 3.42.0 |
| 缓存 | `commons-pool2` | 2.11.1 |
| 对象映射 | MapStruct | 1.6.3 |
| 简化代码 | Lombok | 1.18.36 |
| JSON | fastjson | 1.2.71 |
| 工具库 | commons-lang3 | 3.17.0 |
| 工具库 | Guava | 27.1-jre |
| 工具库 | commons-collections4 | 4.4 |
| 工具库 | Hutool | 5.6.3 |
| 工具库 | `transmittable-thread-local` | 2.14.5 |
| 图片处理 | Thumbnailator | 0.4.14 |
| 鉴权 | `java-jwt` (auth0) | 3.15.0 |
| 鉴权 | shiro-spring | 3.0.0-alpha-1 |
| API 文档 | Knife4j (`knife4j-openapi3-jakarta-spring-boot-starter`) | 4.5.0 |
| API 文档 | `springdoc-openapi-starter-webmvc-ui` | 2.8.0（强制覆盖 Knife4j 内置旧版） |
| HTTP 客户端 | Apache HttpClient5 | 5.4.2 |
| 云存储 | 七牛云 `qiniu-java-sdk` | 7.6.0（已本地化，实际未启用） |
| 邮件 | `spring-boot-starter-mail` | 3.5.11 |
| 短信 | 阿里云 `aliyun-java-sdk-core` / `dysmsapi` | 4.5.20 / 2.1.0 |
| 第三方公共库 | `io.github.maliangnansheng:nansheng-common` | 3.5.11-open-1.1.0 |
| 构建 | `flatten-maven-plugin` | 1.1.0（支持 `${revision}` 占位符） |
| 构建 | `maven-assembly-plugin` | 3.3.0 |
| 构建 | `maven-surefire-plugin` | 3.2.5（配置 `skipTests=true`） |

> **`${revision}` 机制**：父 POM 用 `<version>${revision}</version>`，`revision = 3.0.0-SNAPSHOT`。
> 子模块继承 `${revision}` 必须依赖 `flatten-maven-plugin`（绑定在 `process-resources` 阶段），
> 插件会在构建时生成 `.flattened-pom.xml` 把占位符解析成真实版本号。
> 项目根目录的 `springboot/.flattened-pom.xml` 就是这个插件的产物。

### 2.2 前端依赖（`vue-ui/package.json`）

| 类别 | 组件 | 版本 |
|------|------|------|
| 框架 | Vue | ^2.6.11 |
| UI 组件库 | ant-design-vue | ^1.7.0 |
| 路由 | vue-router | ^3.2.0 |
| 状态管理 | vuex | ^3.4.0 |
| HTTP | axios | **^0.21.0**（注意：旧版本，SSE 需绕开它） |
| 国际化 | vue-i18n | ^8.22.1 |
| 富文本编辑器 | wangeditor | ^4.7.4 |
| Markdown 编辑器 | mavon-editor | ^2.10.4 |
| Markdown 渲染 | marked | 4.3.0 |
| 图表 | echarts | ^5.1.2 |
| 时间处理 | moment | ^2.29.1 |
| 查询串 | qs | ^6.10.3 |
| 剪贴板 | vue-clipboard2 | ^0.3.3 |
| **CSS 预处理器** | less | **2.7.2**（旧版，`calc()` 陷阱见 12.3） |
| 主题切换 | webpack-theme-color-replacer | 1.3.22 |
| 构建 | @vue/cli-service | ~4.5.0 |
| 压缩 | compression-webpack-plugin | 5.0.0（gzip） |
| 压缩 | uglifyjs-webpack-plugin | ^2.2.0 |
| Node 版本 | `.node-version` | **16.20.2** |

> `package.json` 的 scripts 都带 `NODE_OPTIONS=--openssl-legacy-provider`，
> 这是 Node 17+ 与 webpack 4 的 MD4 哈希不兼容问题的标准解法——说明该项目虽然锁定 Node 16，
> 但做了向前兼容处理。

### 2.3 AI 服务依赖（`MultimodalRAG/requirements.txt`）

`langchain`、`langchain-openai`、`langchain-experimental`、`langchain-text-splitters`、
`pymilvus==2.6.0`（Milvus Lite）、`dashscope`、`gradio`、`loguru`、`pillow`、
`PyMuPDF`、`sentence_transformers`、`ragas`。
另有 `python-docx`（`.docx` 解析，可选）。

### 2.4 运行环境

| 项 | 值 |
|----|-----|
| Java | 17（`springboot/.vfox.toml` 指定 `java = "17.0.19-amzn"`） |
| Node.js | 16.20.2（`vue-ui/.node-version`） |
| MySQL | 8.0.29（据 `open_bbs.sql` 头部，字符集 `utf8mb4`，排序规则 `utf8mb4_general_ci`，引擎 InnoDB） |
| Python | 3.10+ |

---

## 三、系统架构与部署拓扑

### 3.1 微服务如何划分

项目用 **Apache Dubbo + ZooKeeper** 做 RPC 与服务发现，用 **Maven 多模块**组织代码，
整体拆分为 **4 个可独立部署的进程 + 若干共享依赖模块**：

```
ns-bbs (父 POM：com.liang:ns-bbs，仅做版本/依赖/插件统一管理)
│
├── bbs-rest                        # ① REST 网关层（对外入口，Dubbo 纯消费者）
├── bbs-common                      # ② 公共模块（枚举/常量/工具类/公共 facade）
│
├── bbs-user                        # ③ 用户域微服务（父 POM）
│   ├── bbs-user-facade             #     接口契约 + DTO（Dubbo 接口层）
│   ├── bbs-user-persistence        #     数据访问层（entity + mapper）
│   └── bbs-user-service            #     服务实现（Dubbo 提供者，可执行应用）
│
├── bbs-article                     # ④ 文章域微服务（父 POM，同 user 三层结构）
│   ├── bbs-article-facade
│   ├── bbs-article-persistence
│   └── bbs-article-service
│
└── bbs-auth                        # ⑤ 鉴权微服务（自托管，替代作者外部 ns-manage 服务）
```

### 3.2 四个可部署进程

| 服务 | `spring.application.name` | HTTP | Dubbo | 依赖数据库 | 角色 |
|------|--------------------------|------|-------|-----------|------|
| `bbs-rest` | `ns-bbs-rest` | 7010 | 22001 | 无（纯消费者） | REST 网关 / Dubbo 消费者 |
| `bbs-article-service` | `ns-bbs-article` | 7011 | 22002 | MySQL `open_bbs` | 文章域：提供者 + 消费者 |
| `bbs-user-service` | `ns-bbs-user` | 7013 | 22003 | MySQL `open_bbs` | 用户域：提供者 + 消费者 |
| `bbs-auth` | `ns-bbs-auth` | 7014 | 22004 | MySQL `ns_auth` | 鉴权：提供者 |

### 3.3 三层模块拆分的职责边界

每个业务域（user / article）都按**三层**拆分，职责边界清晰：

| 层 | 模块 | 内容 | 谁依赖它 |
|----|------|------|---------|
| **接口层（契约）** | `*-facade` | `facade.server.*` 接口 + `facade.dto.*` DTO | 消费者与提供者**都**依赖 |
| **数据层** | `*-persistence` | MyBatis `entity`（Po / PoExample）+ `mapper` + `mybatis/mappers/*.xml` | **只有** `*-service` 依赖 |
| **实现层（可执行）** | `*-service` | `impl` 实现 + `mapstruct` 转换 + `config` + 启动类 + `application.yml` | 可独立打包运行 |

> 关键点：**facade 是契约、persistence 是私有实现、service 是运行单元**。

### 3.4 Dubbo 关键配置

四个模块的 `application.yml` 都使用**完全相同**的 Dubbo 关键配置：

```yaml
dubbo:
  application:
    serialize-check-status: DISABLE   # 关闭序列化安全检查
    register-mode: interface          # 强制接口级注册，禁用应用级服务发现
    parameters:
      migration.step: FORCE_INTERFACE # 强制接口级，跳过服务发现
  registry:
    address: zookeeper://127.0.0.1:2181   # ★ 四个模块必须一致
  consumer:
    check: false                      # Provider 未就绪也能启动
  provider:
    filter: -exception                # 使自定义异常可被抛出（否则永远是 RuntimeException）
```

- **服务提供者**：启动类加 `@EnableDubbo`，`@DubboComponentScan(basePackages="...service.impl")` 扫描实现类，实现类标注 `org.apache.dubbo.config.annotation.Service`。
- **服务消费者**：注入远程接口用 `@DubboReference`。
- **接口级注册的必要性**：Dubbo 3 默认应用级服务发现，而本项目强制 `interface` 模式 + `FORCE_INTERFACE`，
  确保消费方与提供方按「接口全限定名 + 版本」精确匹配。

### 3.5 服务间调用拓扑（含双向 RPC）

```
                 ┌────────────────────────────┐
   外部请求 ───▶ │  bbs-rest (REST 网关 :7010) │
                 │  @DubboReference 调用各服务  │
                 └───┬──────────┬──────────┬───┘
                     │          │          │
             ┌───────▼──┐  ┌────▼──────┐  ┌▼─────────┐
             │ article  │◀▶│  user     │  │  auth    │
             │ -service │  │ -service  │  │(鉴权/SSO)│
             └──────────┘  └───────────┘  └──────────┘
                 ▲                ▲
                 └──── 双向 RPC ────┘
```

- `bbs-rest` 是**唯一对外入口**，通过 `@DubboReference` 调用 user / article / auth 的 facade 接口。
- `article-service` 与 `user-service` 存在**双向 RPC**：
  - article 调 user 的 `LikeService` / `FollowService` / `LikeCommentService`；
  - user 调 article 的 `ArticleService`（见 `FollowServiceImpl`）。
- `user-service` 还调用 auth 的 `com.liang.manage.auth.facade.server.UserService`。

> ⚠️ **双向 RPC 的运维含义**：两套服务必须同时在线并连到同一个 ZooKeeper，否则互相调用失败。
> 在 `consumer.check: false` 下表现为**运行时异常**而非启动失败。

### 3.6 基础设施清单

| 组件 | 默认地址 | 用途 | 使用方 |
|------|---------|------|--------|
| ZooKeeper | `127.0.0.1:2181` | Dubbo 注册中心 | 全部 4 个模块 |
| MySQL | `127.0.0.1:3306` | `open_bbs`（业务库）、`ns_auth`（鉴权库） | user/article 用前者，auth 用后者 |
| Redis | `127.0.0.1:6379`（无密码） | SSO token、验证码、权限缓存、点赞/关注缓存 | rest / user / auth |
| MongoDB | `127.0.0.1:27017/open_bbs`（`bbs-article-service` 遗留配置） | **已无业务使用**，仅残留配置 | article（不生效） |
| 本地磁盘 | `./uploads`（auth 进程工作目录） | 图片与文档附件存储 | auth（`FileService`） |
| 邮件 SMTP | 未配置 | 邮箱验证码 | auth（未配置则仅打日志） |
| 阿里云短信 | 未配置 | 手机验证码 | auth（未配置则仅打日志） |
| DashScope / DeepSeek / 智谱 | 外部 HTTPS | 多模态嵌入 / 对话 / 联网搜索 | 小罗Bot |

> **MongoDB 已不再被业务代码使用**。早期设计用 MongoDB 存文章正文，`配置清单.md` 明确记录「闲聊群组已剔除」，
> 而 `open_bbs.sql` 中 `fs_article.content` 是 `longtext`——**正文实际存在 MySQL 里**。
> 但工程中仍保留 `spring-boot-starter-data-mongodb` 依赖、`MongoConfig` 配置类，
> 以及 **`bbs-article-service` 的一份有效配置**：
>
> ```yaml
> spring.data.mongodb.uri: mongodb://127.0.0.1:27017/open_bbs
> ```
>
> 由于 Spring Boot 只在存在 `MongoClient` 相关 Bean 时才尝试连接（且该 URI 指向本机），
> 未启动 MongoDB 通常不影响启动，但**若出现 MongoDB 连接相关报错，
> 优先怀疑这处遗留配置**（移除依赖与 `MongoConfig` 即可彻底消除）。
> 历史备份 `springboot/db备份/bbs_navicat_mongodb.js`（32 KB）同样是遗留物。

### 3.7 图片与文件的存储策略

依据 `vue-ui/项目说明.txt`（项目原始设计说明）：

| 内容 | 存储位置（当前实现） | 原始设计意图 |
|------|-------------------|-------------|
| 论坛图片（标签 logo、题图、正文插图、轮播图资源图） | **后端服务器本地磁盘** | 「预期换成坚果云」 |
| 论坛文字（文章正文） | **MySQL `fs_article.content`（longtext）** | 原设计为 MongoDB |
| 其余信息 | MySQL | MySQL |

当前 `bbs-auth` 的 `FileServiceImpl` 把文件写到 `auth.file-storage-path`（默认 `./uploads`），
通过 `auth.file-url-prefix`（默认 `http://127.0.0.1:7014/static/`）+ `/static/**` 静态资源映射对外提供，
**已完整本地化，不依赖七牛云**。磁盘上的实际目录结构：

```
springboot/uploads/
├── articleTitleMap/     # 文章题图
└── headPortrait/        # 用户头像
```

### 3.8 为什么 AI 域不建 Dubbo 模块

论坛的惯例是「一个业务域 = facade + persistence + service 三层」，
但 AI 能力**不在 Java 里实现**（模型、向量库、LangGraph 都在 Python 侧），
建一个 Dubbo facade 只会得到一层空壳转发，反而增加跨语言维护成本。

因此把 AI 定位成 **`bbs-rest` 网关背后的外部能力服务**，用 HTTP 反向代理接入 ——
这是现代项目里「BFF / API 网关 + 独立 AI 服务」的常见做法。三种方案的取舍：

| 方案 | 问题 |
|------|------|
| 前端 iframe 嵌 Gradio 界面 | 界面对不上论坛风格，交互与引用无法定制 |
| 前端直连 Python 服务 | ① `vue.config.js` 只代理 `/api`，直连 7861 属跨域，而 bbs-rest 没有全局 CORS；② 绕过统一响应信封 `{code,desc,data}`，前端 axios 拦截器判成功/弹登录的逻辑全部失效；③ 把持有模型 Key 的服务暴露给浏览器 |
| **经 springboot 网关**（采用） | 同源、信封统一、登录态可复用；AI 服务地址/超时/限流收敛在 `application.yml`；Python 侧只做「AI 能力」，职责边界干净 |

---

## 四、后端工程结构（springboot）

### 4.1 模块全景

```
springboot/
├── pom.xml                     父 POM（com.liang:ns-bbs，packaging=pom）
├── .flattened-pom.xml          flatten 插件产物
├── .vfox.toml                  Java 17.0.19-amzn
├── 说明.txt / 配置清单.md / 微服务架构与拆分说明.md   ← 项目自带文档
├── db备份/
│   ├── open_bbs.sql            业务库导出（1339 行，13 张表）
│   └── bbs_navicat_mongodb.js  历史 MongoDB 备份（已不启用）
├── uploads/                    本地上传目录（articleTitleMap / headPortrait）
│
├── bbs-common/                 【公共模块】9 个 Java 文件
│   └── src/main/java/com/liang/bbs/common/
│       ├── config/RestTemplateConfig.java
│       ├── constant/RedisConstants.java
│       ├── enums/{ArticleStateEnum, DynamicTypeEnum, EnumIntegerTransform,
│       │          SortRuleEnum, UserLevelEnum}.java
│       ├── facade/server/UserAdminService.java
│       └── util/Placeholder.java
│
├── bbs-rest/                   【REST 网关】35 个 Java 文件
│   └── src/main/java/com/liang/bbs/rest/
│       ├── RestApplication.java
│       ├── config/{ObjectMapperConfig, RedisConfig, RedissonConfig, WebConfig}.java
│       ├── config/ai/AiAgentProperties.java
│       ├── config/login/NoNeedLogin.java
│       ├── config/swagger/{ApiVersion, ApiVersionConstant, SwaggerConfig}.java
│       ├── controller/         ← 11 个 Controller，见第六章
│       ├── controller/ai/{AiAgentClient.java, dto/AiChatDTO.java}
│       ├── init/ApiDataInit.java
│       ├── interceptor/        ← 6 个拦截器 + 全局异常处理
│       └── utils/{FileLengthUtils, HostUtils, HttpRequestUtils, IpUtil}.java
│
├── bbs-user/                   【用户域】57 个 Java 文件
│   ├── bbs-user-facade/        ← 5 个 Dubbo 接口 + 11 个 DTO
│   ├── bbs-user-persistence/   ← 5 个 entity（+5 个 Example）+ 7 个 Mapper
│   └── bbs-user-service/       ← 5 个 impl + 6 个 MapStruct + 7 个 config + 2 个定时任务
│
├── bbs-article/                【文章域】64 个 Java 文件
│   ├── bbs-article-facade/     ← 6 个 Dubbo 接口 + 15 个 DTO
│   ├── bbs-article-persistence/← 6 个 entity（+6 个 Example）+ 9 个 Mapper
│   └── bbs-article-service/    ← 6 个 impl + 7 个 MapStruct + 6 个 config + 评论树工具
│
└── bbs-auth/                   【鉴权服务】17 个 Java 文件
    ├── db/ns_auth.sql          鉴权库建库脚本（4 张表 + 超管种子数据）
    └── src/main/java/com/liang/bbs/auth/
        ├── AuthApplication.java
        ├── config/{DubboConfig, MybatisConfig, WebConfig}.java
        ├── persistence/mapper/{Notify, NotifyUser, User, Visit}Mapper.java
        ├── service/impl/       ← 8 个实现类
        └── utils/PasswordUtils.java
```

**后端 Java 源文件总计：182 个**（article 64 / user 57 / rest 35 / auth 17 / common 9），
全部位于各模块 `src/` 下（`target/` 为编译产物，不计）。

### 4.2 bbs-common（公共模块）

| 类 | 说明 |
|----|------|
| `config/RestTemplateConfig` | 公共 `RestTemplate` 构造（默认读超时 10 秒） |
| `constant/RedisConstants` | Redis key 前缀常量：`BASE_KEY="ns:"`、`RIGHTS_KEY="rights:"`、`API_KEY="ns:rights:api:"` |
| `enums/ArticleStateEnum` | 文章状态：`pendingReview(-1,"待审核")`、`disabled(0,"禁用")`、`enable(1,"启用")` |
| `enums/DynamicTypeEnum` | 动态类型：`writeArticle`(写文章)、`likeArticle`(点赞文章)、`likeComment`(点赞评论)、`commentArticle`(评论文章)、`commentReply`(评论回复)、`followUser`(关注用户) |
| `enums/UserLevelEnum` | 用户等级与积分区间，见下表 |
| `enums/SortRuleEnum` | 排序规则：`hottest`(最热)、`newest`(最新) |
| `enums/EnumIntegerTransform` | 枚举 ↔ Integer 转换工具 |
| `facade/server/UserAdminService` | 公共 Dubbo 契约：`List<Long> listAdminUserIds()`——查所有管理员 id（`ns_user.is_admin=1`），由 `bbs-auth` 实现，供前端头像「会员」标识使用 |
| `util/Placeholder` | 占位工具类 |

**用户等级体系（`UserLevelEnum`）**：

| 等级 | 积分下限 | 区间说明 |
|------|---------|---------|
| `Lv1` | 0 | `0 <= x < 100` |
| `Lv2` | 100 | `100 <= x < 300` |
| `Lv3` | 300 | `300 <= x < 600` |
| `Lv4` | 600 | `600 <= x < 1000` |
| `Lv5` | 1000 | `1000 <= x < 1500` |
| `Lv6` | 1500 | `1500 <= x < 2100` |

> `get(code)` 按积分区间返回等级；`code >= 1500` 返回 `Lv6`，兜底返回 `Lv1`。
> 前端配套资源为 `vue-ui/src/assets/img/level/Lv1..Lv6.svg` 与 `badge-Lv1..badge-Lv6.svg`。

### 4.3 bbs-rest（REST 网关，35 个 Java 文件）

#### 启动类与配置

| 类 | 说明 |
|----|------|
| `RestApplication` | Spring Boot 启动类 |
| `config/WebConfig` | 注册 6 个拦截器（顺序即执行顺序）+ swagger 静态资源映射 |
| `config/RedisConfig` | `RedisTemplate` 序列化配置 |
| `config/RedissonConfig` | Redisson 客户端（分布式锁） |
| `config/ObjectMapperConfig` | Jackson 配置（日期格式等） |
| `config/ai/AiAgentProperties` | `ai.agent.*` 配置绑定（`@ConfigurationProperties`） |
| `config/login/NoNeedLogin` | 自定义注解：标在方法或类上表示**免登录** |
| `config/swagger/{SwaggerConfig, ApiVersion, ApiVersionConstant}` | Knife4j / OpenAPI 分组与版本 |
| `init/ApiDataInit` | 启动时反射扫描所有 `@Controller` 的 `@Operation` 注解，构建「uri → 权限说明」映射写入 Redis `ns:rights:api:{projectCode}`；**Redis 不可用时只告警不阻断启动** |

#### 拦截器链（`WebConfig.addInterceptors`，全部作用于 `/**`）

| # | 拦截器 | 职责 |
|---|--------|------|
| 1 | `RequestMonitor` | 请求耗时等监控信息（受 `interceptor.monitor.status` 开关控制） |
| 2 | `LoginInterceptor` | SSO 登录校验：读 Cookie → `UserService.verifyToken` / `isExpired` / `getUserSsoDTOByToken` → 写入 `UserContextUtils` 线程变量；`@NoNeedLogin` 放行 |
| 3 | `UrlAccessCheckInterceptor` | 路径级权限：调 `UrlAccessRightService.checkUrlAccess(user, uri, pathVars)`，拒绝时抛 `BusinessException(URL_ACCESS_REFUSED)` |
| 4 | `UserPictureInterceptor` | 把用户头像链接写进响应头 `X-User-Picture` |
| 5 | `VisitInterceptor` | 访问记录（→ `ns_visit`） |
| 6 | `NotifyInterceptor` | 把消息通知数量写进响应头 `X-System-Notify-Count` / `X-Task-Notify-Count` |

**免登录放行路径**（`NOT_LOGIN_URLS`，仅对文档类资源）：
`/swagger-resources/**`、`/webjars/**`、`/v2/**`、`/v3/**`、`/doc.html/**`、
`/swagger-ui.html/**`、`/springdoc/**`、`/favicon.ico/**`、`/error/**`。

> **注意**：业务接口的免登录**不**通过这个列表控制，而是靠 `@NoNeedLogin` 注解
> （注解优先于拦截器，方法级或类级均可）。

#### 全局异常处理

`interceptor/GlobalExceptionHandler`：把 `BusinessException` 等异常统一转换成
`{code, desc, data}` 信封返回，避免前端拿到 500 原始堆栈。

#### 工具类

| 类 | 说明 |
|----|------|
| `utils/FileLengthUtils` | 上传文件大小校验（配合 `file.source.length`，默认 5 MB） |
| `utils/HostUtils` | 主机名/地址获取 |
| `utils/HttpRequestUtils` | Cookie 查找（`findCookie`）、重定向（`redirect`） |
| `utils/IpUtil` | 客户端真实 IP 提取（供 `ns_visit` 使用） |

#### AI 客户端

`controller/ai/AiAgentClient`：**单独构造** `RestTemplate` 用于访问小罗Bot。
之所以不复用论坛公共的那份，是因为公共 `RestTemplate` 读超时只有 10 秒，
而 Agent 一轮问答动辄十几秒——所以这里读超时给到 180 秒（`ai.agent.read-timeout`）。
提供 `call()` / `stream()`（SSE 透传）/ `upload()`（multipart 转发）三类方法。

`controller/ai/dto/AiChatDTO`：`{question, image, sessionId, webSearchEnabled}`。

### 4.4 bbs-user（用户域，57 个 Java 文件）

#### facade —— Dubbo 接口契约（`com.liang.bbs.user.facade.server`）

| 接口 | 方法 |
|------|------|
| `DynamicService` | `Boolean create(DynamicDTO)`、`Boolean verifyExist(DynamicDTO)`、`Boolean delete(LocalDateTime startTime, LocalDateTime endTime)`、`void updateAll()` |
| `FollowService` | `FollowDTO getById(Integer)`、`FollowDTO getByFromToUser(Long fromUser, Long toUser, Boolean isAll)`、`Boolean updateFollowState(Long fromUser, Long toUser)`、`FollowCountDTO getFollowCount(Long userId)` |
| `LikeService` | `LikeDTO getById(Integer)`、`LikeDTO getByArticleIdUserId(Integer articleId, Long userId)`、`Long getLikeCountArticle(List<Integer> articleIds)`、`Boolean isLike(Integer articleId, Long userId)`、`Boolean updateLikeState(Integer articleId, UserSsoDTO currentUser)`、`Long getUserLikeCount(Long userId)`、`Long getUserTheLikeCount(Long userId)` |
| `LikeCommentService` | `Long getLikeCountCommentId(Integer commentId)`、`Boolean isLike(Integer commentId, Long userId)`、`Boolean updateLikeCommentState(Integer commentId, UserSsoDTO currentUser)`、`LikeCommentDTO getByCommentIdUserId(Integer commentId, Long userId)` |
| `UserLevelService` | `Boolean create(Long userId)`、`Boolean update(Long userId, Integer points)`、`Boolean updatePointsAll()`、`Boolean syncAll()`、`UserForumDTO getUserInfo(Long userId, UserSsoDTO currentUser)` |

**DTO（11 个）**：`DynamicDTO`、`FollowCountDTO`、`FollowDTO`、`FollowSearchDTO`、
`LikeCommentDTO`、`LikeDTO`、`LikeSearchDTO`、`UserForumDTO`、`UserLevelDTO`、
`UserOperateCountDTO`、`UserSearchDTO`。

#### persistence —— 数据访问层

| entity | 表 | 说明 |
|--------|-----|------|
| `DynamicPo` | `fs_dynamic` | 用户动态 |
| `FollowPo` | `fs_follow` | 关注关系 |
| `LikePo` | `fs_like` | 文章点赞 |
| `LikeCommentPo` | `fs_comment_like` | 评论点赞 |
| `UserLevelPo` | `fs_user_level` | 用户等级与积分 |

Mapper 接口（7 个）：`DynamicPoMapper`、`FollowPoMapper`、`LikePoMapper`、
`LikePoExMapper`（扩展）、`LikeCommentPoMapper`、`LikeCommentPoExMapper`（扩展）、`UserLevelPoMapper`。
对应 XML 位于 `src/main/resources/mybatis/mappers/*.xml`。

#### service —— 实现层

| 实现类 | 实现接口 |
|--------|---------|
| `DynamicServiceImpl` | `DynamicService` |
| `FollowServiceImpl` | `FollowService`（同时 `@DubboReference` 依赖 article 的 `ArticleService` 与 auth 的 `UserService`） |
| `LikeServiceImpl` | `LikeService` |
| `LikeCommentServiceImpl` | `LikeCommentService` |
| `UserLevelServiceImpl` | `UserLevelService` |

MapStruct 转换器（6 个）：`CommonMS`、`DynamicMS`、`FollowMS`、`LikeMS`、`LikeCommentMS`、`UserLevelMS`。

配置类（7 个）：`CommonConfig`、`DruidConfig`、`DubboConfig`、`MongoConfig`、
`MybatisConfig`、`RedisConfig`、`RedissonConfig`、`TaskThreadPoolConfig`。

**定时任务（`scheduler/`）**：

| 类 | 职责 |
|----|------|
| `UserDynamicWorker` | 周期同步/整理用户动态（配合 `DynamicService.updateAll()`） |
| `UserLevelWorker` | 周期重算用户积分与等级（配合 `UserLevelService.updatePointsAll()` / `syncAll()`） |

### 4.5 bbs-article（文章域，64 个 Java 文件）

#### facade —— Dubbo 接口契约（`com.liang.bbs.article.facade.server`）

| 接口 | 方法 |
|------|------|
| `ArticleService` | `Long getUserArticleCount(Long, ArticleStateEnum)`、`Boolean updateState(ArticleDTO, UserSsoDTO)`、`Boolean create(ArticleDTO, List<Integer> labelIds, UserSsoDTO)`、`Boolean update(...)`、`Boolean create(byte[] bytes, String sourceFileName, ...)`、`Boolean update(byte[], String, ...)`、`String uploadPicture(byte[], String)`、`TotalDTO getArticleCommentVisitTotal()`、`Long getTotal()`、`ArticleCountDTO getCountById(Integer, UserSsoDTO)`、`Boolean updatePv(ArticleDTO)`、`Boolean articleTop(Integer, Boolean, UserSsoDTO)`、`Integer getMaxTop()`、`Boolean delete(Integer, UserSsoDTO)`、`ArticleCheckCountDTO getArticleCheckCount(String title)` |
| `CommentService` | `Long getCommentCountByArticle(Integer articleId)`、`Long getTotal()`、`Boolean create(CommentDTO, UserSsoDTO)`、`Boolean delete(Integer commentId)`、`void getAllChildrenByPreId(List<CommentDTO> result, Integer preId)`、`Integer getArticleIdByCommentId(Integer commentId)`、`CommentDTO getById(Integer commentId)` |
| `LabelService` | `Boolean create(LabelDTO, UserSsoDTO)`、`String uploadLabelLogo(byte[], String)`、`Boolean update(LabelDTO, UserSsoDTO)`、`Boolean delete(Integer)` |
| `ArticleLabelService` | `Boolean create(List<Integer> labelIds, Integer articleId, UserSsoDTO)`、`Boolean update(List<Integer> labelIds, Integer articleId, UserSsoDTO)`、`Long getCountByLabelId(Integer labelId)` |
| `ResourceNavigateService` | `Boolean create(ResourceNavigateDTO, UserSsoDTO)`、`String uploadResourceNavigateLogo(byte[], String)`、`Boolean update(ResourceNavigateDTO, UserSsoDTO)`、`Boolean delete(Integer)` |
| `SlideshowService` | `List<SlideshowDTO> getList()` |

**DTO（15 个）**：`ArticleCheckCountDTO`、`ArticleCountDTO`、`ArticleDTO`、`ArticleLabelDTO`、
`ArticleMarkdownInfo`、`ArticleReadDTO`、`ArticleSearchDTO`、`CommentDTO`、`CommentSearchDTO`、
`LabelDTO`、`LabelSearchDTO`、`ResourceNavigateDTO`、`ResourceNavigateSearchDTO`、
`SlideshowDTO`、`TotalDTO`。

#### persistence —— 数据访问层

| entity | 表 |
|--------|-----|
| `ArticlePo` | `fs_article` |
| `CommentPo` | `fs_comment` |
| `LabelPo` | `fs_label` |
| `ArticleLabelPo` | `fs_article_label` |
| `ResourceNavigatePo` | `fs_resource_navigate` |
| `SlideshowPo` | `fs_slideshow` |

Mapper（9 个）：`ArticlePoMapper`、`ArticlePoExMapper`、`CommentPoMapper`、`CommentPoExMapper`、
`LabelPoMapper`、`ArticleLabelPoMapper`、`ArticleLabelPoExMapper`、`ResourceNavigatePoMapper`、`SlideshowPoMapper`。

#### service —— 实现层

| 实现类 | 实现接口 |
|--------|---------|
| `ArticleServiceImpl` | `ArticleService` |
| `CommentServiceImpl` | `CommentService` |
| `LabelServiceImpl` | `LabelService` |
| `ArticleLableServiceImpl` | `ArticleLabelService` |
| `ResourceNavigateServiceImpl` | `ResourceNavigateService` |
| `SlideshowServiceImpl` | `SlideshowService` |

MapStruct（7 个）：`ArticleMS`、`CommentMS`、`LabelMS`、`ArticleLabelMS`、`ResourceNavigateMS`、`SlideshowMS`、`CommonMS`。

工具类：`utils/CommentTreeUtils` —— 把扁平评论列表按 `pre_id` 组装成**多级评论树**
（配合 `CommentService.getAllChildrenByPreId` 使用）。

配置类（6 个）：`CommonConfig`、`DruidConfig`、`DubboConfig`、`MongoConfig`、`MybatisConfig`、`RedisConfig`。

### 4.6 bbs-auth（自托管鉴权服务，17 个 Java 文件）

**设计背景**：原工程依赖作者的外部 `ns-manage` Dubbo 服务做鉴权。
为「脱离作者服务、独立运营」，新增本模块**本地实现**论坛前端实际依赖的 Dubbo 接口，
让 `bbs-rest` / `bbs-user` / `bbs-article` 的 `@DubboReference` 指向自己的 Provider。
（原工程配置指向作者服务器 ZK `47.109.0.224:2181`、Redis `8.137.106.178:6222`，
若继续连作者 ZK，会与作者仍在运行的 ns-manage Provider 发生**服务发现冲突**。）

#### 提供的 7 个 Dubbo 服务

| 实现类 | 实现的第三方接口（`com.liang.manage.auth.facade.server.*`） | 职责 |
|--------|---------------------------------------------------|------|
| `UserServiceImpl` | `UserService` | 登录/注册/登出/SSO token 校验/用户信息/改密/绑定邮箱手机 |
| `UrlAccessRightServiceImpl` | `UrlAccessRightService` | 管理端路径权限判定 |
| `FileServiceImpl` | `FileService` | 文件上传（本地磁盘，替代七牛云） |
| `NotifyServiceImpl` | `NotifyService` | 通知（未读数/列表/已读） |
| `VisitServiceImpl` | `VisitService` | 访问记录 |
| `MailServiceImpl` | `MailService` | 邮件验证码（可选，未配置仅打日志） |
| `SmsServiceImpl` | `SmsService` | 短信验证码（可选，未配置仅打日志） |
| `UserAdminServiceImpl` | `com.liang.bbs.common.facade.server.UserAdminService` | 查询所有管理员用户 id |

#### 配置与工具

| 类 | 说明 |
|----|------|
| `config/DubboConfig` | `@DubboComponentScan` 扫描 impl 包 |
| `config/MybatisConfig` | MyBatis 配置（`map-underscore-to-camel-case: true`） |
| `config/WebConfig` | `/static/**` 静态资源映射（对外提供上传的图片/附件） |
| `utils/PasswordUtils` | 密码摘要：`SHA256(salt + 明文)`，盐为随机 16 位 hex |

#### 数据访问

Mapper（4 个）：`UserMapper`(→`ns_user`)、`NotifyMapper`(→`ns_notify`)、
`NotifyUserMapper`(→`ns_notify_user`)、`VisitMapper`(→`ns_visit`)。

---

## 五、核心运行机制

### 5.1 统一响应信封

所有接口返回 `ResponseResult<T>`，序列化为：

```json
{ "code": 0, "desc": "成功", "data": { } }
```

| `code` | 含义 | 前端行为 |
|--------|------|---------|
| `0` | 成功 | `resolve(response.data)`，业务代码拿 `res.data` |
| `302` | 未登录 / 需要登录 | 置 `isLogin=false`、弹出登录框，`reject` |
| 其他 | 业务失败 | `throw response.data`，由调用方 `.catch(err => err.desc)` 取提示 |

`302` 分支在 `axios.js` 里对 `/api/bbs/user/getCurrentUserRights` 做了**豁免**
（该接口本身用于探测登录态，未登录是正常结果，不应弹窗）。

### 5.2 登录态（SSO Token）

```
① 前端 POST /api/bbs/sso/login  {name, password}
        ▼
② LoginController 经 Dubbo 调 bbs-auth UserService.login()
        ▼
③ 校验：SHA256(salt + 明文) 与 ns_user.password 比对
        ▼
④ 生成 UUID token，把 UserSsoDTO（含 roles）JSON 存入
   Redis  key = ns:sso:token:{token}   TTL = 7 天
        ▼
⑤ 把 token 写入 Cookie（NS_ACCOUNT_SSO_COOKIE）
        ▼
⑥ 后续每个请求：LoginInterceptor 读 Cookie → verifyToken → isExpired
   → getUserSsoDTOByToken → 存入 UserContextUtils（线程变量，全链路可用）
```

### 5.3 角色与管理员判定

- `ns_user.is_admin = 1` 的用户在登录时被注入 `grade = NS_SUPER_ADMIN_ROLE` 的角色；
- 前端 `App.vue` 的 `getAccess()` 遍历 `res.data.roles`，
  发现 `grade === 'NS_SUPER_ADMIN_ROLE'` 则置 `store.state.isManage = true`；
- 前端据此显示管理入口（文章审核/置顶、标签/资源管理、知识库管理等）；
- 另有 `NS_ORDINARY_ADMIN_ROLE`（普通管理员），服务端 `AiBotController.isAdmin()` 同时接受两者。

> **前后端判定**故意不完全对称：前端 `isManage` 只认 `NS_SUPER_ADMIN_ROLE`，
> 服务端 `AiBotController.isAdmin()` 额外接受 `NS_ORDINARY_ADMIN_ROLE`。结果是普通管理员
> **在 AI 域**「看不到按钮、但直接调接口不会被拒」——反过来（前端显示、后端拒绝）才是真正糟糕的错位。
> 放宽的这一侧不构成越权。
>
> ⚠️ **但这个放宽只限 AI 域**：`UrlAccessRightServiceImpl.isSuperAdmin()` **只认
> `NS_SUPER_ADMIN_ROLE`**，所以普通管理员调文章审核/标签/资源等管理接口**会被拒绝**。
> 两处规则不一致是有意的，修改角色体系时务必同时检查这两处。

### 5.4 路径级权限控制

```
UrlAccessCheckInterceptor
   └─▶ UrlAccessRightService.checkUrlAccess(currentUser, uri, pathVariablesJson)
         ├─ 未登录            → 拒绝
         ├─ 超管（NS_SUPER_ADMIN_ROLE） → 放行
         └─ 非超管：
              请求路径命中「管理路径黑名单」→ 拒绝
              否则                        → 放行
```

管理路径硬编码在 `UrlAccessRightServiceImpl.ADMIN_PATHS`，共 **13 条**（注意：这些是**去掉 `/api` 前缀**后的路径，
判定前 `isAdminPath()` 会先剥掉 `/api/`，并按 `equals(path)` 或 `startsWith(path + "/")` 匹配，
同时会剔除 query string）：

| 域 | 受保护路径 |
|----|-----------|
| 文章管理（5） | `/bbs/article/updateState`、`/articleTop`、`/getPendingReviewArticles`、`/getDisabledArticles`、`/getArticleCheckCount` |
| 标签管理（4） | `/bbs/label/create`、`/update`、`/delete`、`/uploadLabelLogo` |
| 资源管理（4） | `/bbs/resource/create`、`/update`、`/delete`、`/uploadResourceLogo` |

判定逻辑（`checkUrlAccess`）：

```
currentUser == null          → false（拒绝）
isSuperAdmin(currentUser)    → true（放行）
否则                          → !isAdminPath(url)
```

> **注意**：这里的 `isSuperAdmin` **只认 `NS_SUPER_ADMIN_ROLE`**，
> 与 `AiBotController.isAdmin()`（额外接受 `NS_ORDINARY_ADMIN_ROLE`）**不同**。
> 也就是说**普通管理员既看不到按钮，直接调管理接口也会被拒**——
> 只有 AI 域的接口才对普通管理员放宽。

拒绝时抛 `BusinessException(ResponseCode.URL_ACCESS_REFUSED)`，
由 `GlobalExceptionHandler` 转成统一信封，前端拿到非 0 的 `code` 与 `desc`。

### 5.5 访客数统计口径（重要）

`springboot/说明.txt` 专门记录了这个口径，**它不是 PV，也不是严格的自然日 UV**：

```
每个请求 → VisitInterceptor 记录
              ▼
        VisitServiceImpl 按「同一 IP 30 分钟内只记一次」去重
              ▼
        插入 ns_visit 表
              ▼
        COUNT(*) 的行数 ≈ 访客数
```

即：**时间片去重的独立访客口径**。

### 5.6 用户等级与积分

- 积分与等级存于 `fs_user_level`（`user_id`、`level`、`points`）；
- 等级区间由 `UserLevelEnum` 定义（Lv1~Lv6，见 4.2）；
- `bbs-user-service` 的定时任务 `UserLevelWorker` 周期调用
  `UserLevelService.updatePointsAll()` / `syncAll()` 重算；
- 前端以 `vue-ui/src/assets/img/level/Lv*.svg` 与 `badge-Lv*.svg` 渲染等级图标。

### 5.7 用户动态（Feed）

- 触发点由 `DynamicTypeEnum` 枚举：写文章、点赞文章、点赞评论、评论文章、评论回复、关注用户；
- 各业务 Service 在完成动作后调用 `DynamicService.create(DynamicDTO)` 写 `fs_dynamic`；
- `DynamicService.verifyExist()` 防重复；`delete(startTime, endTime)` 支持按时间窗清理；
- `UserDynamicWorker` 定时任务负责批量整理/回填；
- 前端通过 `GET /api/bbs/dynamic/getList` 按 `userId` 分页拉取。

### 5.8 评论树

评论用 `fs_comment.pre_id` 自关联形成多级结构：

- `CommentService.getAllChildrenByPreId(result, preId)` **递归**收集某评论的全部子评论；
- `CommentTreeUtils` 在 Java 侧把扁平列表组装成树，供 `getCommentByArticleId` 返回；
- 前端 `ArticleComment.vue` → `ChildComment.vue` → `CreateComment.vue` 递归渲染。

### 5.9 AI 问答链路与 SSE 协议

浏览器只与 `bbs-rest` 打交道，网关负责补身份、包信封、转发 SSE 与 multipart：

```
BotIndex.vue → BotChat.vue
   │  POST /api/bbs/ai/chat/stream  (原生 fetch + ReadableStream)
   ▼
bbs-rest AiBotController.chatStream()  → AiAgentClient.stream()
   ▼  (HTTP 反向代理，读超时 180s)
小罗Bot FastAPI :7861  → 多智能体图（LangGraph）
   ▼
SSE 事件回传：meta → plan → agent* → sources* → delta* → done → end
```

**SSE 事件协议**（前端按事件名分发，见 `aiBotService.js` 的 `SSE_EVENTS`）：

| 事件 | 载荷 | 前端用途 |
|------|------|---------|
| `meta` | `{sessionId, agents, webSearchEnabled}` | 初始化会话与智能体面板 |
| `plan` | `{plan: [...], reason}` | 渲染调度计划 |
| `agent` | `{agent, label, status: start\|done\|skipped, detail}` | 渲染「智能体协作过程」 |
| `sources` | `{forum: [...], web: [...]}` | 参考来源列表 |
| `delta` | `{text}` | 打字机式追加正文 |
| `done` | `{answer, usedWebSearch, answerScore, citations, images, plan, trace, elapsedMs}` | 收尾、统计与引用 |
| `error` | `{message}` | 错误提示 |
| `end` | `{}` | 流结束（含 `{aborted:true}` 主动中断） |

> **为什么 SSE 不走 axios**：axios 0.21 会把响应整体缓冲，且论坛的响应拦截器要求响应体是
> `{code:0,...}` 的 JSON。所以流式对话用原生 `fetch` + `ReadableStream` 自己解析 `event:` / `data:` 帧，
> 普通接口继续走 axios 以复用统一信封与错误处理。

### 5.10 文件上传

| 环节 | 限制配置 | 值 |
|------|---------|-----|
| Servlet multipart | `spring.servlet.multipart.max-file-size` | 100 MB |
| Servlet multipart | `spring.servlet.multipart.max-request-size` | 1000 MB |
| 业务上传 | `file.source.length`（`FileLengthUtils` 校验） | 5 MB（5242880） |
| AI 附件（网关侧） | `ai.agent.upload-max-bytes` | 20 MB（20971520） |
| AI 附件（服务侧） | `attachment.max_size_mb` | 20 MB |

上传路径：`FileServiceImpl` 写入 `auth.file-storage-path`（默认 `./uploads`），
返回 `auth.file-url-prefix` 前缀的可访问 URL，经 `/static/**` 提供给浏览器。
目录按业务分子目录：`articleTitleMap/`（题图）、`headPortrait/`（头像）。

---

## 六、REST 接口全清单

**统一前缀**：`server.servlet.context-path = /api`。
下表路径均为**含 `/api` 的完整路径**。`🔓` = 标注 `@NoNeedLogin`（免登录）；`🔒` = 需要登录。

### 6.1 登录与账号（`LoginController` → `/bbs/sso/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/bbs/sso/register` | `@RequestBody UserDTO` | 🔓 注册（返回 `UserTokenDTO`） |
| POST | `/api/bbs/sso/login` | `@RequestBody UserLoginDTO` | 🔓 登录（返回 `UserTokenDTO`，写 Cookie + Redis） |
| GET | `/api/bbs/sso/logout` | — | 🔓 登出（清 Cookie 与 Redis token） |

### 6.2 文章（`ArticleController` → `/bbs/article/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/bbs/article/getList` | `ArticleSearchDTO` | 🔓 文章列表（分页） |
| GET | `/api/bbs/article/getPersonalArticles` | `ArticleSearchDTO`, `articleStateEnum?` | 🔓 个人文章（可按状态过滤） |
| GET | `/api/bbs/article/getPendingReviewArticles` | `ArticleSearchDTO` | 待审核文章（管理） |
| GET | `/api/bbs/article/getDisabledArticles` | `ArticleSearchDTO` | 已禁用文章（管理） |
| POST | `/api/bbs/article/updateState` | `@RequestBody ArticleDTO` | 修改审批状态（审核/禁用/启用） |
| GET | `/api/bbs/article/getLikesArticle` | `LikeSearchDTO` | 🔓 我点赞过的文章 |
| GET | `/api/bbs/article/getArticleCommentVisitTotal` | — | 🔓 文章/评论/访问总数（首页统计） |
| GET | `/api/bbs/article/getById` | `id`, `isPv?` | 🔓 文章详情（`isPv=true` 时累加阅读量） |
| POST | `/api/bbs/article/create` | `MultipartFile picture?` + 表单 | 发布文章 |
| POST | `/api/bbs/article/update` | `MultipartFile picture?` + 表单 | 更新文章 |
| POST | `/api/bbs/article/uploadPicture` | `MultipartFile picture` | 正文插图上传（返回 URL） |
| GET | `/api/bbs/article/getCountById` | `id` | 🔓 单篇统计（点赞/评论/访问） |
| GET | `/api/bbs/article/articleTop` | `id`, `top` | 置顶 / 取消置顶（管理） |
| POST | `/api/bbs/article/delete/{id}` | `@PathVariable Integer` | 删除文章 |
| GET | `/api/bbs/article/getArticleCheckCount` | `title?` | 文章审核数据量（管理角标） |

### 6.3 评论（`CommentController` → `/bbs/comment/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/bbs/comment/getCommentByArticleId` | `CommentSearchDTO` | 🔓 文章评论（树形） |
| GET | `/api/bbs/comment/getLatestComment` | `CommentSearchDTO` | 🔓 最新评论（分页，侧栏用） |
| POST | `/api/bbs/comment/create` | `@RequestBody CommentDTO` | 发表评论/回复 |
| POST | `/api/bbs/comment/delete/{commentId}` | `@PathVariable Integer` | 删除评论 |

### 6.4 用户（`UserController` → `/bbs/user/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/bbs/user/getCurrentUserRights` | — | 当前用户权限/角色（`UserRightsDTO`）——**登录态探测接口** |
| GET | `/api/bbs/user/getAdminUserIds` | — | 🔓 所有管理员 id（头像「会员」标识） |
| GET | `/api/bbs/user/getFollowUsers` | `FollowSearchDTO` | 🔓 关注/粉丝列表（分页） |
| GET | `/api/bbs/user/updateFollowState` | `toUser` | 关注 / 取关（切换） |
| GET | `/api/bbs/user/updateLikeState` | `articleId` | 点赞 / 取消（切换） |
| GET | `/api/bbs/user/updateLikeCommentState` | `commentId` | 评论点赞 / 取消（切换） |
| GET | `/api/bbs/user/getHotAuthorsList` | `UserSearchDTO` | 🔓 热门作者榜 |
| GET | `/api/bbs/user/getUserInfo` | `userId` | 🔓 作者信息 |
| GET | `/api/bbs/user/getFollowCount` | `userId` | 🔓 关注数 / 粉丝数 |
| POST | `/api/bbs/user/uploadUserPicture` | `MultipartFile picture` | 上传头像 |
| POST | `/api/bbs/user/updateUserBasicInfo` | `@RequestBody UserDTO` | 修改基本资料 |
| GET | `/api/bbs/user/sendEmailVerifyCode` | `email` | 🔓 发送邮箱验证码 |
| GET | `/api/bbs/user/sendSmsVerifyCode` | `phone` | 🔓 发送短信验证码 |
| POST | `/api/bbs/user/bindEmail` | `@RequestBody UserEmailDTO` | 绑定邮箱 |
| POST | `/api/bbs/user/bindPhone` | `@RequestBody UserEmailDTO` | 绑定手机 |
| POST | `/api/bbs/user/untieEmail` | — | 解绑邮箱 |
| POST | `/api/bbs/user/untiePhone` | — | 解绑手机 |
| POST | `/api/bbs/user/updatePassword` | `@RequestBody UserPasswordDTO` | 修改密码 |
| GET | `/api/bbs/user/isValidEmail` | `email` | 邮箱查重 |
| GET | `/api/bbs/user/isValidPhone` | `phone` | 手机查重 |
| GET | `/api/bbs/user/isValidUser` | `username` | 🔓 用户名查重 |
| POST | `/api/bbs/user/isPhoneExist/{phone}` | `@PathVariable String` | 🔓 手机是否已注册 |
| POST | `/api/bbs/user/isEmailExist/{email}` | `@PathVariable String` | 🔓 邮箱是否已注册 |
| POST | `/api/bbs/user/phoneResetPassword` | `@RequestBody UserEmailDTO` | 🔓 手机重置密码 |
| POST | `/api/bbs/user/emailResetPassword` | `@RequestBody UserEmailDTO` | 🔓 邮箱重置密码 |
| GET | `/api/bbs/user/getUserOperateCount` | `userId` | 🔓 用户操作统计（文章/关注/点赞数） |

### 6.5 标签（`LabelController` → `/bbs/label/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/bbs/label/create` | `@RequestBody LabelDTO` | 新建标签（管理） |
| POST | `/api/bbs/label/uploadLabelLogo` | `MultipartFile logo?` | 上传标签 logo（管理） |
| POST | `/api/bbs/label/update` | `@RequestBody LabelDTO` | 更新标签（管理） |
| GET | `/api/bbs/label/getList` | `LabelSearchDTO` | 🔓 标签列表（分页） |
| POST | `/api/bbs/label/delete/{id}` | `@PathVariable Integer` | 删除标签（管理） |

### 6.6 资源导航（`ResourceController` → `/bbs/resource/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/bbs/resource/create` | `@RequestBody ResourceNavigateDTO` | 新建资源（管理） |
| POST | `/api/bbs/resource/uploadResourceLogo` | `MultipartFile logo?` | 上传资源 logo（管理） |
| POST | `/api/bbs/resource/update` | `@RequestBody ResourceNavigateDTO` | 更新资源（管理） |
| GET | `/api/bbs/resource/getList` | `ResourceNavigateSearchDTO` | 🔓 资源列表（分页） |
| GET | `/api/bbs/resource/getCategorys` | — | 🔓 资源分类列表 |
| POST | `/api/bbs/resource/delete/{id}` | `@PathVariable Integer` | 删除资源（管理） |

### 6.7 轮播图（`SlideshowController` → `/bbs/carousel/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/bbs/carousel/getList` | — | 🔓 轮播图列表 |

### 6.8 动态（`DynamicController` → `/bbs/dynamic/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/bbs/dynamic/getList` | `userId`, `currentPage`, `pageSize` | 🔓 用户动态（分页） |

### 6.9 通知（`NotifyController` → `/bbs/notify/`）

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| POST | `/api/bbs/notify/haveRead` | `type` | 全部已读（按类型） |
| POST | `/api/bbs/notify/markRead` | `@RequestBody List<Integer> notifyIds` | 标记指定通知已读 |
| GET | `/api/bbs/notify/getList` | `NotifySearchDTO` | 通知列表（分页） |

### 6.10 小罗Bot AI（`AiBotController` → `/bbs/ai/`）

> **整个 Controller 标注 `@NoNeedLogin`**：未登录用户也能用（以 guest 身份参与知识库检索与长期记忆）。
> 「仅管理员」的接口由 Controller 内部 `requireAdmin()` 单独判定，返回 `code=1`。

| 方法 | 路径 | 参数 | 权限 | 说明 |
|------|------|------|------|------|
| POST | `/api/bbs/ai/chat` | `@RequestBody AiChatDTO` | 所有人 | 非流式对话（兜底） |
| POST | `/api/bbs/ai/chat/stream` | `@RequestBody AiChatDTO` | 所有人 | **SSE 流式对话**（页面主用） |
| GET | `/api/bbs/ai/sessions` | — | 所有人 | 会话列表 |
| DELETE | `/api/bbs/ai/sessions/{sessionId}` | `@PathVariable String` | 所有人 | 删除会话 |
| GET | `/api/bbs/ai/health` | — | 所有人 | 健康检查（模型 / 知识库 / 论坛数据源） |
| GET | `/api/bbs/ai/kb/status` | — | 所有人 | 知识库条目数与来源分类（非管理员**服务端摘除 `collection` 字段**） |
| POST | `/api/bbs/ai/kb/sync` | `source?` | **仅管理员** | 触发论坛知识库同步（后台任务） |
| GET | `/api/bbs/ai/kb/sync/status` | — | **仅管理员** | 同步进度 |
| GET | `/api/bbs/ai/kb/upload/limits` | — | **仅管理员** | 上传限制（扩展名、大小上限） |
| POST | `/api/bbs/ai/kb/upload` | `MultipartFile file` | **仅管理员** | 上传文档附件并入库（异步，返回 `taskId`） |
| GET | `/api/bbs/ai/kb/upload/status/{taskId}` | `@PathVariable String` | **仅管理员** | 附件解析/入库进度 |
| GET | `/api/bbs/ai/kb/attachments` | — | **仅管理员** | 已入库附件列表 |
| DELETE | `/api/bbs/ai/kb/attachments/{docId}` | `@PathVariable String` | **仅管理员** | 删除附件及其知识条目 |
| GET | `/api/bbs/ai/about` | — | 所有人 | 能力说明（附 `currentUserIsAdmin`） |

> **权限的三处实现必须同步修改**（隐藏前端拦不住直接调接口的人，服务端必须再挡一道）：
> ① `AiBotController` 的 `requireAdmin()` / `kbStatus()` 脱敏；
> ② `MultimodalRAG/tools/dev_gateway.py` 的 `ADMIN_ONLY_PATHS` / `ADMIN_ONLY_PREFIXES` / `SANITIZE_FOR_GUEST`；
> ③ 前端 `BotChat.vue` 的 `isAdmin` 与三处 `v-if`。

**接口统计**：共 **11 个 Controller，78 个 HTTP 端点**：

| Controller | 端点数 |
|-----------|-------|
| `UserController` | 26 |
| `ArticleController` | 15 |
| `AiBotController` | 14 |
| `ResourceController` | 6 |
| `LabelController` | 5 |
| `CommentController` | 4 |
| `LoginController` / `NotifyController` | 各 3 |
| `DynamicController` / `SlideshowController` | 各 1 |
| **合计** | **78** |

### 6.11 交互式 API 文档

`bbs-rest` 集成了 Knife4j。启动后访问：

```
http://127.0.0.1:7010/api/doc.html
```

（受 `swagger.show: true` 控制；相关路径已加入 `NOT_LOGIN_URLS` 免登录白名单。）

---

## 七、前端工程结构（vue-ui）

### 7.1 构建与开发服务器

`vue.config.js` 关键配置：

```js
devServer: {
  proxy: { "/api": { target: "http://localhost:7010", ws: true, changeOrigin: true,
                     router: req => "http://" + req.headers.host.split(":")[0] + ":7010" } },
  disableHostCheck: true,
  port: 8082                      // ★ 开发服务器端口
},
css:      { loaderOptions: { less: { lessOptions: { javascriptEnabled: true } } } },
assetsDir: "static",
productionSourceMap: false,       // 生产不输出 source map
configureWebpack: {
  optimization: { minimizer: [new UglyfyJsPlugin(...)] },     // JS 压缩
  plugins: [ new CompressionPlugin({ algorithm: "gzip", threshold: 10240, ... }) ],  // gzip
  externals: { "vue2-leaflet": "Vue2Leaflet", leaflet: "L" }  // CDN 外链
}
```

- **代理**：所有 `/api` 请求转发到 `http://localhost:7010`（即 `bbs-rest`）。
  `router` 函数让局域网内其他设备访问时也能正确指向后端所在主机。
- **主题动态切换**：`src/config/config.js` 用 `webpack-theme-color-replacer`
  在构建期生成 `css/theme-colors-[contenthash:8].css`，运行时由
  `src/config/utils.js` 的 `changeColor()` 替换颜色。

**npm 脚本**：

```bash
npm run serve     # 开发（:8082）
npm run build     # 生产构建（输出 dist/，assets 在 static/）
```

### 7.2 入口与应用外壳

`src/main.js`：注册 Vue 插件（antd、router、store、i18n、iconfont、全局 CSS、axios 拦截器）。

`src/App.vue`（447 行）承担了应用外壳与多项全局职责：

| 职责 | 实现 |
|------|------|
| 根容器 | `a-config-provider` 只渲染**默认插槽第一个子节点**，所以 `.app-root` 必须包住背景 iframe 与 `#app` |
| 粒子背景 | `<iframe class="bg-iframe" src="/backgroundHtml/bg.html">` 固定定位 `z-index:-1`，`pointer-events:none` |
| 权限初始化 | `mounted()` 调 `getAccess()` → `GET /api/bbs/user/getCurrentUserRights`，置 `isLogin` / `userId` / `isManage` |
| 管理员列表 | `getAdminUserIds()` → `GET /api/bbs/user/getAdminUserIds`，供头像「会员」标识 |
| 响应式 | `initDom()` 设置 `width`/`height`/`collapsed`(<1000px)/`collapsedMax`(<1300px)，**立即执行一次**再挂 `onresize`（避免热更新后 `width=0` 导致不渲染） |
| 主题与语言 | `setLanguageAndTheme()` 从 `localStorage` 读取，默认 `#D4AF37`（镀金）与浏览器语言 |
| 点击星火特效 | `spawnSpark()` 用 Web Animations API 在点击处绽放金色星点，尊重 `prefers-reduced-motion` |
| 全局样式 | `#app [style*="background:#fff"]` 等选择器统一改造成**磨砂玻璃卡片**（半透明白 + `backdrop-filter`），并对不支持 `backdrop-filter` 的浏览器做降级 |

### 7.3 路由表（`src/router/index.js`，总共 18 条）

模式 `history`，**未配置任何路由守卫**（登录态由 `App.vue` 与拦截器信封处理）。

| 路径 | 名称 | 组件 | 说明 |
|------|------|------|------|
| `/` | `home` | `index/Index` | 首页（文章流 + 轮播 + 侧栏） |
| `/search` | — | `index/Index` | 搜索（复用首页，靠 query 参数） |
| `/recommended` | `recommended` | `index/AuthorsListIndex` | 推荐作者 |
| `/write` | — | `index/WriteArticleIndex` | 写文章 |
| `/edit/:id` | — | `index/WriteArticleIndex` | 编辑文章 |
| `/detail/:id` | `detail` | `index/ArticleDetailIndex` | 文章详情 |
| `/empty` | — | `utils/CustomEmpty` | 空状态页 |
| `/user/:id` | — | `index/UserCenterIndex` | 个人中心 |
| `/user/:id/:userCenterTab` | — | `index/UserCenterIndex` | 个人中心（子 Tab） |
| `/label` | `label` | `index/LabelIndex` | 标签广场 |
| `/label/:id` | — | `index/LabelToArticleIndex` | 某标签下的文章 |
| `/settings` | — | `index/SetUpIndex` | 设置（容器） |
| `/settings` → `` | — | redirect `profile` | 默认重定向 |
| `/settings/profile` | `profile` | `user/ProfileContent` | 资料设置 |
| `/settings/account` | `account` | `user/AccountSettings` | 账号设置（绑定/改密） |
| `/resource` | `resource` | `index/ResourceIndex` | 资源导航 |
| `/book` | `book` | `index/Book` | 文档/书籍页 |
| `/about` | `about` | `index/About` | 关于 |
| **`/bot`** | `bot` | **`index/BotIndex`** | **小罗Bot AI 搜索引擎** |
| `/commentDonate` | `commentDonate` | `index/CommentDonateIndex` | 评论捐赠 |
| `/500` | `500` | `errorPage/ServerError` | 服务器错误页 |
| `/:pathMatch(.*)*` | `404` | `errorPage/NotFound` | 404 兜底 |

> `router/index.js` 开头重写了 `VueRouter.prototype.push`，捕获重复导航的
> `NavigationDuplicated` 异常，避免控制台警告。

### 7.4 状态管理（`src/store/index.js`，Vuex 单模块）

**state 关键字段**：

| 字段 | 初始值 | 说明 |
|------|-------|------|
| `isLogin` | `false` | 是否已登录 |
| `loginVisible` / `registerVisible` | `false` | 登录 / 注册弹窗 |
| `mobileResetPasswordVisible` / `emailResetPasswordVisible` | `false` | 找回密码弹窗 |
| `userId` | `""` | 登录用户 id |
| `picture` | `""` | 头像（由响应头 `X-User-Picture` 更新） |
| `isManage` | `false` | 是否超级管理员 |
| `adminUserIds` | `[]` | 管理员 id 集合（头像会员标识） |
| `articleCheck` | `"enable"` | 文章审核筛选态 |
| `userMaxLength` | `10` | 用户名长度限制 |
| `colorOptions` | `["#D4AF37","#C0C0C0","#000000"]` | 主题色：镀金 / 银灰 / 黑色 |
| `themeColor` | `"#D4AF37"` | 当前主题色（默认镀金） |
| `isCarousel` | `1` | 是否启用跑马灯 |
| `collapsed` / `collapsedMax` | `false` | 侧栏收缩态 |
| `width` / `height` | `0` | 视口尺寸 |
| `locale` | `"zh_CN"` | 语言 |
| `systemNotifyCount` / `taskNotifyCount` | `0` | 通知角标（由响应头更新） |
| `translate` | function | 国际化取值方法（`langs[locale]` 逐级下钻，失败回退末段） |

**getters**：`formCol`（表单栅格）、`contentWidth`（内容区宽度，按 `collapsed` 计算）、
`isPc`（`width > 750`）、`isAdminUser(id)`（判断某用户是否管理员，当前登录用户优先）、
`stateList`（启用/禁用选项）。

**mutations**：`changeColor(color)` —— 调 `utils.updateTheme()` 热替换样式、
写 `localStorage.themeColor`、同步 CSS 变量 `--theme-color`。

### 7.5 HTTP 层（`src/service/axios.js`）

```js
axios.defaults.timeout = 15000;   // 15 秒

// 响应拦截器
① 读响应头 X-User-Picture        → store.state.picture
② 读响应头 X-System-Notify-Count → store.state.systemNotifyCount
③ 读响应头 X-Task-Notify-Count   → store.state.taskNotifyCount
④ status===200 且 body.code===0  → resolve(response.data)
⑤ body.code===302（且非 getCurrentUserRights）→ isLogin=false, loginVisible=true, reject
⑥ 其它                           → throw response.data
```

### 7.6 API 服务层全清单（`src/service/`，11 个文件 / 81 个导出函数）

| 服务文件 | 函数数 |
|---------|-------|
| `userService.js` | 26 |
| `aiBotService.js` | 13（另含 4 个模块内辅助/常量） |
| `articleService.js` | 15 |
| `resourceService.js` | 6 |
| `labelService.js` | 5 |
| `commentService.js` | 4 |
| `loginService.js` / `messageService.js` | 各 3 |
| `carouselService.js` / `dynamicService.js` | 各 1 |
| `axios.js` | 拦截器（无导出函数） |

#### `aiBotService.js`（小罗Bot，含唯一的手写 SSE 解析）

| 函数 | 方法 | 路径 |
|------|------|------|
| `health()` | GET | `/api/bbs/ai/health` |
| `kbStatus()` | GET | `/api/bbs/ai/kb/status` |
| `kbSync(params)` | POST | `/api/bbs/ai/kb/sync` |
| `kbSyncStatus()` | GET | `/api/bbs/ai/kb/sync/status` |
| `about()` | GET | `/api/bbs/ai/about` |
| `sessions()` | GET | `/api/bbs/ai/sessions` |
| `kbUploadLimits()` | GET | `/api/bbs/ai/kb/upload/limits` |
| `kbUpload(file, onProgress)` | POST | `/api/bbs/ai/kb/upload`（multipart，超时 300s，带上传进度） |
| `kbUploadStatus(taskId)` | GET | `/api/bbs/ai/kb/upload/status/{taskId}` |
| `kbAttachments()` | GET | `/api/bbs/ai/kb/attachments` |
| `kbAttachmentDelete(docId)` | DELETE | `/api/bbs/ai/kb/attachments/{docId}` |
| `chat(data)` | POST | `/api/bbs/ai/chat`（非流式兜底） |
| `chatStream(data, handlers, options)` | POST | `/api/bbs/ai/chat/stream`（**原生 fetch + SSE**） |

`chatStream` 的处理器签名：`onMeta` / `onPlan` / `onAgent` / `onSources` / `onDelta` /
`onDone` / `onError` / `onEnd`，`options.signal` 支持主动中止（「停止生成」）。
解析逻辑在模块级 `parseFrame(raw, handlers)`：按空行分帧、兼容 `\r\n`、
忽略 `:` 注释行、只认 `SSE_EVENTS` 白名单内的事件名、`JSON.parse` 失败时降级为 `{text: rawData}`。

#### 其余 10 个服务（全部走 axios）

| 文件 | 函数 → 路径 |
|------|-----------|
| `articleService.js` | `getArticleList`→`/api/bbs/article/getList`、`getPersonalArticles`→`/getPersonalArticles`、`getPendingReviewArticles`、`getDisabledArticles`、`updateState`→`POST /updateState`、`getLikesArticle`、`getArticleCommentVisitTotal`、`uploadPicture`→`POST /uploadPicture`、`articleCreate`→`POST /create`、`articleUpdate`→`POST /update`、`getArticleById`→`/getById`、`getArticleCountById`→`/getCountById`、`articleTop`、`articleDelete`→`POST /delete/{id}`、`getArticleCheckCount`（均在 `/api/bbs/article/` 下） |
| `commentService.js` | `getCommentByArticleId`、`getLatestComment`、`createComment`→`POST /create`、`deleteComment`→`POST /delete/{id}`（`/api/bbs/comment/`） |
| `carouselService.js` | `getCarouselList`→`GET /api/bbs/carousel/getList` |
| `dynamicService.js` | `getDynamicList`→`GET /api/bbs/dynamic/getList` |
| `labelService.js` | `getLabelList`、`uploadLabelLogo`→`POST`、`labelCreate`→`POST /create`、`labelUpdate`→`POST /update`、`labelDelete`→`POST /delete/{id}`（`/api/bbs/label/`） |
| `loginService.js` | `register`→`POST /api/bbs/sso/register`、`login`→`POST /api/bbs/sso/login`、`logout`→`GET /api/bbs/sso/logout` |
| `messageService.js` | `getMessageList`→`GET /api/bbs/notify/getList`、`makeAllRead`→`POST /api/bbs/notify/haveRead`、`markRead`→`POST /api/bbs/notify/markRead` |
| `resourceService.js` | `getResourceList`、`getCategorys`、`uploadResourceLogo`→`POST`、`resourceCreate`→`POST /create`、`resourceUpdate`→`POST /update`、`resourceDelete`→`POST /delete/{id}`（`/api/bbs/resource/`） |
| `userService.js` | 27 个函数，覆盖 `/api/bbs/user/` 全部端点（权限探测、管理员列表、点赞/关注切换、作者信息、头像上传、资料更新、验证码、绑定/解绑邮箱手机、改密、查重、重置密码、操作统计） |

### 7.7 组件清单（`src/components/`，73 个 `.vue` 文件）

#### `index/` —— 页面级组件（17 个）

| 文件 | 行数 | 说明 |
|------|------|------|
| `Index.vue` | 419 | 首页：文章流 + 轮播 + 侧栏 + 排序/搜索 |
| `ArticleDetailIndex.vue` | 197 | 文章详情页外壳 |
| `BotIndex.vue` | 262 | **小罗Bot 页面**：hero + 实时统计（知识条目/文章/评论数） |
| `LabelIndex.vue` | 132 | 标签广场 |
| `LabelToArticleIndex.vue` | 207 | 标签下的文章列表 |
| `ResourceIndex.vue` | 129 | 资源导航页 |
| `UserCenterIndex.vue` | 173 | 个人中心外壳 |
| `AuthorsListIndex.vue` | 147 | 推荐作者页 |
| `WriteArticleIndex.vue` | 20 | 写文章页薄壳 |
| `SetUpIndex.vue` | 123 | 设置页外壳 |
| `About.vue` | 103 | 关于页 |
| `Book.vue` | 53 | 文档/书籍页 |
| `CommentDonateIndex.vue` | 66 | 评论捐赠页 |
| `head/IndexHeader.vue` | 450 | 顶栏（含小罗Bot 菜单项） |
| `head/IndexMenu.vue` | 213 | 顶栏菜单 |
| `head/IndexSider.vue` | 52 | 侧边栏 |
| `messages/{Message, MessageBox, Notification}.vue` | 117/197/115 | 消息中心三件套 |

#### `bot/` —— 小罗Bot 聊天（2 个，共 2232 行，是前端最重的模块）

| 文件 | 行数 | 说明 |
|------|------|------|
| `BotChat.vue` | **1686** | 聊天主组件：SSE 消费、Markdown 渲染、智能体协作过程面板、参考来源、知识库面板（同步/上传/附件列表）、联网开关、会话管理、`isAdmin` 权限门控 |
| `BotMessage.vue` | 546 | 单条消息气泡：Markdown 正文、引用列表、图片、统计行 |

#### 其余分组

| 目录 | 组件 | 说明 |
|------|------|------|
| `article/` | `ArticleDetail.vue`(463)、`FrontPageArticle.vue`(398)、`WriteArticle.vue`(278)、`ArticleBasicInfo.vue`(182)、`LeftButtons.vue`(115)、`ArticleCheck.vue`(113)、`UploadImage.vue`(54) | 文章详情/列表项/写作/审核/插图 |
| `comment/` | `ChildComment.vue`(217)、`ArticleComment.vue`(118)、`CreateComment.vue`(104) | 多级评论渲染与发表 |
| `user/` | `ProfileContent.vue`(361)、`UserTabs.vue`(348)、`PersonalInfoDisplay.vue`(295)、`BindEmail.vue`(211)、`AccountSettings.vue`(209)、`BindPhone.vue`(200)、`ChangePassword.vue`(161)、`UploadModal.vue`(161)、`FollowTabs.vue`(143)、`AuthorsListContent.vue`(139)、`FollowAuthorsListContent.vue`(135)、`Dynamic.vue`(116)、`SetUpMenu.vue`(69) | 个人中心与账号管理 |
| `right/` | `MarkdownToc.vue`(161)、`FriendDonate.vue`(139)、`AuthorBlock.vue`(127)、`AuthorsList.vue`(122)、`RelatArticle.vue`(117)、`LatestComment.vue`(99)、`ProjectIntro.vue`(95)、`PersonalAchievement.vue`(80)、`FilingInfo.vue`(72)、`FollowCount.vue`(66) | 右侧栏各类卡片（目录/捐赠/作者/相关文章/最新评论/备案信息） |
| `label/` | `LabelContent.vue`(228)、`LabelCreate.vue`(138)、`ImageUpload.vue`(125) | 标签展示与新建 |
| `resource/` | `ResourceContent.vue`(261)、`ResourceCreate.vue`(183)、`ImageUpload.vue`(126) | 资源展示与新建 |
| `login/` | `EmailResetPassword.vue`(202)、`MobileResetPassword.vue`(202)、`Register.vue`(179)、`Login.vue`(110) | 登录/注册/两种找回密码 |
| `utils/` | `FooterButtons.vue`(287)、`Clock.vue`(187)、`CustomEmpty.vue`(88)、`Spin.vue`(19) | 底部悬浮按钮（含二维码）、时钟、空状态、加载 |
| `concern/` | `SlideShow.vue`(68) | 轮播图 |
| `errorPage/` | `ServerError.vue`(69)、`NotFound.vue`(68) | 500 / 404 |
| `books/` | `CairoValue.vue`(293) | 「开罗价值观」内容页 |

### 7.8 国际化（`src/i18n/`）

```
i18n/
├── zh_CN.js       # 中文入口
├── en_US.js       # 英文入口
├── zh/common.js   # 中文词条
└── en/common.js   # 英文词条
```

- `store.state.locale` 默认 `zh_CN`，由 `App.vue` 的 `setLanguageAndTheme()` 决定：
  有 `localStorage.language` 用它，否则按 `navigator.language`（`zh-CN` → `zh_CN`，其它 → `en_US`）。
- 取值通过 `store.state.translate("common.enabled")` —— 以 `.` 逐级下钻，
  任一层失败则回退到路径最后一段（作为兜底文案，避免显示空白）。
- 组件库语言包在 `App.vue` 用 `a-config-provider :locale` 绑定 antd 的 `zh_CN` / `en_US`。

### 7.9 工具与配置（`src/utils/`、`src/config/`）

| 文件 | 说明 |
|------|------|
| `utils/markdown.js` | Markdown 渲染（基于 `marked` 4.3.0），文章正文与 AI 回答共用 |
| `utils/utils.js` | 通用工具函数 |
| `config/config.js` | `webpack-theme-color-replacer` 插件配置（构建期）；`matchColors` 锁定 antd 原始蓝 `#1890ff` 系列；`changeSelector()` 修正若干 antd 选择器优先级问题 |
| `config/utils.js` | 运行时 `updateTheme(newPrimaryColor)`，热替换已编译的 CSS 颜色 |

### 7.10 静态资源（`src/assets/`）

| 目录 | 内容 |
|------|------|
| `css/` | 全局样式（3 个 `.css` + 1 个 `.less`） |
| `font/` | `hamburgserial-xbold.ttf` + `font.css` |
| `icon/` | iconfont 字体与脚本（`iconfont.js/.json/.ttf/.woff/.woff2`）——含管理员标识 `icon-huiyuan` |
| `img/level/` | **等级徽章系统**：`Lv1.svg`~`Lv6.svg` + `badge-Lv1.svg`~`badge-Lv6.svg`（对应 `UserLevelEnum`） |
| `img/message/` | 消息中心插图 |
| `img/chinaPay/` | 捐赠/支付二维码 |
| `img/contactway/` | 联系方式图标 |
| `img/` | 其它：`logo-lanse222.png`、`about-nsbbs.png`、`404.svg`、`badge.svg` |
| `json/nav.js` | 导航菜单数据结构 |

`public/backgroundHtml/` 存放全局粒子背景（`bg.html` 及其依赖），
以 iframe 方式挂载在 `App.vue` 最底层。

---

## 八、数据库设计

系统使用**两个 MySQL 库**，通过不同的命名前缀区分归属：

| 库 | 建库脚本 | 表数 | 前缀 | 归属服务 |
|----|---------|------|------|---------|
| `open_bbs` | `springboot/db备份/open_bbs.sql`（1339 行，126 KB） | **13** | `fs_` | `bbs-article-service` + `bbs-user-service`（**共用**） |
| `ns_auth` | `springboot/bbs-auth/db/ns_auth.sql`（4 KB） | **4** | `ns_` | `bbs-auth` |

> ⚠️ **两个前缀都是历史的产物**：业务库表用 `fs_`（早期项目名），鉴权库表用 `ns_`
> （来自上游 `nansheng-common` 体系）。它们**没有外键约束**彼此关联——
> `fs_*` 里的 `create_user` / `like_user` / `follow.from_user` 等字段在逻辑上指向
> `ns_auth.ns_user.id`，但**跨库无法建外键**，一致性靠应用层保证。
> 排查数据问题时务必记住这一点。

**通用约定**：所有表 `ENGINE=InnoDB`、`CHARSET=utf8mb4`、`COLLATE=utf8mb4_general_ci`；
主键统一为 `PRIMARY KEY (id) USING BTREE`；绝大多数业务表带
`is_deleted`（逻辑删除）、`create_user`、`update_user`、`create_time`、`update_time` 审计字段。

### 8.1 `open_bbs` 业务库（13 张表）

#### 8.1.1 `fs_article` —— 文章

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 文章编号 |
| `title_map` | varchar(120) | NULL | | 题图 |
| `title` | varchar(100) | NULL | | 文章标题 |
| `content` | longtext | NULL | | 文章内容（Markdown） |
| `state` | tinyint(1) | 1 | | 状态（0 禁用，1 启用） |
| `pv` | int | 0 | | 文章浏览量 |
| `top` | int | NULL | | 置顶（数字越大越靠前） |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除（0 正常，1 删除） |
| `create_user` | bigint | NULL | | 创建用户 id |
| `update_user` | bigint | NULL | | 更新用户 id |
| `create_time` | datetime | NULL | | 创建时间 |
| `update_time` | datetime | NULL | | 更新时间 |

`AUTO_INCREMENT = 42`，种子数据 **6 行**。

> 审核态在应用层用 `ArticleStateEnum` 表达（`pendingReview=-1` / `disabled=0` / `enable=1`），
> 数据库里 `state` 只承载 0/1；**待审核是应用层语义**，不是独立的数据库状态值。

#### 8.1.2 `fs_comment` —— 评论

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 评论编号 |
| `pre_id` | int | NULL | | **父评论 id**（自关联，构成多级评论树） |
| `content` | text | NULL | | 评论内容 |
| `article_id` | int(11) UNSIGNED ZEROFILL | NULL | | 被评论帖子 id |
| `state` | tinyint(1) | 1 | | 状态（0 禁用，1 启用） |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除 |
| `comment_user` | bigint | NULL | | 评论用户 id |
| `create_time` | datetime | NULL | | 创建时间 |
| `update_time` | datetime | NULL | | 更新时间 |

`AUTO_INCREMENT = 25`，无种子数据。

#### 8.1.3 `fs_label` —— 标签

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 标签编号 |
| `label_name` | varchar(64) | NULL | | 标签名字 |
| `logo` | varchar(120) | NULL | | logo（图片 URL） |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除 |
| `create_user` / `update_user` | bigint | NULL | | 审计 |
| `create_time` / `update_time` | datetime | NULL | | 审计 |

`AUTO_INCREMENT = 21`，种子数据 **16 行**（如 `Vue.js`，logo 指向
`http://aid.nansin.top/default/labelPicture-...png`）。

#### 8.1.4 `fs_article_label` —— 文章↔标签 多对多

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 文章标签编号 |
| `article_id` | int | NULL | | 文章 id |
| `label_id` | int | NULL | | 标签 id |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除 |
| `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

`AUTO_INCREMENT = 38`，种子数据 **26 行**。

#### 8.1.5 `fs_like` —— 文章点赞

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 点赞编号 |
| `article_id` | int | NULL | | 文章 id |
| `state` | tinyint(1) | 1 | | 状态（0 取消，1 点赞） |
| `like_user` | bigint | NULL | | 点赞用户 id |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

`AUTO_INCREMENT = 40`。**用 `state` 而非删除行**记录取消点赞。

#### 8.1.6 `fs_comment_like` —— 评论点赞

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 评论点赞编号 |
| `comment_id` | int | NULL | | 评论 id |
| `state` | tinyint(1) | 1 | | 状态（0 取消，1 点赞） |
| `like_user` | bigint | NULL | | 评论点赞用户 id |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

`AUTO_INCREMENT = 11`。

#### 8.1.7 `fs_follow` —— 关注关系

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 关注编号 |
| `from_user` | bigint | NULL | | 发起关注的人 |
| `state` | tinyint(1) | 1 | | 状态（0 取消，1 关注） |
| `to_user` | bigint | NULL | | 被关注的人 |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

`AUTO_INCREMENT = 33`。无唯一约束，**同一对用户可有多行**（靠 `state` 与查询逻辑取有效行）。

#### 8.1.8 `fs_dynamic` —— 用户动态

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 用户动态编号 |
| `type` | varchar(32) | NULL | | 类型（写文章、评论、点赞、关注等，取自 `DynamicTypeEnum`） |
| `user_id` | bigint | NULL | | 发起人 |
| `object_id` | varchar(32) | NULL | | 操作的对象 ID（文章 id、用户 id 等） |
| `comment_id` | int | NULL | | 评论 id |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

`AUTO_INCREMENT = 15137`（历史数据量最大的表），种子数据为空。

#### 8.1.9 `fs_user_level` —— 用户等级与积分

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 用户等级编号 |
| `user_id` | bigint | NULL | | 用户 id |
| `level` | varchar(32) | `'Lv1'` | | 等级（Lv1~Lv6） |
| `points` | int | 0 | | 积分 |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

`AUTO_INCREMENT = 1014`，种子数据 **987 行**。

#### 8.1.10 `fs_resource_navigate` —— 资源导航

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 资源导航编号 |
| `resource_name` | varchar(64) | NULL | | 资源名字 |
| `logo` | varchar(120) | NULL | | logo（图片 URL） |
| `category` | varchar(64) | NULL | | 类别 |
| `desc` | varchar(255) | NULL | | 描述 |
| `link` | varchar(255) | NULL | | 链接 |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除 |
| `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

`AUTO_INCREMENT = 95`，种子数据 **10 行**（如 `everypixel`，类别「图片」）。

#### 8.1.11 `fs_slideshow` —— 轮播图

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 轮播图编号 |
| `name` | varchar(255) | NULL | | 名称 |
| `image` | varchar(255) | NULL | | 轮播图 |
| `jump_address` | varchar(255) | NULL | | 跳转地址 |
| `desc` | varchar(255) | NULL | | 描述 |
| `state` | tinyint(1) | 1 | | 状态（0 禁用，1 启用） |
| `is_deleted` | tinyint(1) | NULL | | 逻辑删除 |
| `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

`AUTO_INCREMENT = 6`，种子数据 **5 行**。

#### 8.1.12 `fs_album` —— 相册（功能未启用）

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 相册编号 |
| `pre_id` | int | NULL | | 前置相册 id |
| `name` | varchar(100) | NULL | | 相册名称 |
| `desc` | varchar(255) | NULL | | 说明 |
| `photo` | varchar(255) | NULL | | 照片 |
| `state` | tinyint(1) | 1 | | 状态（0 禁用，1 启用） |
| `is_deleted` / `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

无种子数据，**代码中无对应 entity/mapper，属预留表**。

#### 8.1.13 `fs_course` —— 课程（功能未启用）

| 列 | 类型 | 默认 | 键 | 注释 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 课程编号 |
| `title` | varchar(64) | NULL | | 课程标题 |
| `content` | varchar(255) | NULL | | 课程内容（视频） |
| `desc` | varchar(255) | NULL | | 课程描述 |
| `cover` | varchar(120) | NULL | | 封面 |
| `level` | varchar(64) | NULL | | 级别（初级/中级/困难） |
| `classify` | varchar(64) | NULL | | 专栏分类（动漫/游戏…） |
| `is_deleted` / `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

`AUTO_INCREMENT = 1`，无种子数据，**同样无对应代码，属预留表**。

> **`fs_album` 与 `fs_course` 是唯二「有表无码」的表**，可以安全地视为历史预留。

### 8.2 `ns_auth` 鉴权库（4 张表）

#### 8.2.1 `ns_user` —— 用户（**主用户表**）

| 列 | 类型 | 默认 | 键 | 说明 |
|----|------|------|----|------|
| `id` | bigint | AUTO_INCREMENT | PK | 用户 id |
| `name` | varchar(50) | NULL | **UNIQUE `uk_name`** | 用户名 |
| `password` | varchar(64) | NULL | | `SHA256(salt + 明文)` 的十六进制 |
| `salt` | varchar(32) | NULL | | 盐（随机 16 位 hex） |
| `gender` | tinyint | NULL | | 性别 |
| `birthday` | varchar(20) | NULL | | 生日 |
| `phone` | varchar(20) | NULL | | 手机 |
| `email` | varchar(100) | NULL | | 邮箱 |
| `picture` | varchar(500) | NULL | | 头像 |
| `position` | varchar(100) | NULL | | 职位 |
| `company` | varchar(100) | NULL | | 公司 |
| `home_page` | varchar(200) | NULL | | 个人主页 |
| `intro` | varchar(500) | NULL | | 简介 |
| `org_id` | int | NULL | | 组织 id |
| `state` | tinyint(1) | 1 | | 状态（1 启用） |
| `auth_id` | varchar(100) | NULL | | 第三方认证 id |
| `auth_source` | varchar(50) | NULL | | 第三方认证来源 |
| **`is_admin`** | tinyint(1) | **0** | | **是否管理员（1=是）** |
| `create_time` / `update_time` | datetime | NULL | | 时间 |

**种子数据（超管）**：

```sql
INSERT INTO ns_user (id, name, password, salt, gender, state, org_id, is_admin, ...)
VALUES (1, 'admin',
        '5514b67fb72216fdd5de7666303225b8f0ac1e9c88612247a169042f329e25bf',
        'a1b2c3d4e5f6a7b8', 0, 1, 1, 1, NOW(), NOW());
```

| 项 | 值 |
|----|-----|
| 账号 | `admin` |
| 密码 | `123456`（**登录后请立即修改**） |
| 盐 | `a1b2c3d4e5f6a7b8`（固定） |
| 摘要 | `SHA256('a1b2c3d4e5f6a7b8' + '123456')` |

> ⚠️ **业务库的表不存用户**：`fs_article.create_user`、`fs_like.like_user`、
> `fs_follow.from_user` 等字段的值都指向 `ns_user.id`，但**跨库无外键**。

#### 8.2.2 `ns_notify` —— 通知内容

| 列 | 类型 | 默认 | 键 | 说明 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 通知 id |
| `project_id` | int | NULL | | 项目 id |
| `message` | varchar(1000) | NULL | | 通知内容 |
| `type` | tinyint | NULL | | 类型 |
| `is_deleted` | tinyint(1) | 0 | | 逻辑删除 |

#### 8.2.3 `ns_notify_user` —— 用户通知状态（已读/未读）

| 列 | 类型 | 默认 | 键 | 说明 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 主键 |
| `type` | tinyint | NULL | | 类型（对应通知角标的 system / task 分类） |
| `notify_id` | int | NULL | | 通知 id → `ns_notify.id` |
| `user_id` | bigint | NULL | **KEY `idx_user`** | 用户 id → `ns_user.id` |
| `is_read` | tinyint(1) | 0 | | 是否已读 |
| `is_deleted` | tinyint(1) | 0 | | 逻辑删除 |
| `create_user` / `update_user` / `create_time` / `update_time` | — | NULL | | 审计 |

#### 8.2.4 `ns_visit` —— 访问记录（**访客数来源**）

| 列 | 类型 | 默认 | 键 | 说明 |
|----|------|------|----|------|
| `id` | int | AUTO_INCREMENT | PK | 主键 |
| `project_id` | int | NULL | | 项目 id |
| `ip` | varchar(50) | NULL | **KEY `idx_ip`** | 访客 IP（去重键） |
| `country` / `province` / `city` | varchar(50) | NULL | | IP 归属地 |
| `host_name` | varchar(100) | NULL | | 主机名 |
| `os` | varchar(50) | NULL | | 操作系统 |
| `count` | int | 1 | | 计数 |
| `day` | varchar(20) | NULL | | 日期 |
| `title` | varchar(50) | NULL | | 标题 |
| `create_time` | datetime | NULL | | 时间 |

> 统计口径见 [5.5](#55-访客数统计口径重要)：**按 IP 30 分钟去重后 COUNT(\*)**，
> 是时间片去重的独立访客口径，不是 PV，也不是严格自然日 UV。

### 8.3 实体关系（逻辑）

```
                    ns_auth.ns_user  (用户主体，is_admin)
                            │  1
        ┌───────────────────┼───────────────────┬──────────────┐
        │ N                 │ N                 │ N            │ N
   fs_article          fs_comment          fs_follow      fs_user_level
   (create_user)      (comment_user)     (from/to_user)     (user_id)
        │ 1                 │ N                 │
        │                   │                   │ N
        │ N                 │ 1                 ▼
   fs_article_label    fs_comment_like     (关注对象同样是 ns_user)
   (article_id/label_id)  (comment_id/like_user)
        │ N                 │
        ▼ 1                 ▼ 1
     fs_label           fs_comment
                        (自关联 pre_id → 多级回复)

   fs_like (article_id → fs_article.id, like_user → ns_user.id)
   fs_dynamic (user_id → ns_user.id, object_id → 多态, comment_id → fs_comment.id)
   fs_slideshow / fs_resource_navigate / fs_album / fs_course  (独立字典/配置表)

   ns_notify 1 ──N ns_notify_user (notify_id, user_id → ns_user.id)
   ns_visit  (独立访问日志，按 ip 去重统计)
```

**所有关联均为逻辑关联，无数据库外键约束。**

---

## 九、小罗Bot AI 服务（MultimodalRAG）

### 9.1 定位

`MultimodalRAG` 由原「MultimodalRAG 多模态知识库问答系统」改造而来，
改造后是**开罗论坛内置的 AI 搜索引擎 Agent「小罗Bot」**：
多智能体协作 + 多模态 RAG，**先在论坛里找答案，论坛里没有（且用户允许）时再联网找**。

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
  ├── Agent 层：agent/        多智能体图（LangGraph）
  ├── 检索层：milvus_db/      多模态混合检索（Milvus Lite）
  ├── 索引层：ingestion/      论坛内容接入 + 分块 + 向量化
  └── 外部依赖：DashScope（多模态嵌入）/ DeepSeek（对话）/ 智谱（联网搜索）
```

### 9.2 六个智能体

| 智能体 | 职责 | 产出 |
|--------|------|------|
| **调度** `supervisor` | 用大模型规划本轮要跑哪些智能体，并按上游结论自适应改计划 | `plan` |
| **多模态理解** `vision` | 读懂用户上传的图片，产出可检索关键词与可直接回答的部分 | `vision_note` |
| **论坛检索** `forum` | 改写检索式 → 多模态混合检索 → **判定论坛里到底有没有** | `forum_hits`、`forum_sufficient` |
| **联网搜索** `web` | 论坛不足且用户开启开关时，改写搜索词 → 智谱搜索 → 整理材料 | `web_results` |
| **答案合成** `compose` | 把材料写成带来源说明的 Markdown，**流式**输出 | `answer` |
| **质量评估** `evaluate` | 规则层 + 模型层双层打分，不通过则触发补搜/重写（各限一次） | `answer_score` |

图入口有 `prepare` 节点，每轮清空 `plan` / `agent_status` / `citations` 等**单轮级字段**，
同时保留 `messages` 里的多轮历史——解决「同一会话追问时复读上一轮」的状态残留问题。

### 9.3 多模态 RAG 的关键设计

**图文共用一个向量空间**：所有内容（文章正文、评论、资源描述、标签说明、图片描述、
PDF 分块、上传的文档附件）都送同一支多模态嵌入模型
（`multimodal-embedding-v1`，1024 维，输出已 L2 归一化），因此：

- 文本能搜到图片（「有没有讲 Flink 架构的图」）；
- 图片能搜到文本与图片（用户直接传截图问「这个报错怎么解决」）。

代价是文本检索质量不如纯文本嵌入模型、且不能换模型（换了就得全量重建），
但对「以图搜图是刚需」的场景是划算的。

**「论坛里到底有没有」必须显式判定**（需求要求「论坛内得不到相关内容才联网」），做成两层：

1. **主判据（模型层）**：把命中片段交给大模型，回答 `{sufficient, score, reason}`，
   提示词里明确「只沾边不算能回答」；
2. **兜底判据（向量层）**：稠密余弦相似度与阈值 `forum_relevance_threshold`（默认 0.70）比较。
   实测相关文本 0.78~0.93、无关 0.44~0.60，阈值取在中间。

只有判定为「不足」时才会走联网。

### 9.4 论坛数据源三级降级

| 优先级 | 数据源 | 场景 |
|--------|--------|------|
| 1 | `RestForumSource` → bbs-rest 网关 | 正常开发/生产：不复制业务 SQL，字段跟着 DTO 走 |
| 2 | `MysqlForumSource` → `open_bbs` 只读 | 网关或 Dubbo/ZooKeeper 没起来时建库 |
| 3 | `LocalSnapshotSource` → `forum_snapshot/` | 完全离线 / 写测试用例 |

三者产出同一个 `ForumDocument`，后续分块/向量化/入库完全一致。

网关中用到的 5 个导出接口（都是 `@NoNeedLogin`）：

| 用途 | 接口 |
|------|------|
| 文章列表 | `GET /bbs/article/getList` |
| 文章详情 | `GET /bbs/article/getById` |
| 文章评论 | `GET /bbs/comment/getCommentByArticleId` |
| 标签列表 | `GET /bbs/label/getList` |
| 资源导航 | `GET /bbs/resource/getList` |

### 9.5 向量库

Milvus Lite（嵌入式单进程，数据文件 `milvus_local.db`），三个集合：

| 集合 | 用途 |
|------|------|
| `t_knowledge_collection` | ★ 统一多模态知识库（论坛内容 + PDF + 上传附件） |
| `t_context_collection` | 长期记忆（历次回答，跨会话召回） |
| `t_doc_collection` | 旧版 PDF 知识库（保留兼容） |

**幂等**：每条知识的主键是 `chunk_id`（如 `article:43#2`、`article:43#img0`），
写入前先按主键删除，所以重复同步不会产生重复数据。

**损坏防护**（记录了一次真实事故）：

- Milvus Lite 写入先进 WAL 再合并成 parquet。进程被**强杀**会损坏正在写的 WAL，
  下次打开时 Milvus 丢弃它，而 manifest 已推进到新版本 —— 表现为「整个集合查询为 0 条」，
  但 `data/*.parquet` 里的数据其实还在。
- 已做两道防护：`upsert_rows()` 写完立即 `flush()`；FastAPI 的 `shutdown` 事件再落一次盘。
  **所以停服务请用一次 Ctrl+C，不要直接强杀进程。**
- `knowledge_stats()` 不再静默吞异常：查询失败返回 `ok:false` + `error`，
  页面显示黄色告警而不是误导性的 `0`。
- 恢复顺序：先备份 `milvus_local.db` → 再 `.\start_kb_sync.ps1` 重新同步。
  **知识库的真相来源是论坛数据库，向量库只是可重建的派生数据。**

### 9.6 目录结构

```
MultimodalRAG/
├── config.yml                    ★ 唯一配置源（API Key / 端口 / 检索参数 / 开关）
├── requirements.txt
├── README.md                     详细使用文档
├── start_bot.ps1                 ★ 启动 AI 服务（FastAPI）
├── start_kb_sync.ps1             ★ 同步论坛内容到知识库
├── start_chat.ps1                启动 Gradio 调试界面
├── start_knowledge.ps1           启动 PDF 知识库构建界面
│
├── agent/                        ★ 多智能体核心（graph/supervisor/forum_agent/
│   │                               web_agent/vision_agent/composer/evaluator/
│   │                               session/state/events/prompts/llm_utils/cli）
├── server/                       ★ FastAPI 服务层（app.py / schemas.py）
├── ingestion/                    ★ 论坛知识接入（forum_source / forum_ingest /
│   │                               attachment_ingest / cli）
├── milvus_db/                    集合定义 + 多模态混合检索器
├── utils/                        配置、嵌入、日志、图片理解
├── tools/dev_gateway.py          本地联调网关桩（模拟 bbs-rest）
├── dots_ocr/                     PDF/图片解析（DotsOCR）
├── splitters/                    Markdown 四层分块器
├── evaluate/                     RAGAS 评估器封装
├── graph/                        共享 LangGraph 组件
├── output/                       解析产物（含 attachments/ 上传的附件原文件）
├── forum_snapshot/               离线数据源目录（放 md/txt/json）
├── milvus_local.db               Milvus Lite 数据文件
├── logs/                         日志
└── 项目文档/                      设计与架构文档（含小罗Bot-架构与设计.md 等）
```

### 9.7 页面上的知识库管理

小罗Bot 页面（`/bot`）的「知识库」面板支持管理员直接拖拽上传文档，
不必再去服务器执行脚本：

```
页面拖拽文件 → /api/bbs/ai/kb/upload（multipart）
            → AI 服务落盘 → 后台解析 → 分块 → 向量化 → 写入 t_knowledge_collection
            → 返回 taskId，前端轮询 /kb/upload/status/{taskId} 显示进度
```

| 格式 | 解析方式 |
|------|---------|
| `.pdf` | PyMuPDF 逐页抽正文（不需要 GPU/OCR） |
| `.txt` / `.md` | 直接读取 |
| `.json` | 展开成 `key.path: value` 便于按字段名检索 |
| `.csv` | 逐行转成「列名: 值」；只取前 `csv_max_rows` 行 |
| `.docx` | python-docx 抽段落（标题转成 `#`）+ 表格 |
| `.png/.jpg/.jpeg/.webp/.bmp` | 多模态模型生成描述，图片与描述一起向量化 |

要点：

- **扫描件 PDF 会明确报错**，不会静默入库（当前环境 DotsOCR 权重不存在、未部署 vLLM）；
- **重复上传同一文件不会重复入库**：主键是内容摘要 `attachment:<sha1前16位>`，重复上传是覆盖；
- 原文件落在 `output/attachments/`，删除附件时连同它的全部知识块与原文件一起清理。

### 9.8 本地联调网关桩

`bbs-rest` 依赖一整套中间件。只想把页面跑起来时，可用内置的**网关桩**
（同路径、同响应信封，直接把请求转给 AI 服务）：

```powershell
python tools\dev_gateway.py      # 监听 7010，前端配置不用改
```

链路变成 `vue-ui → 网关桩:7010 → AI 服务:7861`，前端代码一行都不用动。
**它不做鉴权，只用于本地联调。**

---

## 十、部署与启动

### 10.1 前置准备

**必须自行准备的基础设施**（默认地址已写入各 `application.yml`）：

| 组件 | 默认地址 | 说明 |
|------|---------|------|
| ZooKeeper | `127.0.0.1:2181` | **4 个模块必须指向同一台** |
| MySQL | `127.0.0.1:3306` | 两个库：`open_bbs`（论坛）+ `ns_auth`（鉴权） |
| Redis | `127.0.0.1:6379`（无密码） | SSO token / 验证码 |

> ⚠️ **关键提醒**：原工程 `bbs-rest` / `bbs-user` / `bbs-article` 的配置曾指向作者服务器
> （ZK `47.109.0.224:2181`、Redis `8.137.106.178:6222`）。
> 若继续连作者的 ZK，会与作者仍在运行的 ns-manage Provider 发生**服务发现冲突**。
> **务必全部改成你自己的 ZK / Redis。**

### 10.2 建库

```bash
mysql -uroot -p < springboot/db备份/open_bbs.sql          # 论坛业务库（13 张表）
mysql -uroot -p < springboot/bbs-auth/db/ns_auth.sql      # 鉴权库（4 张表，必导）
```

### 10.3 后端构建与启动

```bash
# 在 springboot 根目录
mvn clean install -DskipTests
```

**启动顺序**（先中间件，再 Provider，最后网关）：

```bash
# ① 启动 ZooKeeper / MySQL / Redis

# ② 鉴权服务（先启动）
java -jar bbs-auth/target/bbs-auth.jar

# ③ 业务 Provider
java -jar bbs-user/bbs-user-service/target/bbs-user-service.jar
java -jar bbs-article/bbs-article-service/target/bbs-article-service.jar

# ④ REST 网关
java -jar bbs-rest/target/bbs-rest.jar
```

> `dubbo.consumer.check=false` 已开启，Provider 未就绪也能启动；
> 但走到登录/鉴权/上传时，对应 Provider 必须已注册，否则报「No provider」。

**各进程端口**：

| 服务 | HTTP | Dubbo |
|------|------|-------|
| `bbs-rest` | 7010（context-path `/api`） | 22001（消费者，不注册） |
| `bbs-article-service` | 7011 | 22002 |
| `bbs-user-service` | 7013 | 22003 |
| `bbs-auth` | 7014 | 22004 |

### 10.4 前端启动

```bash
cd vue-ui
npm install
npm run serve        # http://localhost:8082
```

生产构建：

```bash
npm run build        # 产物在 dist/，JS/CSS 同时输出 .gz
```

> 路由用 `history` 模式，**生产环境需在 nginx 配置**
> `try_files $uri $uri/ /index.html;`，否则刷新非根路径会 404。

### 10.5 AI 服务启动

```powershell
cd MultimodalRAG
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 编辑 config.yml 填入 API Key

.\start_kb_sync.ps1          # ① 先建知识库（不建则论坛检索永远为空）
.\start_bot.ps1              # ② 启动 AI 服务（:7861）
```

常见开关：

| 目的 | 命令 |
|------|------|
| 全量同步（含图片理解） | `.\start_kb_sync.ps1` |
| 跳过图片理解（快很多） | `.\start_kb_sync.ps1 -NoImages` |
| 只看数据源与知识库状态 | `.\start_kb_sync.ps1 -Status` |
| 命令行问答 | `python -m agent.cli "论坛里有哪些标签？" --web` |
| 交互式多轮问答 | `python -m agent.cli -i` |
| 查看知识库数据 | `python check_milvus.py`（**需先停 AI 服务**，Milvus Lite 单进程独占锁） |
| 清理数据库 | `python clear_milvus.py` |
| 离线 RAG 评估 | `python evaluate_full.py` |
| 本地联调网关桩 | `python tools\dev_gateway.py` |

### 10.6 完整启动检查清单

```
□ ZooKeeper 已启动并监听 2181
□ MySQL 已启动，open_bbs 与 ns_auth 两个库已导入
□ Redis 已启动并监听 6379
□ 四个模块的 application.yml 中 dubbo.registry.address 指向同一 ZK
□ 各模块 MySQL 账号密码已改成自己的
□ 已按顺序启动：auth → user-service / article-service → bbs-rest
□ 访问 http://127.0.0.1:7010/api/doc.html 能看到 Knife4j 文档
□ 前端 npm run serve 后 http://localhost:8082 能打开首页
□ 用 admin / 123456 能登录，且能看到管理入口
□ （可选）AI 服务 :7861/health 返回 status: ok
□ （可选）知识库条目数不为 0
```

### 10.7 跨主机拆分指南

若要把微服务拆分/迁移到其它主机，核心结论是：

1. **本项目已具备拆分基础**——每个 `*-service` 本身就是可独立打包、独立运行的
   Spring Boot 应用（有自己的 `main` 启动类、`application.yml`、
   `spring-boot-maven-plugin` 打包、`assembly.xml` 打成 zip）。
   因此「迁移到其它主机」主要不是改代码，而是**改配置 + 解决依赖共享**。
2. **真正要动的只有一件事——facade 契约的共享方式**。Dubbo 靠「接口全限定名 + 版本」
   匹配消费者与提供者，所以**消费者和提供者必须拿到完全相同的 facade 接口类**。
   单机单仓库时靠 Maven 本地 reactor 直接依赖；跨主机后必须把 facade 发布到 Maven 私服共享。

**代码归属**：

| 类别 | 模块 | 说明 |
|------|------|------|
| **带走**（跟随服务部署） | `bbs-user-service` + `bbs-user-persistence`；`bbs-article-service` + `bbs-article-persistence`；`bbs-auth` | persistence 是 service 的私有依赖，随服务走，**不单独部署** |
| **共享**（所有主机同一份） | `bbs-user-facade`、`bbs-article-facade`、`bbs-common`、`nansheng-common`（第三方） | facade 与 common 需 `mvn deploy` 到私服并**锁定相同版本号** |
| **保留原处** | `bbs-rest`（统一对外入口）、父 POM `ns-bbs`（构建根） | 彻底拆成多仓库时需为每个服务单独建父 POM |

**必改配置**：

| 配置项 | 当前值 | 改法 |
|--------|--------|------|
| `dubbo.registry.address` | `zookeeper://127.0.0.1:2181` | 所有主机都能访问的 ZK 地址（**四个服务必须一致**） |
| `spring.datasource.url` | `jdbc:mysql://127.0.0.1:3306/...` | MySQL 所在主机 |
| `spring.data.redis.host` | `127.0.0.1` | Redis 所在主机 |
| `auth.file-url-prefix` | `http://127.0.0.1:7014/static/` | auth 服务的对外地址 |
| `ai.agent.base-url` | `http://127.0.0.1:7861` | AI 服务所在主机 |
| `dubbo.protocol.port` | 22001~22004 | 跨主机可**保持不变**（IP 不同即可区分），注意放行防火墙 |

**需要注意的决策点**：

- **共享库 vs 拆库**：当前 `open_bbs` 被 `article-service` 和 `user-service` **共用一个 MySQL 库**。
  拆到两台主机后，要么保留共享 MySQL 实例远程连接，要么按域拆库
  （用户表归 user、文章表归 article），但需同步改动 mapper 与 SQL，工作量较大。
- **facade 版本治理**：引入私服后，`*-facade`、`bbs-common` 需锁版本，避免接口漂移。
- **双向 RPC 的耦合**：`article` ↔ `user` 双向调用意味着两套服务必须同时在线并连同一 ZK。

**最小拆分步骤（以拆出 user 服务为例）**：

1. 把 `bbs-user-facade`、`bbs-common`（及依赖的 `nansheng-common`）发布到 Maven 私服，锁定版本。
2. 目标主机上 `mvn package` 打包 `bbs-user-service`（会连同 persistence、facade、common 打进 lib）。
3. 修改目标主机的 `application.yml`：ZK / MySQL / Redis 指向正确主机。
4. 原主机 `bbs-rest`、`bbs-article-service` 的 `dubbo.registry.address` 指向同一 ZK，并更新 facade 依赖版本。
5. 依次启动 ZooKeeper → MySQL/Redis → auth → article-service / user-service → bbs-rest，验证接口可通。

---

## 十一、配置项速查

### 11.1 后端四个 `application.yml`

| 配置项 | bbs-rest | bbs-article | bbs-user | bbs-auth |
|--------|----------|-------------|----------|----------|
| `server.port` | 7010 | 7011 | 7013 | 7014 |
| `server.servlet.context-path` | `/api` | — | — | — |
| `spring.application.name` | `ns-bbs-rest` | `ns-bbs-article` | `ns-bbs-user` | `ns-bbs-auth` |
| `dubbo.protocol.port` | 22001 | 22002 | 22003 | 22004 |
| `dubbo.registry.address` | `zookeeper://127.0.0.1:2181` | 同 | 同 | 同 |
| 数据库 | — | `open_bbs` | `open_bbs` | `ns_auth` |
| Redis | `127.0.0.1:6379` | `127.0.0.1:6379` | `127.0.0.1:6379` | `127.0.0.1:6379` |
| MongoDB | — | `mongodb://127.0.0.1:27017/open_bbs`（遗留） | — | — |
| `mybatis.mapper-locations` | — | `classpath*:mybatis/mappers/*.xml` | 同 | 同 |
| `spring.main.allow-circular-references` | — | — | `true` | `true` |

**bbs-rest 独有配置**：

```yaml
spring.servlet.multipart:
  max-file-size: 100MB
  max-request-size: 1000MB
interceptor.monitor.status: true        # 请求监控开关
swagger.show: true                      # API 文档开关
file.source.length: 5242880             # 上传源文件上限 5MB
ai.agent:
  enabled: true
  base-url: http://127.0.0.1:7861
  connect-timeout: 5000                 # 5 秒
  read-timeout: 180000                  # 180 秒（Agent 一轮含规划+检索+联网+生成）
  sync-timeout: 1800000                 # 30 分钟（知识库全量同步）
  upload-max-bytes: 20971520            # 20 MB
```

**bbs-auth 独有配置**：

```yaml
auth:
  file-storage-path: ./uploads                    # 本地存储目录
  file-url-prefix: http://127.0.0.1:7014/static/  # 对外访问前缀
  sms:                                            # 阿里云短信（可选，留空=仅打日志）
    access-key-id:
    access-key-secret:
    sign-name:
    template-code:
```

**Druid 连接池（user / article / auth）**：`initial-size: 5`、`min-idle: 5`、`max-active: 20`、
`max-wait: 60000`、`time-between-eviction-runs-millis: 60000`、
`validation-query: SELECT 1 FROM DUAL`、`filters: wall,state`、
慢 SQL 阈值 `slow-sql-millis: 2000`。

### 11.2 前端关键配置

| 配置 | 值 | 位置 |
|------|-----|------|
| devServer 端口 | `8082` | `vue.config.js` |
| 代理前缀 | `/api` → `http://localhost:7010` | `vue.config.js` |
| axios 超时 | `15000` ms | `src/service/axios.js` |
| 上传超时（AI 附件） | `300000` ms | `src/service/aiBotService.js` |
| 资源目录 | `static` | `vue.config.js` |
| 生产 source map | 关闭 | `vue.config.js` |
| gzip 阈值 | 10240 B | `vue.config.js` |
| 主题色候选 | `#D4AF37` / `#C0C0C0` / `#000000` | `src/store/index.js` |
| 默认主题色 | `#D4AF37`（镀金） | `src/store/index.js` |

### 11.3 AI 服务关键配置（`config.yml`）

| 配置段 | 关键项 | 默认值 |
|--------|--------|--------|
| `app` | `bot_name` / `welcome` | 「小罗Bot」/ 欢迎语 |
| `llm.openai` | 对话模型 | `deepseek-flash` @ `api.deepseek.com`，`temperature: 1.3` |
| `llm.multimodal` | 多模态模型 + DashScope Key | `qwen3.5-plus-2026-04-20` |
| `llm.embedding` | 文本嵌入（RAGAS 评估用） | `text-embedding-v4`，1024 维 |
| `llm.zhipu` | 联网搜索 Key | — |
| `llm.dashscope` | 多模态嵌入 | `multimodal-embedding-v1`，`rpm_limit: 120` |
| `milvus` | 集合与维度 | `t_knowledge_collection` / `t_context_collection`，`dim: 1024`，`tokenizer: jieba` |
| `forum` | 论坛接入 | `base_url: http://127.0.0.1:7010/api`，`page_size: 50`，`max_pages: 40` |
| `forum.mysql` | 兜底数据源 | `127.0.0.1:3306/open_bbs` |
| `forum` | 分块 | `chunk_size: 700`，`chunk_overlap: 80`，`max_images_per_article: 3` |
| `web_search` | 联网搜索 | `enabled_by_default: false`，`provider: zhipu`，`max_results: 8` |
| `attachment` | 附件上传 | `admin_only: true`，`max_size_mb: 20`，`pdf_max_pages: 200`，`csv_max_rows: 500` |
| `agent` | 调度 | `max_handoffs: 9`，`max_web_queries: 2`，`max_forum_queries: 3` |
| `agent` | 判定阈值 | `forum_relevance_threshold: 0.70`，`answer_score_threshold: 0.55` |
| `agent` | 其他 | `enable_evaluator: true`，`history_window: 8`，`memory_top_k: 3`，`max_answer_tokens: 2048` |
| `retrieval` | 混合检索 | `agent_top_k: 5`，`agent_search_limit: 20`，`sparse_weight: 1.0`，`dense_weight: 1.0` |
| `server` | HTTP 服务 | `host: 127.0.0.1`，`port: 7861`，`max_sessions: 500`，TTL 7200s |
| `logging` | 日志 | `level: INFO`，`rotation: 10 MB`，`retention: 20` |

> ⚠️ **`config.yml` 是唯一配置源**，代码不读环境变量、不读 `.env`。
> 当前文件中**已填入真实 API Key**，属于敏感信息（见 12.1）。

---

## 十二、安全与已知问题

### 12.1 敏感信息硬编码（**最高优先级**）

仓库中多处存在明文凭据，且 `config.yml` 已被纳入版本控制：

| 位置 | 内容 | 风险 |
|------|------|------|
| `MultimodalRAG/config.yml` | DeepSeek Key、DashScope Key（**出现两次**）、智谱 Key | **真实可用的付费 API Key 泄露**，会被盗刷 |
| `springboot/bbs-user/.../application.yml` | MySQL `root` / `441616300g` | 数据库口令泄露 |
| `springboot/bbs-article/.../application.yml` | 同上（需确认） | 同上 |
| `springboot/bbs-auth/.../application.yml` | MySQL `root` / `441616300g` | 同上 |
| `MultimodalRAG/config.yml` | `forum.mysql.password: 441616300g` | 同上 |
| `bbs-auth/db/ns_auth.sql` | 超管 `admin` / `123456` | 默认弱口令 |

**整改建议**：

1. **立即轮换全部已泄露的 Key 与数据库口令**（这是最紧急的一步，改代码之前就要做）；
2. 把真实凭据移到环境变量或外部配置（Spring Boot 支持 `${DB_PASSWORD:}` 占位；
   AI 侧需改造 `utils/config.py` 以支持环境变量插值）；
3. 把 `config.yml`、`application-local.yml` 加入 `.gitignore`，仓库内只保留 `*.example` 模板；
4. 生产环境修改超管默认密码；
5. 为 MySQL 建专用低权限账号（业务只需 CRUD，AI 兜底数据源只需只读）。

### 12.2 `fastjson 1.2.71` 版本风险

父 POM 使用 `com.alibaba:fastjson:1.2.71`。该系列历史上有多个反序列化远程代码执行漏洞
（1.2.80 之前需开启 `safeMode` 或升级）。当前用法是本地对象序列化
（`UrlAccessCheckInterceptor` 里的 `JSON.toJSONString`），风险可控，
但建议升级到 `fastjson2` 或至少启用 `ParserConfig.getGlobalInstance().setSafeMode(true)`。

### 12.3 前端技术债

| 项 | 问题 | 规避方式 |
|----|------|---------|
| **Less 2.7.2 + `calc()`** | Less 会去计算 `calc()` 里的表达式，`height: calc(100vh - 128px)` 被编译成 `calc(-28vh)`，高度直接失效 | 三种规避写法，均已在代码中使用：① 转义 `~"calc(100% - 56px)"`（`BotMessage.vue`）；② 干脆不用 calc，改纯 CSS flex 分配（`BotChat.vue`）；③ 放进 `<style>` 之外的**内联 `:style`**，由浏览器处理而非 Less（`LabelContent.vue`、`ResourceContent.vue`）。纯 CSS 的 `BotIndex.vue` 不受影响 |
| **axios 0.21** | 会把响应整体缓冲，无法处理 SSE；且拦截器要求响应体是 `{code:0,...}` JSON | 流式对话改用原生 `fetch` + `ReadableStream`（见 `aiBotService.chatStream`） |
| **antd `default` 预设色** | `:color="x ? 'green' : 'default'"` 会让 antd 走到 `color && !isPresetColor(color)` 分支并加上 `.ant-tag-has-color`，该类文字色是 `#fff` —— 浅色底上「白字白底」标签直接看不见 | 不可用状态传 `undefined`（或不传 `color`） |
| **`a-config-provider` 单子节点** | 它只渲染默认插槽的第一个子节点（`filterEmpty($slots.default)[0]`），背景与 `#app` 必须包在同一根节点里，否则 `#app` 整个应用被丢弃、只剩背景板 | 用 `.app-root` 统一包裹 |
| **路由无守卫** | `router/index.js` 未配置全局守卫，权限靠接口信封与组件内 `v-if` | 涉及权限的新页面需自行判断 `store.state.isManage` |
| **无 ESLint/Prettier 校验流程** | 仅有一个 `.prettierrc`，`package.json` 无 lint script | 提交前手工格式化 |

### 12.4 后端已知事项

| 项 | 说明 |
|----|------|
| `shiro-spring 3.0.0-alpha-1` | 引入的是 alpha 版本，实际鉴权走自研 SSO + Dubbo，该依赖可能为历史遗留 |
| `MongoConfig` / MongoDB 依赖 | 保留但功能已不启用（正文在 MySQL）。若确认无用可移除依赖减小包体 |
| `fs_album` / `fs_course` | 有表无码，属预留 |
| `dubbo.consumer.check=false` | 提升启动容错，但会把「Provider 未就绪」推迟到运行时暴露，上线时需关注 |
| 无外键约束 | 业务库与鉴权库跨库关联全靠应用层，脏数据排查难度较高 |
| `maven-surefire-plugin` 配置 `skipTests=true` | 默认跳过测试，CI 中需显式 `-DskipTests=false` 才能真正跑测试 |

### 12.5 AI 服务的运维注意点

| 项 | 说明 |
|----|------|
| **不要强杀进程** | Milvus Lite 的 WAL 会被写坏，可能导致整个集合查询为 0 条。请用一次 Ctrl+C |
| **Milvus Lite 单进程独占** | AI 服务运行时 `check_milvus.py` 会报 `Open local milvus failed`；反之亦然 |
| **一轮问答 10~20 秒** | 含规划 + 检索 + 判定 + 生成 + 评估，属正常范围。触发联网时更久 |
| 想更快 | `config.yml → agent.enable_evaluator: false` 可省一次 LLM 调用（快 2~3 秒） |
| 联网是兜底通道 | 只有论坛检索判定为「不足」时才会真正触发；开关打开≠一定联网 |
| 扫描件 PDF | 当前环境无 OCR，会明确报错而非静默入库 |
| 知识库为空 | 页面「一问就答不上来」时先确认知识库条目数，其次确认问题与文档用词是否过于不同 |

---

## 十三、开发与维护指南

### 13.1 新增一个 REST 接口的标准流程

```
① 在 bbs-article-facade / bbs-user-facade 里定义或复用接口方法（契约先行）
② 在对应 *-persistence 增改 entity / Mapper / XML
③ 在对应 *-service 的 impl 实现（必要时加 MapStruct 转换）
④ 在 bbs-rest 的 Controller 增加 handler，用 @DubboReference 注入 facade
⑤ 需要免登录则加 @NoNeedLogin；需要管理权限则确认路径已在 ADMIN_PATHS 规则内
⑥ 加 @Operation(summary="...")  —— ApiDataInit 会据此构建权限描述写入 Redis
⑦ 前端在 src/service/ 对应文件加函数，组件内调用
```

> **顺序很重要**：契约在 facade，实现在 service，暴露在 rest。
> 跨域改动时，facade 版本必须同步升级并通知所有消费方。

### 13.2 新增数据库表的流程

1. 在对应库（`open_bbs` → 前缀 `fs_`，`ns_auth` → 前缀 `ns_`）建表，**带全列注释**；
2. 更新各 `*-persistence` 的 entity 与 Mapper XML；
3. `generatorConfig.xml` 配的是 MyBatis Generator 逆向工程配置，
   也可用它生成 `Po` 与 `PoExample`（entity 与 Example 成对出现即来源于此）；
4. 更新 `db备份/open_bbs.sql`（或 `bbs-auth/db/ns_auth.sql`）导出，保持建库脚本与代码同步。

### 13.3 新增前端页面的流程

1. `src/components/index/` 下新建页面组件（页面级用**非 scoped** 的根 id 选择器，
   如 `#bot-index .xxx`；叶子组件用 `less + scoped`）；
2. `src/router/index.js` 注册路由（`history` 模式，懒加载 `() => import(...)`）；
3. `src/service/` 下新增或复用 API 函数；
4. 需要中英文则在 `src/i18n/zh/common.js` 与 `en/common.js` 同步加词条，
   用 `this.$store.state.translate("xxx.yyy")` 取值。

### 13.4 本地开发的两条路径

**路径 A：完整环境（推荐用于后端联调）**

```
ZooKeeper + MySQL + Redis  →  bbs-auth  →  user/article service  →  bbs-rest  →  vue-ui
```

**路径 B：只要看前端 / 没有中间件**

```powershell
cd MultimodalRAG
python tools\dev_gateway.py        # 网关桩监听 7010
cd ..\vue-ui
npm run serve                      # :8082
```

链路为 `vue-ui → 网关桩:7010 → AI 服务:7861`，前端配置一行不改。
用网关桩验证管理员视图：

```bash
curl -H "X-Dev-Role: admin" http://127.0.0.1:7010/api/bbs/ai/kb/status
# 或浏览器控制台：document.cookie='devRole=admin;path=/'; 然后刷新
```

### 13.5 修改权限规则的「三处同步」清单

改 AI 知识库相关权限时，**必须同时改三处**，否则会出现「联调通过但上线被拒」或反之：

| # | 位置 | 具体实现 |
|---|------|---------|
| ① | `AiBotController` | `requireAdmin("...")`（6 个接口）+ `kbStatus()` 的非管理员脱敏 |
| ② | `MultimodalRAG/tools/dev_gateway.py` | `ADMIN_ONLY_PATHS` / `ADMIN_ONLY_PREFIXES` / `SANITIZE_FOR_GUEST` |
| ③ | `vue-ui/src/components/bot/BotChat.vue` | `isAdmin` 判定 + 三处 `v-if` |

两个容易漏的点：

- `BotIndex.vue` 的 hero 统计也调 `/kb/status`，所以**脱敏时只摘 `collection`**，
  `total` 与 `bySourceType` 必须保留，否则游客页面上的「知识条目」会变成 0；
- `ADMIN_ONLY_PATHS` 这类模块级常量**不要定义两遍**——后定义的会静默覆盖前面的。
  这个坑真踩过：新增上传接口时下游又出现一份两元素的旧定义，
  结果「游客竟然能上传」，而联调桩看起来一切正常。

### 13.6 排查问题速查

| 现象 | 排查方向 |
|------|---------|
| 启动报 `No provider` | 对应 Provider 未注册：确认 ZK 地址一致、Provider 已启动 |
| 登录接口 500 | `bbs-auth` 未启动，或 `ns_auth` 库未导入 |
| 前端接口全部 302 | 未登录，或 token 过期（TTL 7 天）；确认 Redis 中 `ns:sso:token:{token}` 存在 |
| 上传头像报错 | `bbs-auth` 的 `file-storage-path` 目录不存在或无写权限；确认 `/static/**` 映射 |
| 管理接口 403 / `URL_ACCESS_REFUSED` | 当前用户不是超管，或该路径命中 `ADMIN_PATHS` 黑名单 |
| 页面白屏只剩背景 | `App.vue` 的 `#app` 是否被 `a-config-provider` 丢弃（根节点结构问题） |
| 前端刷新 404 | history 模式，生产 nginx 缺 `try_files` |
| Less 里 `calc()` 失效 | Less 2.7.2 会预先计算 `calc()` 表达式。改用 `~"calc(...)"` 转义、改内联 `:style`、或改用 flex 布局 |
| AI 回答「论坛里没有相关内容」 | 知识库为空，跑 `.\start_kb_sync.ps1` |
| AI 页面报「服务暂不可用」 | AI 服务未启动，确认 `:7861/health` |
| 知识库显示 0 条且有黄色告警 | 统计读取失败（`ok:false`），检查 Milvus Lite 是否被强杀损坏 WAL |
| `check_milvus.py` 打不开库 | AI 服务正持有 Milvus Lite 独占锁，先停服务 |
| `Invalid update`（改 AI 状态字段后） | LangGraph 要求节点返回的键必须在 `agent/state.py` 的 `BotState` 里声明 |

### 13.7 代码规范约定

**后端**

- 分层严格：`facade`（契约/DTO）→ `service`（实现）→ `persistence`（entity/mapper），
  **不允许 persistence 泄漏到 facade**；
- DTO 转换统一用 MapStruct（`*MS` 接口），不手写 setter 拷贝；
- 统一抛 `BusinessException` + `ResponseCode`，由 `GlobalExceptionHandler` 兜底；
- entity 命名 `*Po`，MyBatis Generator 生成的配套条件类为 `*PoExample`，
  手写扩展 Mapper 命名 `*ExMapper`；
- 数据库列 `snake_case`，Java 字段 `camelCase`（`map-underscore-to-camel-case: true`）。

**前端**

- 页面组件放 `components/index/`，可复用业务组件放按域命名的目录（`article/`、`user/`…）；
- 页面级样式用**非 scoped** 根 id 选择器（`#page-index .xxx`），叶子组件用 `less + scoped`；
- 所有 API 调用集中在 `src/service/`，组件内不直接写 `axios`；
- 业务成功判断依赖 axios 拦截器已解包，拿到的 `res` 就是 `{code,desc,data}`，
  业务数据在 `res.data`；
- 主题色一律引用 `var(--theme-color)` 或 `store.state.themeColor`，不硬编码金色。

---

## 附录

### A. 项目文件清单（不含 node_modules / target / .venv）

**根目录**

```
Cairo Forum/
├── springboot/        Java 后端（Maven 多模块，182 个 Java 文件）
├── vue-ui/            Vue 2 前端（73 个 .vue + 24 个 .js）
├── MultimodalRAG/     Python AI 服务
└── Cairo Forum 项目文档.md    ← 本文档
```

**项目自带文档**

| 文件 | 内容 |
|------|------|
| `springboot/说明.txt` | 技术选型与访客数统计口径 |
| `springboot/配置清单.md` | 自托管部署配置清单（基础设施、必改配置、建库、默认账号） |
| `springboot/微服务架构与拆分说明.md` | 微服务划分原理与跨主机拆分指南 |
| `vue-ui/项目说明.txt` | 图片/文字/其它信息的存储策略 |
| `MultimodalRAG/README.md` | AI 服务完整使用文档（528 行） |
| `MultimodalRAG/项目文档/小罗Bot-架构与设计.md` | AI 服务设计决策与踩坑记录 |
| `MultimodalRAG/项目文档/面试项目文档.md` | 项目讲解材料 |
| `MultimodalRAG/项目文档/{graph_rag.png, 存储流程图.png}` | 架构图 |

### B. 端口分配一览

| 端口 | 用途 |
|------|------|
| 2181 | ZooKeeper |
| 3306 | MySQL |
| 6379 | Redis |
| 7010 | bbs-rest HTTP（context-path `/api`） |
| 7011 | bbs-article-service HTTP |
| 7013 | bbs-user-service HTTP |
| 7014 | bbs-auth HTTP（兼 `/static/**` 文件服务） |
| 7860 | 小罗Bot Gradio 调试界面（可选） |
| 7861 | 小罗Bot FastAPI 服务（仅 127.0.0.1） |
| 8082 | vue-ui 开发服务器 |
| 22001 | bbs-rest Dubbo |
| 22002 | bbs-article-service Dubbo |
| 22003 | bbs-user-service Dubbo |
| 22004 | bbs-auth Dubbo |

### C. 常用命令速查

```bash
# ---------- 后端 ----------
mvn clean install -DskipTests                    # 在 springboot/ 下全量构建
mvn -pl bbs-rest -am package -DskipTests         # 只构建 bbs-rest 及其依赖
java -jar bbs-rest/target/bbs-rest.jar           # 启动网关

# ---------- 前端 ----------
npm run serve                                    # 开发服务器 :8082
npm run build                                    # 生产构建

# ---------- 建库 ----------
mysql -uroot -p < springboot/db备份/open_bbs.sql
mysql -uroot -p < springboot/bbs-auth/db/ns_auth.sql

# ---------- AI 服务（PowerShell）----------
.\start_bot.ps1                                  # 启动 AI 服务
.\start_kb_sync.ps1                              # 全量同步知识库
.\start_kb_sync.ps1 -NoImages                    # 跳过图片理解
.\start_kb_sync.ps1 -Status                      # 查看数据源与知识库状态
python -m agent.cli "问题" --web                  # 命令行问答
python -m agent.cli -i                           # 交互式多轮
python check_milvus.py                           # 查看知识库（需先停 AI 服务）
python tools\dev_gateway.py                      # 联调网关桩

# ---------- 验证 ----------
curl http://127.0.0.1:7010/api/doc.html          # Knife4j API 文档
curl http://127.0.0.1:7861/health                # AI 服务健康检查
curl http://127.0.0.1:7861/docs                  # AI 服务交互式文档
```

### D. 术语表

| 术语 | 含义 |
|------|------|
| **facade** | Dubbo 接口契约层，只放接口与 DTO，消费者与提供者都依赖 |
| **persistence** | 数据访问层（entity + mapper + XML），仅被同域 service 依赖 |
| **Po / PoExample** | MyBatis Generator 生成的实体类与查询条件类 |
| **ExMapper** | 手写的扩展 Mapper（补充生成器无法表达的复杂 SQL） |
| **NS_SUPER_ADMIN_ROLE** | 超级管理员角色标识，前端据此显示管理入口 |
| **NS_ORDINARY_ADMIN_ROLE** | 普通管理员角色标识，服务端放行、前端不显示按钮 |
| **NoNeedLogin** | 自定义免登录注解，可标在方法或类上 |
| **统一信封** | `{code, desc, data}` 三段式响应结构 |
| **小罗Bot** | 论坛内置 AI 搜索引擎 Agent（MultimodalRAG 项目） |
| **论坛数据源三级降级** | REST 网关 → 直连 MySQL → 本地快照目录 |
| **chunk_id** | 知识库条目主键（如 `article:43#2`），保证同步幂等 |
| **Milvus Lite** | 嵌入式向量库，单进程独占，数据文件 `milvus_local.db` |

---

*文档基于项目源码与自带文档整理，所有类名、路径、端口、配置值均取自实际代码。*
