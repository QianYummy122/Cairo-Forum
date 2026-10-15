<template>
  <div class="bot-chat">
    <!-- ===== 顶部：小罗Bot 标识 + 能力开关 ===== -->
    <div class="bot-chat-head">
      <div class="bot-chat-title">
        <span class="bot-logo">罗</span>
        <div class="bot-title-text">
          <div class="bot-name">
            小罗Bot
            <a-tag class="bot-version">AI 搜索引擎</a-tag>
          </div>
          <div class="bot-subtitle">
            多智能体协作 · 多模态 RAG · 先查论坛，查不到再联网
          </div>
        </div>
      </div>

      <div class="bot-chat-switches">
        <!-- 联网搜索开关（需求 6：用户可自行选择是否启用） -->
        <a-tooltip :title="webSearchEnabled
            ? '已开启：论坛里查不到相关内容时，小罗Bot 会到互联网上继续找'
            : '已关闭：小罗Bot 只在论坛知识库中检索'">
          <div class="bot-switch" :class="{ 'is-on': webSearchEnabled }" @click="toggleWebSearch">
            <a-icon type="global"/>
            <span>联网搜索</span>
            <a-switch :checked="webSearchEnabled" size="small" @click.native.stop="toggleWebSearch"/>
          </div>
        </a-tooltip>

        <a-tooltip title="清空当前对话（开启新会话）">
          <a-button size="small" type="link" class="bot-btn-link" @click="newSession">
            <a-icon type="plus"/> 新对话
          </a-button>
        </a-tooltip>

        <a-tooltip title="知识库状态与同步">
          <a-button size="small" type="link" class="bot-btn-link" @click="openKnowledge">
            <a-icon type="database"/> 知识库
          </a-button>
        </a-tooltip>
      </div>
    </div>

    <!-- ===== 智能体协作过程（可折叠） ===== -->
    <transition name="bot-slide">
      <div v-if="traceVisible && (trace.length || running)" class="bot-trace">
        <div class="bot-trace-head" @click="traceOpen = !traceOpen">
          <a-icon :type="traceOpen ? 'down' : 'right'"/>
          <span>智能体协作过程</span>
          <span v-if="running" class="bot-trace-running">
            <a-icon type="loading"/> {{ runningLabel }}
          </span>
          <span v-else class="bot-trace-done">共 {{ trace.length }} 步</span>
        </div>
        <div v-show="traceOpen" class="bot-trace-body">
          <div v-for="(item, index) in trace" :key="index"
               class="bot-trace-item" :class="'is-' + item.status">
            <span class="bot-trace-dot"></span>
            <span class="bot-trace-agent">{{ item.label }}</span>
            <span class="bot-trace-detail">{{ item.detail }}</span>
          </div>
        </div>
      </div>
    </transition>

    <!-- ===== 消息区 ===== -->
    <div ref="scroller" class="bot-messages">
      <!-- 欢迎区 -->
      <div v-if="!messages.length" class="bot-welcome">
        <div class="bot-welcome-logo">罗</div>
        <h2>你好，我是小罗Bot 🏖️</h2>
        <p class="bot-welcome-desc">
          开罗论坛的 AI 搜索引擎助手。我会先在论坛的文章、评论、资源与标签里找答案；
          如果站内没有相关内容，你还可以打开上面的「联网搜索」，让我去互联网上继续找。
        </p>

        <div class="bot-suggest-title">试试这样问</div>
        <div class="bot-suggests">
          <div v-for="(item, index) in suggests" :key="index"
               class="bot-suggest" @click="useSuggest(item.text)">
            <a-icon :type="item.icon"/>
            <span>{{ item.text }}</span>
          </div>
        </div>

        <div class="bot-capabilities">
          <div class="bot-capability">
            <a-icon type="cluster"/>
            <div>
              <strong>多智能体协作</strong>
              <span>调度、论坛检索、联网搜索、多模态理解、答案合成、质量评估六个智能体分工完成一次回答</span>
            </div>
          </div>
          <div class="bot-capability">
            <a-icon type="picture"/>
            <div>
              <strong>多模态检索</strong>
              <span>文字与图片共用一个向量空间，可以直接上传截图、报错图来提问</span>
            </div>
          </div>
          <div class="bot-capability">
            <a-icon type="safety-certificate"/>
            <div>
              <strong>有据可查</strong>
              <span>回答会标注每条信息来自论坛还是互联网，找不到就直说找不到</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <BotMessage
          v-for="(message, index) in messages"
          :key="index"
          :message="message"
          @regenerate="regenerate"
          @preview="previewImage"/>
    </div>

    <!-- ===== 输入区 ===== -->
    <div class="bot-composer">
      <!-- 待发送的图片预览 -->
      <div v-if="pendingImage" class="bot-pending-image">
        <img :src="pendingImage" alt="待发送的图片"/>
        <a-icon type="close-circle" class="bot-pending-remove" @click="pendingImage = ''"/>
      </div>

      <div class="bot-composer-box" :class="{ 'is-focus': focused }">
        <textarea
            ref="input"
            v-model="draft"
            class="bot-textarea"
            :placeholder="placeholder"
            rows="1"
            @focus="focused = true"
            @blur="focused = false"
            @keydown.enter.exact.prevent="send"
            @input="autoGrow"></textarea>

        <div class="bot-composer-tools">
          <a-tooltip title="上传图片提问（支持截图、报错图、流程图）">
            <div class="bot-tool" @click="pickImage">
              <a-icon type="picture"/>
            </div>
          </a-tooltip>
          <input ref="file" type="file" accept="image/*" style="display:none" @change="onFileChange"/>

          <a-tooltip :title="webSearchEnabled ? '已开启联网搜索' : '开启后，论坛查不到时会去互联网找'">
            <div class="bot-tool" :class="{ 'is-on': webSearchEnabled }" @click="toggleWebSearch">
              <a-icon type="global"/>
            </div>
          </a-tooltip>

          <span class="bot-composer-hint">Enter 发送 / Shift+Enter 换行</span>

          <a-button v-if="running" size="small" class="bot-send-btn-stop" @click="stop">
            <a-icon type="pause"/> 停止
          </a-button>
          <a-button v-else size="small" type="primary" class="bot-send-btn"
                    :disabled="!canSend" @click="send">
            <a-icon type="send"/> 发送
          </a-button>
        </div>
      </div>

      <div class="bot-disclaimer">
        小罗Bot 的回答由 AI 生成，可能不准确；请以论坛原文与官方文档为准。
      </div>
    </div>

    <!-- ===== 图片预览 ===== -->
    <a-modal :visible="previewVisible" :footer="null" :width="760"
             :bodyStyle="{padding: '8px', textAlign: 'center'}"
             @cancel="previewVisible = false">
      <img :src="previewSrc" style="max-width:100%;max-height:70vh" alt="预览"/>
    </a-modal>

    <!-- ===== 知识库面板 ===== -->
    <a-modal title="小罗Bot 知识库" :visible="kbVisible" :footer="null" :width="560"
             @cancel="kbVisible = false">
      <a-spin :spinning="kbLoading">
        <div v-if="kb" class="bot-kb">
          <!-- 读取失败时不要说成"知识库是空的"：这两件事必须区分开 -->
          <div v-if="kb.ok === false" class="bot-kb-error">
            <a-icon type="warning"/>
            知识库统计读取失败，下面的数字不可信（可能是向量库文件损坏或服务未就绪）。
            <span v-if="kb.error" class="bot-kb-error-detail">{{ kb.error }}</span>
          </div>
          <!-- 向量集合属于内部实现细节（t_knowledge_collection），只给管理员看 -->
          <div class="bot-kb-row" v-if="isAdmin && kb.collection">
            <span class="bot-kb-label">向量集合</span>
            <span>{{ kb.collection }}</span>
          </div>
          <div class="bot-kb-row">
            <span class="bot-kb-label">知识条目</span>
            <span><strong>{{ kb.total }}</strong> 条</span>
          </div>
          <div class="bot-kb-row">
            <span class="bot-kb-label">按来源</span>
            <span class="bot-kb-tags">
              <a-tag v-for="(count, key) in kb.bySourceType" :key="key"
                     :color="count ? 'gold' : undefined">
                {{ sourceTypeName(key) }} {{ count }}
              </a-tag>
            </span>
          </div>
          <div class="bot-kb-row" v-if="kb.sources && kb.sources.length">
            <span class="bot-kb-label">论坛数据源</span>
            <span class="bot-kb-tags">
              <!--
                注意：不可用时必须传 undefined，不能传 'default'。
                antd 的预设色里没有 'default'，传它会落到 `color && !isPresetColor(color)`
                分支上，加上 ant-tag-has-color（该类的文字色是 #fff），
                在浅色底上就变成"白字白底"看不见了。
              -->
              <a-tag v-for="(item, index) in kb.sources" :key="index"
                     :color="item.available ? 'green' : undefined">
                {{ item.name }}{{ item.available ? ' 可用' : ' 不可用' }}
              </a-tag>
            </span>
          </div>
          <a-divider style="margin: 12px 0"/>

          <!-- 管理员：可触发同步（会重建整个知识库，属运维操作） -->
          <template v-if="isAdmin">
            <div class="bot-kb-tip">
              论坛新增文章后，可点下面的按钮把最新内容重新索引进向量库
              （优先走 springboot 网关，网关不可用时自动回退到直连 MySQL）。
            </div>
            <div style="margin-top: 12px">
              <a-button type="primary" size="small" :loading="syncing" @click="syncKnowledge">
                <a-icon type="sync"/> 同步论坛内容
              </a-button>
              <a-button size="small" style="margin-left: 8px" @click="loadKnowledge">
                <a-icon type="reload"/> 刷新
              </a-button>
              <span v-if="syncMessage" class="bot-kb-sync-msg">{{ syncMessage }}</span>
            </div>

            <a-divider style="margin: 16px 0 12px"/>

            <!-- ===== 上传文档附件 ===== -->
            <div class="bot-upload-title">
              <a-icon type="cloud-upload"/>
              上传文档附件
              <span class="bot-upload-sub">传上来就能被小罗Bot 检索到，不用再跑命令行脚本</span>
            </div>

            <a-upload-dragger
                class="bot-upload-dragger"
                name="file"
                :multiple="true"
                :showUploadList="false"
                :beforeUpload="handleDocPick"
                :disabled="!uploadLimits || !uploadLimits.enabled">
              <p class="ant-upload-drag-icon"><a-icon type="inbox"/></p>
              <p class="ant-upload-text">点击或把文件拖到这里上传</p>
              <p class="ant-upload-hint" v-if="uploadLimits">
                支持 {{ (uploadLimits.allowedExtensions || []).join(' ') }}；
                单个文件不超过 {{ uploadLimits.maxSizeMb }}MB
              </p>
            </a-upload-dragger>

            <!-- 本次上传的进度（解析与向量化在服务端后台进行，所以要轮询） -->
            <div v-if="uploadTasks.length" class="bot-upload-tasks">
              <div v-for="task in uploadTasks" :key="task.id" class="bot-upload-task"
                   :class="'is-' + task.state">
                <a-icon :type="taskIcon(task)"/>
                <span class="bot-upload-name" :title="task.fileName">{{ task.fileName }}</span>
                <span class="bot-upload-state">{{ task.text }}</span>
              </div>
            </div>

            <!-- 已入库的附件（即使为 0 也显示表头，让管理员知道"我上传的东西去哪了"） -->
            <div class="bot-attach-list">
              <div class="bot-attach-head">
                已入库文档（{{ attachments.length }}）
                <a class="bot-attach-refresh" @click="loadAttachments">刷新</a>
              </div>
              <div v-if="!attachments.length" class="bot-attach-empty">
                还没有上传过文档附件；上传成功的文件会出现在这里，并立刻可以被小罗Bot 检索到。
              </div>
              <div v-for="item in attachments" :key="item.docId" class="bot-attach-item">
                <a-icon :type="attachIcon(item)"/>
                <span class="bot-attach-name" :title="item.title">{{ item.title }}</span>
                <span class="bot-attach-meta">{{ item.chunks }} 块<span v-if="item.author"> · {{ item.author }}</span></span>
                <a-popconfirm title="删除后该文档的知识条目会一并移除，确定吗？"
                              okText="删除" cancelText="取消"
                              @confirm="removeAttachment(item)">
                  <a-icon type="delete" class="bot-attach-del"/>
                </a-popconfirm>
              </div>
            </div>
          </template>

          <!-- 非管理员/游客：只读统计 -->
          <template v-else>
            <div class="bot-kb-tip">
              <a-icon type="info-circle"/> 以上是小罗Bot 当前可检索的知识规模。
              知识库的内容由管理员从论坛同步维护，普通用户与游客无需（也无法）操作。
            </div>
            <div style="margin-top: 12px">
              <a-button size="small" @click="loadKnowledge">
                <a-icon type="reload"/> 刷新
              </a-button>
            </div>
          </template>
        </div>
      </a-spin>
    </a-modal>
  </div>
</template>

<script>
  import aiBotService from "@/service/aiBotService";
  import BotMessage from "@/components/bot/BotMessage";

  // 智能体展示名（与后端 agent/events.py 的 AGENT_LABELS 对应，前端留一份兜底）
  const AGENT_LABELS = {
    supervisor: "调度智能体",
    vision: "多模态理解智能体",
    forum: "论坛检索智能体",
    web: "联网搜索智能体",
    compose: "答案合成智能体",
    evaluate: "质量评估智能体",
  };

  const SOURCE_TYPE_NAMES = {
    article: "文章",
    comment: "评论",
    resource: "资源",
    label: "标签",
    attachment: "上传文档",
    snapshot: "导入文档",
    pdf: "PDF文档",
  };

  export default {
    name: "BotChat",

    components: {BotMessage},

    props: {
      // 联网搜索的默认开关（来自页面，便于后续做用户偏好持久化）
      defaultWebSearch: {
        type: Boolean,
        default: false,
      },
    },

    data() {
      return {
        messages: [],
        draft: "",
        pendingImage: "",
        sessionId: "",
        running: false,
        focused: false,
        abortController: null,

        // 联网搜索开关
        webSearchEnabled: this.defaultWebSearch,

        // 智能体协作轨迹
        trace: [],
        traceOpen: true,
        traceVisible: true,
        runningLabel: "",

        // 图片预览
        previewVisible: false,
        previewSrc: "",

        // 知识库面板
        kbVisible: false,
        kbLoading: false,
        kb: null,
        syncing: false,
        syncMessage: "",

        // 文档附件上传（仅管理员）
        uploadLimits: null,
        uploadTasks: [],
        attachments: [],

        suggests: [
          {icon: "tags", text: "论坛里有哪些标签？"},
          {icon: "file-text", text: "论坛最近发布了哪些文章？"},
          {icon: "appstore", text: "论坛的资源导航里有哪些设计素材站？"},
          {icon: "bulb", text: "Vue 2 项目怎么开启 history 路由模式？", web: true},
        ],
      };
    },

    computed: {
      /**
       * 是否管理员。
       * 与论坛既有约定保持一致：store.isManage 只在角色里出现 NS_SUPER_ADMIN_ROLE 时置真
       * （见 App.vue 的 getAccess），游客/普通用户都是 false。
       *
       * 用途：知识库面板里的「向量集合」（内部实现细节）与「同步论坛内容」
       * （会重建整个向量库的重操作）只对管理员展示。
       * 注意前端隐藏只是体验层，服务端在 AiBotController 里也做了同样校验。
       */
      isAdmin() {
        return this.$store.state.isLogin && this.$store.state.isManage;
      },

      canSend() {
        return !this.running && (this.draft.trim().length > 0 || !!this.pendingImage);
      },

      placeholder() {
        if (this.webSearchEnabled) {
          return "问点什么吧…（已开启联网搜索，论坛查不到时会去网上找）";
        }
        return "问点什么吧…（当前只在论坛知识库中检索）";
      },
    },

    mounted() {
      // 会话 id 存在 sessionStorage，刷新页面后还能接着上一轮聊
      const saved = window.sessionStorage.getItem("botSessionId");
      if (saved) {
        this.sessionId = saved;
      }
      const savedWeb = window.localStorage.getItem("botWebSearch");
      if (savedWeb !== null) {
        this.webSearchEnabled = savedWeb === "1";
      }
      this.autoGrow();
    },

    beforeDestroy() {
      this.stop();
    },

    methods: {
      // ------------------------------------------------------------------
      // 交互
      // ------------------------------------------------------------------

      toggleWebSearch() {
        this.webSearchEnabled = !this.webSearchEnabled;
        window.localStorage.setItem("botWebSearch", this.webSearchEnabled ? "1" : "0");
        this.$message.info(this.webSearchEnabled
            ? "已开启联网搜索：论坛查不到时会到互联网上继续找"
            : "已关闭联网搜索：只在论坛知识库中检索");
      },

      useSuggest(text) {
        // 建议里标了 web 的，顺手把联网开关打开，体验更顺
        const hit = this.suggests.find((s) => s.text === text);
        if (hit && hit.web) {
          this.webSearchEnabled = true;
        }
        this.draft = text;
        this.send();
      },

      autoGrow() {
        this.$nextTick(() => {
          const el = this.$refs.input;
          if (!el) {
            return;
          }
          el.style.height = "auto";
          el.style.height = Math.min(el.scrollHeight, 140) + "px";
        });
      },

      pickImage() {
        this.$refs.file && this.$refs.file.click();
      },

      onFileChange(event) {
        const file = event.target.files && event.target.files[0];
        event.target.value = "";
        if (!file) {
          return;
        }
        if (!/^image\//.test(file.type)) {
          this.$message.warning("请选择图片文件");
          return;
        }
        if (file.size > 5 * 1024 * 1024) {
          this.$message.warning("图片请控制在 5MB 以内");
          return;
        }
        const reader = new FileReader();
        reader.onload = () => {
          this.pendingImage = reader.result;
        };
        reader.readAsDataURL(file);
      },

      previewImage(src) {
        this.previewSrc = src;
        this.previewVisible = true;
      },

      newSession() {
        this.stop();
        this.sessionId = "";
        window.sessionStorage.removeItem("botSessionId");
        this.messages = [];
        this.trace = [];
        this.draft = "";
        this.pendingImage = "";
        this.$message.success("已开启新对话");
      },

      stop() {
        if (this.abortController) {
          this.abortController.abort();
          this.abortController = null;
        }
      },

      // ------------------------------------------------------------------
      // 发送与流式接收
      // ------------------------------------------------------------------

      send() {
        if (!this.canSend) {
          return;
        }
        const question = this.draft.trim();
        const image = this.pendingImage;

        this.messages.push({
          role: "user",
          content: question,
          image: image,
        });

        // 占位的助手消息，delta 到了就往里追加
        const assistant = {
          role: "assistant",
          content: "",
          streaming: true,
          citations: [],
          images: [],
          usedWebSearch: false,
          forumHitCount: 0,
          answerScore: 0,
        };
        this.messages.push(assistant);
        const assistantRef = this.messages[this.messages.length - 1];

        this.draft = "";
        this.pendingImage = "";
        this.trace = [];
        this.running = true;
        this.runningLabel = "正在调度智能体…";
        this.autoGrow();
        this.scrollToBottom();

        const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
        this.abortController = controller;

        const payload = {
          question: question,
          image: image || null,
          sessionId: this.sessionId || null,
          webSearchEnabled: this.webSearchEnabled,
        };

        aiBotService.chatStream(payload, {
          onMeta: (data) => {
            if (data.sessionId) {
              this.sessionId = data.sessionId;
              window.sessionStorage.setItem("botSessionId", data.sessionId);
            }
          },

          onPlan: () => {
            // 计划事件只用于展示，具体步骤在 agent 事件里体现
          },

          onAgent: (data) => {
            const label = data.label || AGENT_LABELS[data.agent] || data.agent;
            if (data.status === "start") {
              this.runningLabel = label + "工作中…";
              // 正在工作的智能体也先放进轨迹，让用户看到"现在轮到谁"
              this.trace.push({
                label: label,
                detail: data.detail || "正在处理…",
                status: "running",
                agent: data.agent,
              });
            } else {
              // 完结/跳过：找到同 agent 的最后一条 running 记录并替换
              let index = -1;
              for (let i = this.trace.length - 1; i >= 0; i--) {
                if (this.trace[i].agent === data.agent) {
                  index = i;
                  break;
                }
              }
              const entry = {
                label: label,
                detail: data.detail || "",
                status: data.status === "skipped" ? "skipped" : "done",
                agent: data.agent,
              };
              if (index >= 0) {
                this.$set(this.trace, index, entry);
              } else {
                this.trace.push(entry);
              }
              if (data.agent === "forum" && data.hitCount !== undefined) {
                assistantRef.forumHitCount = data.hitCount;
              }
            }
            this.scrollToBottom();
          },

          onSources: (data) => {
            if (data && data.forum && data.forum.length) {
              assistantRef.forumHitCount = data.forum.length;
            }
          },

          onDelta: (data) => {
            assistantRef.content += data.text || "";
            this.scrollToBottom();
          },

          onDone: (data) => {
            assistantRef.streaming = false;
            assistantRef.elapsedMs = data.elapsedMs;
            assistantRef.answerScore = data.answerScore;
            assistantRef.usedWebSearch = data.usedWebSearch;
            assistantRef.webSearchEnabled = data.webSearchEnabled;
            assistantRef.forumSufficient = data.forumSufficient;
            assistantRef.forumRelevance = data.forumRelevance;
            assistantRef.citations = data.citations || [];
            assistantRef.images = data.images || [];
            // 后端最终答案优先（流式拼接可能有细微差异）
            if (data.answer) {
              assistantRef.content = data.answer;
            }
            if (!assistantRef.content) {
              assistantRef.content = "抱歉，这次没有生成出回答，请换个说法再试一次。";
            }
            this.running = false;
            this.runningLabel = "";
            this.scrollToBottom();
          },

          onError: (data) => {
            assistantRef.streaming = false;
            assistantRef.error = true;
            if (!assistantRef.content) {
              assistantRef.content = "";
            }
            this.messages.push({
              role: "system",
              icon: "warning",
              content: (data && data.message) || "小罗Bot 服务出现异常，请稍后再试",
            });
            this.running = false;
            this.runningLabel = "";
            this.scrollToBottom();
          },

          onEnd: () => {
            assistantRef.streaming = false;
            this.running = false;
            this.runningLabel = "";
            this.abortController = null;
          },
        }, controller ? {signal: controller.signal} : {});
      },

      regenerate() {
        // 找到最后一条用户提问，重新发一次
        for (let i = this.messages.length - 1; i >= 0; i--) {
          if (this.messages[i].role === "user") {
            this.draft = this.messages[i].content || "";
            this.pendingImage = this.messages[i].image || "";
            // 丢掉旧的问答对，避免界面重复
            this.messages.splice(i, this.messages.length - i);
            this.autoGrow();
            this.send();
            return;
          }
        }
      },

      scrollToBottom() {
        this.$nextTick(() => {
          const el = this.$refs.scroller;
          if (el) {
            el.scrollTop = el.scrollHeight;
          }
        });
      },

      // ------------------------------------------------------------------
      // 知识库面板
      // ------------------------------------------------------------------

      sourceTypeName(key) {
        return SOURCE_TYPE_NAMES[key] || key;
      },

      openKnowledge() {
        this.kbVisible = true;
        if (!this.kb) {
          this.loadKnowledge();
        }
        // 管理员才有上传区，顺带把限制与已入库列表拉回来
        if (this.isAdmin) {
          if (!this.uploadLimits) {
            this.loadUploadLimits();
          }
          this.loadAttachments();
        }
      },

      // ------------------------------------------------------------------
      // 文档附件上传（仅管理员）
      // ------------------------------------------------------------------

      loadUploadLimits() {
        aiBotService.kbUploadLimits()
            .then((res) => {
              this.uploadLimits = res.data || {enabled: false, allowedExtensions: [], maxSizeMb: 0};
            })
            .catch(() => {
              this.uploadLimits = {enabled: false, allowedExtensions: [], maxSizeMb: 0};
            });
      },

      loadAttachments() {
        aiBotService.kbAttachments()
            .then((res) => {
              this.attachments = res.data || [];
            })
            .catch(() => {
              this.attachments = [];
            });
      },

      /**
       * a-upload 的 beforeUpload：返回 false 阻止 antd 自己上传，
       * 改由我们自己控制（要拿 onUploadProgress，还要接后台入库的轮询）。
       */
      handleDocPick(file) {
        if (!this.isAdmin) {
          this.$message.warning("只有管理员可以上传文档到知识库");
          return false;
        }
        const limits = this.uploadLimits || {};
        const ext = ("." + (file.name.split(".").pop() || "")).toLowerCase();
        const allowed = (limits.allowedExtensions || []).map((e) => e.toLowerCase());
        if (allowed.length && allowed.indexOf(ext) < 0) {
          this.$message.error(`不支持的文件类型 ${ext}`);
          return false;
        }
        if (limits.maxSizeMb && file.size > limits.maxSizeMb * 1024 * 1024) {
          this.$message.error(`文件超过 ${limits.maxSizeMb}MB`);
          return false;
        }
        this.startUpload(file);
        return false;
      },

      startUpload(file) {
        const task = {
          id: "local-" + Date.now() + "-" + Math.random().toString(36).slice(2, 7),
          fileName: file.name,
          state: "uploading",
          text: "上传中 0%",
        };
        this.uploadTasks.unshift(task);

        aiBotService.kbUpload(file, (percent) => {
          const target = this.uploadTasks.find((t) => t.id === task.id);
          if (target && target.state === "uploading") {
            target.text = `上传中 ${percent}%`;
          }
        })
            .then((res) => {
              const data = res.data || {};
              const target = this.uploadTasks.find((t) => t.id === task.id);
              if (!data.accepted) {
                if (target) {
                  target.state = "failed";
                  target.text = data.reason || "服务端拒绝了该文件";
                }
                this.$message.error(data.reason || "上传被拒绝");
                return;
              }
              if (target) {
                target.state = "processing";
                target.text = "已上传，正在解析入库…";
              }
              this.pollUpload(data.taskId, task.id);
            })
            .catch((err) => {
              const target = this.uploadTasks.find((t) => t.id === task.id);
              if (target) {
                target.state = "failed";
                target.text = (err && err.desc) || "上传失败";
              }
              this.$message.error((err && err.desc) || "上传失败");
            });
      },

      /** 轮询后台入库进度；完成后刷新统计与附件列表 */
      pollUpload(taskId, localId, times) {
        const round = times || 0;
        if (round > 150) {
          const target = this.uploadTasks.find((t) => t.id === localId);
          if (target) {
            target.state = "failed";
            target.text = "等待超时，请稍后用「刷新」查看结果";
          }
          return;
        }
        aiBotService.kbUploadStatus(taskId)
            .then((res) => {
              const data = res.data || {};
              const target = this.uploadTasks.find((t) => t.id === localId);
              if (target) {
                target.text = data.progressText || "处理中…";
                target.state = data.running ? "processing" : (data.state === "done" ? "done" : "failed");
              }
              if (data.running) {
                setTimeout(() => this.pollUpload(taskId, localId, round + 1), 2000);
                return;
              }
              if (data.state === "done") {
                const r = data.result || {};
                this.$message.success(
                    `${r.fileName || "文件"} 已入库：${r.inserted || 0} 条知识`);
                this.loadKnowledge();
                this.loadAttachments();
              } else {
                this.$message.error(data.error || "入库失败");
              }
            })
            .catch((err) => {
              const target = this.uploadTasks.find((t) => t.id === localId);
              if (target) {
                target.state = "failed";
                target.text = (err && err.desc) || "查询进度失败";
              }
            });
      },

      removeAttachment(item) {
        aiBotService.kbAttachmentDelete(item.docId)
            .then(() => {
              this.$message.success(`已删除《${item.title}》`);
              this.loadAttachments();
              this.loadKnowledge();
            })
            .catch((err) => {
              this.$message.error((err && err.desc) || "删除失败");
            });
      },

      taskIcon(task) {
        if (task.state === "done") {
          return "check-circle";
        }
        if (task.state === "failed") {
          return "close-circle";
        }
        return "loading";
      },

      /**
       * 按文件名后缀选图标。
       *
       * 注意：知识条目里的 `fileType` 字段存的是**块类型**（text/image），
       * 不是文件扩展名（向量库字段就是这么定义的），所以这里从 title（原始文件名）取后缀。
       */
      attachIcon(item) {
        const name = (item && item.title) || "";
        const dot = name.lastIndexOf(".");
        const ext = dot >= 0 ? name.slice(dot).toLowerCase() : "";
        if (ext === ".pdf") {
          return "file-pdf";
        }
        if (ext === ".docx" || ext === ".doc") {
          return "file-word";
        }
        if (ext === ".csv" || ext === ".json" || ext === ".xlsx" || ext === ".xls") {
          return "file-excel";
        }
        if ([".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"].indexOf(ext) >= 0) {
          return "file-image";
        }
        return "file-text";
      },

      loadKnowledge() {
        this.kbLoading = true;
        aiBotService.kbStatus()
            .then((res) => {
              this.kb = res.data;
            })
            .catch((err) => {
              this.$message.error(err.desc || "读取知识库状态失败");
            })
            .finally(() => {
              this.kbLoading = false;
            });
      },

      syncKnowledge() {
        // 双保险：按钮本身只对管理员渲染，这里再挡一次（例如角色状态刚变化、或有人绕过 UI 调用）
        if (!this.isAdmin) {
          this.$message.warning("只有管理员可以同步知识库");
          return;
        }
        this.syncing = true;
        this.syncMessage = "同步任务已提交，正在后台执行…";
        aiBotService.kbSync({async: true})
            .then((res) => {
              if (res.data && res.data.accepted === false) {
                this.syncMessage = res.data.reason || "已有同步任务在执行";
                this.syncing = false;
                return;
              }
              this.pollSyncStatus(0);
            })
            .catch((err) => {
              this.syncing = false;
              this.syncMessage = "";
              // 服务端也会校验权限，被拒时 desc 是「只有管理员可以同步知识库」
              this.$message.error((err && err.desc) || "触发同步失败");
            });
      },

      pollSyncStatus(times) {
        if (times > 100) {
          this.syncing = false;
          this.syncMessage = "同步仍在后台进行，可稍后刷新查看";
          return;
        }
        aiBotService.kbSyncStatus()
            .then((res) => {
              const state = res.data || {};
              if (state.running) {
                this.syncMessage = "正在同步论坛内容…";
                setTimeout(() => this.pollSyncStatus(times + 1), 3000);
                return;
              }
              this.syncing = false;
              if (state.error) {
                this.syncMessage = "同步失败：" + state.error;
              } else if (state.result) {
                const r = state.result;
                this.syncMessage = r.ok
                    ? `同步完成：${r.documents} 条内容 / ${r.inserted} 条知识入库（来源：${r.source}）`
                    : "同步失败：" + (r.error || "没有可用数据源");
                this.loadKnowledge();
              } else {
                this.syncMessage = "";
              }
            })
            .catch(() => {
              this.syncing = false;
              this.syncMessage = "";
            });
      },
    },
  };
</script>

<style lang="less" scoped>
  @sand-50: #FFFDF7;
  @sand-100: #FBF4E6;
  @sand-200: #F3E7CE;
  @gold: #D4AF37;
  @gold-deep: #B8952C;
  @ink: #3D3A34;
  @ink-soft: #6B6558;

  .bot-chat {
    display: flex;
    flex-direction: column;
    // 高度由父级（BotIndex 的 .content，纯 CSS）用 flex 分配，
    // 这里只保证一个最小可用的高度。
    // 注意：Less 2.x 会去计算 calc() 里的表达式并把结果算坏，所以本文件不用 calc()。
    flex: 1 1 auto;
    min-height: 420px;
    background: linear-gradient(180deg, @sand-50 0%, #FFFDF9 100%);
    border-radius: 12px;
    overflow: hidden;
  }

  /* ===== 顶部 ===== */
  .bot-chat-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 18px;
    background: linear-gradient(120deg, #FFF8E6 0%, #FDF1D6 55%, #FAE9C4 100%);
    border-bottom: 1px solid @sand-200;
  }

  .bot-chat-title {
    display: flex;
    align-items: center;
  }

  .bot-logo,
  .bot-welcome-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    margin-right: 10px;
    border-radius: 10px;
    color: #fff;
    font-weight: 700;
    font-size: 17px;
    background: linear-gradient(135deg, @gold 0%, @gold-deep 100%);
    box-shadow: 0 2px 8px rgba(184, 149, 44, 0.3);
  }

  .bot-title-text {
    .bot-name {
      font-size: 16px;
      font-weight: 600;
      color: @ink;
      display: flex;
      align-items: center;
    }

    .bot-version {
      margin-left: 8px;
      color: @gold-deep;
      background: rgba(212, 175, 55, 0.14);
      border-color: rgba(212, 175, 55, 0.35);
      font-size: 11px;
      line-height: 17px;
    }

    .bot-subtitle {
      font-size: 12px;
      color: @ink-soft;
      margin-top: 2px;
    }
  }

  .bot-chat-switches {
    display: flex;
    align-items: center;

    .bot-switch {
      display: flex;
      align-items: center;
      padding: 4px 10px;
      border-radius: 16px;
      cursor: pointer;
      background: rgba(255, 255, 255, 0.7);
      border: 1px solid @sand-200;
      font-size: 12px;
      color: @ink-soft;
      transition: all 0.2s;

      .anticon {
        margin-right: 5px;
      }

      .ant-switch {
        margin-left: 8px;
      }

      &.is-on {
        color: @gold-deep;
        border-color: rgba(212, 175, 55, 0.6);
        background: rgba(212, 175, 55, 0.12);
      }
    }

    .bot-btn-link {
      color: @ink-soft;
      padding: 0 6px;
      margin-left: 6px;

      &:hover {
        color: @gold-deep;
      }
    }
  }

  /* ===== 协作轨迹 ===== */
  .bot-trace {
    background: #FFFCF3;
    border-bottom: 1px solid @sand-200;
    font-size: 12px;
  }

  .bot-trace-head {
    display: flex;
    align-items: center;
    padding: 7px 18px;
    cursor: pointer;
    color: @ink-soft;
    user-select: none;

    .anticon:first-child {
      margin-right: 6px;
    }

    .bot-trace-running {
      margin-left: 10px;
      color: @gold-deep;
    }

    .bot-trace-done {
      margin-left: 10px;
      color: #A79E8A;
    }
  }

  .bot-trace-body {
    max-height: 148px;
    overflow-y: auto;
    padding: 2px 18px 10px;
  }

  .bot-trace-item {
    display: flex;
    align-items: baseline;
    padding: 3px 0;
    color: @ink-soft;

    .bot-trace-dot {
      flex: 0 0 auto;
      width: 6px;
      height: 6px;
      margin-right: 8px;
      border-radius: 50%;
      background: #D8CFB8;
    }

    .bot-trace-agent {
      flex: 0 0 auto;
      min-width: 112px;
      font-weight: 600;
      color: @ink;
    }

    .bot-trace-detail {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    &.is-running {
      .bot-trace-dot {
        background: @gold;
        animation: bot-pulse 1.2s ease-in-out infinite;
      }

      .bot-trace-detail {
        color: @gold-deep;
      }
    }

    &.is-done .bot-trace-dot {
      background: #7BB662;
    }

    &.is-skipped {
      opacity: 0.6;

      .bot-trace-dot {
        background: #C9C2B0;
      }
    }
  }

  @keyframes bot-pulse {
    0%, 100% {
      opacity: 1;
      transform: scale(1);
    }
    50% {
      opacity: 0.45;
      transform: scale(0.75);
    }
  }

  .bot-slide-enter-active,
  .bot-slide-leave-active {
    transition: all 0.2s ease;
  }

  .bot-slide-enter,
  .bot-slide-leave-to {
    opacity: 0;
    max-height: 0;
  }

  /* ===== 消息区 ===== */
  .bot-messages {
    flex: 1;
    overflow-y: auto;
    padding: 18px 18px 4px;
    scroll-behavior: smooth;
  }

  .bot-welcome {
    max-width: 640px;
    margin: 8px auto 0;
    text-align: center;
    color: @ink-soft;

    .bot-welcome-logo {
      width: 54px;
      height: 54px;
      margin: 0 auto 12px;
      font-size: 24px;
      border-radius: 14px;
    }

    h2 {
      font-size: 20px;
      color: @ink;
      margin-bottom: 8px;
      font-weight: 600;
    }

    .bot-welcome-desc {
      font-size: 13px;
      line-height: 1.85;
      margin-bottom: 20px;
    }
  }

  .bot-suggest-title {
    font-size: 12px;
    color: #A79E8A;
    margin-bottom: 8px;
  }

  .bot-suggests {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    margin-bottom: 22px;
  }

  .bot-suggest {
    display: flex;
    align-items: center;
    margin: 0 5px 9px;
    padding: 8px 14px;
    border-radius: 18px;
    background: #fff;
    border: 1px solid @sand-200;
    font-size: 13px;
    color: @ink;
    cursor: pointer;
    transition: all 0.18s;

    .anticon {
      margin-right: 7px;
      color: @gold-deep;
    }

    &:hover {
      border-color: @gold;
      box-shadow: 0 3px 12px rgba(184, 149, 44, 0.16);
      transform: translateY(-1px);
    }
  }

  .bot-capabilities {
    text-align: left;
    border-top: 1px dashed @sand-200;
    padding-top: 16px;
  }

  .bot-capability {
    display: flex;
    align-items: flex-start;
    padding: 7px 0;

    > .anticon {
      flex: 0 0 auto;
      width: 30px;
      height: 30px;
      margin-right: 10px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: @gold-deep;
      background: rgba(212, 175, 55, 0.12);
      font-size: 15px;
    }

    strong {
      display: block;
      color: @ink;
      font-size: 13px;
      font-weight: 600;
    }

    span {
      font-size: 12px;
      line-height: 1.7;
    }
  }

  /* ===== 输入区 ===== */
  .bot-composer {
    padding: 10px 18px 12px;
    border-top: 1px solid @sand-200;
    background: rgba(255, 253, 247, 0.92);
  }

  .bot-pending-image {
    position: relative;
    display: inline-block;
    margin-bottom: 8px;

    img {
      max-height: 76px;
      max-width: 140px;
      border-radius: 8px;
      border: 1px solid @sand-200;
      display: block;
    }

    .bot-pending-remove {
      position: absolute;
      top: -7px;
      right: -7px;
      font-size: 16px;
      color: #C0392B;
      background: #fff;
      border-radius: 50%;
      cursor: pointer;
    }
  }

  .bot-composer-box {
    border: 1px solid @sand-200;
    border-radius: 12px;
    background: #fff;
    padding: 8px 10px 6px;
    transition: all 0.18s;

    &.is-focus {
      border-color: @gold;
      box-shadow: 0 0 0 3px rgba(212, 175, 55, 0.12);
    }
  }

  .bot-textarea {
    width: 100%;
    border: none;
    outline: none;
    resize: none;
    font-size: 14px;
    line-height: 1.7;
    color: @ink;
    background: transparent;
    max-height: 140px;
    font-family: inherit;

    &::placeholder {
      color: #BDB49F;
    }
  }

  .bot-composer-tools {
    display: flex;
    align-items: center;
    margin-top: 4px;

    .bot-tool {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 28px;
      height: 28px;
      margin-right: 6px;
      border-radius: 7px;
      color: @ink-soft;
      cursor: pointer;
      font-size: 15px;

      &:hover {
        background: @sand-100;
        color: @gold-deep;
      }

      &.is-on {
        color: @gold-deep;
        background: rgba(212, 175, 55, 0.14);
      }
    }

    .bot-composer-hint {
      flex: 1;
      font-size: 11px;
      color: #BDB49F;
    }

    .bot-send-btn,
    .bot-send-btn-stop {
      border-radius: 8px;
      height: 28px;
      font-size: 13px;
    }

    .bot-send-btn {
      background: linear-gradient(135deg, @gold 0%, @gold-deep 100%);
      border-color: @gold-deep;

      &[disabled] {
        background: #E6DFCE;
        border-color: #E6DFCE;
        color: #fff;
      }
    }
  }

  .bot-disclaimer {
    margin-top: 7px;
    text-align: center;
    font-size: 11px;
    color: #BDB49F;
  }

  /* ===== 知识库面板 ===== */
  .bot-kb {
    font-size: 13px;
    color: @ink;
  }

  .bot-kb-error {
    display: flex;
    align-items: flex-start;
    margin-bottom: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    background: #FFF7E6;
    border: 1px solid #FFD591;
    font-size: 12px;
    line-height: 1.7;
    color: #AD6800;

    .anticon {
      margin-right: 6px;
      margin-top: 2px;
    }

    .bot-kb-error-detail {
      display: block;
      margin-top: 2px;
      color: #B98A4A;
      word-break: break-all;
    }
  }

  .bot-kb-row {
    display: flex;
    align-items: flex-start;
    padding: 5px 0;

    .bot-kb-label {
      flex: 0 0 82px;
      color: @ink-soft;
    }
  }

  .bot-kb-tags {
    .ant-tag {
      margin-bottom: 4px;
    }
  }

  .bot-kb-tip {
    font-size: 12px;
    color: @ink-soft;
    line-height: 1.8;
  }

  .bot-kb-sync-msg {
    margin-left: 10px;
    font-size: 12px;
    color: @gold-deep;
  }

  /* ===== 文档附件上传 ===== */
  .bot-upload-title {
    font-size: 13px;
    font-weight: 600;
    color: @ink;
    margin-bottom: 6px;

    .anticon {
      margin-right: 6px;
      color: @gold-deep;
    }

    .bot-upload-sub {
      margin-left: 8px;
      font-weight: 400;
      font-size: 12px;
      color: @ink-soft;
    }
  }

  .bot-upload-dragger {
    display: block;

    /deep/ .ant-upload.ant-upload-drag {
      border: 1px dashed @sand-200;
      background: @sand-50;
      border-radius: 10px;
      padding: 6px 0;

      &:hover {
        border-color: @gold;
      }
    }

    /deep/ .ant-upload-drag-icon {
      margin-bottom: 2px;

      .anticon {
        font-size: 26px;
        color: @gold-deep;
      }
    }

    /deep/ .ant-upload-text {
      font-size: 13px;
      color: @ink;
      margin-bottom: 2px;
    }

    /deep/ .ant-upload-hint {
      font-size: 11px;
      color: #BDB49F;
      padding: 0 12px;
      line-height: 1.7;
    }
  }

  .bot-upload-tasks {
    margin-top: 8px;
  }

  .bot-upload-task {
    display: flex;
    align-items: center;
    font-size: 12px;
    padding: 3px 0;
    color: @ink-soft;

    .anticon {
      margin-right: 6px;
    }

    .bot-upload-name {
      max-width: 180px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: @ink;
    }

    .bot-upload-state {
      margin-left: 8px;
      color: @gold-deep;
    }

    &.is-done .anticon,
    &.is-done .bot-upload-state {
      color: #52c41a;
    }

    &.is-failed .anticon,
    &.is-failed .bot-upload-state {
      color: #f5222d;
    }
  }

  .bot-attach-list {
    margin-top: 12px;
    border-top: 1px dashed @sand-200;
    padding-top: 8px;
  }

  .bot-attach-head {
    font-size: 12px;
    color: @ink-soft;
    margin-bottom: 4px;

    .bot-attach-refresh {
      margin-left: 8px;
      color: @gold-deep;
    }
  }

  .bot-attach-empty {
    font-size: 12px;
    color: #BDB49F;
    line-height: 1.8;
    padding: 2px 0 4px;
  }

  .bot-attach-item {
    display: flex;
    align-items: center;
    font-size: 12px;
    padding: 4px 0;
    color: @ink;

    > .anticon:first-child {
      margin-right: 7px;
      color: @gold-deep;
    }

    .bot-attach-name {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .bot-attach-meta {
      flex: 0 0 auto;
      margin-left: 8px;
      color: #A79E8A;
    }

    .bot-attach-del {
      margin-left: 10px;
      color: #C9C2B0;
      cursor: pointer;

      &:hover {
        color: #f5222d;
      }
    }
  }

  /* ===== 移动端 ===== */
  @media screen and (max-width: 900px) {
    .bot-chat {
      border-radius: 0;
      min-height: 360px;
    }

    .bot-chat-head {
      flex-direction: column;
      align-items: flex-start;

      .bot-chat-switches {
        margin-top: 8px;
      }
    }

    .bot-trace-item .bot-trace-agent {
      min-width: 96px;
    }

    .bot-messages {
      padding: 12px 10px 4px;
    }

    .bot-composer {
      padding: 8px 10px 10px;
    }
  }
</style>
