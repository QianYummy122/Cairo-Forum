<template>
  <!--
    单条消息气泡。
    - role=user：右侧、金色渐变气泡，支持展示用户上传的图片
    - role=assistant：左侧、白底卡片，Markdown 渲染 + 来源引用 + 相关图片
    - role=system：居中的浅色提示条（用于错误、中断等系统信息）
  -->
  <div class="bot-message" :class="'bot-message-' + message.role">
    <!-- 头像 -->
    <div class="bot-avatar" v-if="message.role !== 'system'">
      <img v-if="message.role === 'user' && $store.state.picture" :src="$store.state.picture" alt="我"/>
      <img v-else-if="message.role === 'user'" src="@/assets/img/default_avatar.png" alt="我"/>
      <span v-else class="bot-avatar-bot">罗</span>
    </div>

    <div class="bot-bubble-wrap">
      <!-- 系统提示 -->
      <div v-if="message.role === 'system'" class="bot-system">
        <a-icon :type="message.icon || 'info-circle'"/>
        <span>{{ message.content }}</span>
      </div>

      <template v-else>
        <div class="bot-bubble">
          <!-- 用户上传的图片 -->
          <div v-if="message.image" class="bot-user-image">
            <img :src="message.image" alt="上传的图片" @click="previewImage(message.image)"/>
          </div>

          <!-- 正文 -->
          <div v-if="message.role === 'user'" class="bot-text-plain">{{ message.content }}</div>
          <div v-else class="markdown-body" v-html="renderedContent"></div>

          <!-- 光标：正在生成时显示 -->
          <span v-if="message.streaming" class="bot-caret"></span>

          <!-- 小罗Bot 的检索/联网信息条 -->
          <div v-if="message.role === 'assistant' && !message.streaming && metaLine" class="bot-meta-line">
            <span v-for="(item, index) in metaLine" :key="index" class="bot-meta-item">
              <a-icon :type="item.icon"/>
              {{ item.text }}
            </span>
          </div>

          <!-- 来源引用 -->
          <div v-if="message.role === 'assistant' && citations.length" class="bot-citations">
            <div class="bot-citations-title">
              <a-icon type="link"/>
              参考来源（{{ citations.length }}）
            </div>
            <ul>
              <li v-for="(cite, index) in citations" :key="index">
                <span class="bot-cite-tag" :class="cite.type === 'web' ? 'is-web' : 'is-forum'">
                  {{ cite.type === 'web' ? '联网' : '论坛' }}
                </span>
                <a v-if="cite.url" :href="cite.url" :target="isExternal(cite.url) ? '_blank' : '_self'"
                   rel="noopener noreferrer">{{ cite.title || cite.url }}</a>
                <span v-else>{{ cite.title }}</span>
                <span v-if="cite.author" class="bot-cite-author">· {{ cite.author }}</span>
              </li>
            </ul>
          </div>

          <!-- 命中的图片 -->
          <div v-if="message.role === 'assistant' && images.length" class="bot-images">
            <img v-for="(img, index) in images" :key="index" :src="img" alt="相关内容配图"
                 @click="previewImage(img)"/>
          </div>
        </div>

        <!-- 底部操作 -->
        <div v-if="message.role === 'assistant' && !message.streaming && message.content"
             class="bot-actions">
          <a-tooltip title="复制回答">
            <a-icon type="copy" @click="copy"/>
          </a-tooltip>
          <a-tooltip title="重新生成">
            <a-icon type="reload" @click="$emit('regenerate', message)"/>
          </a-tooltip>
          <span v-if="message.elapsedMs" class="bot-elapsed">{{ (message.elapsedMs / 1000).toFixed(1) }}s</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
  import {renderMarkdown, decorateLinks} from "@/utils/markdown";

  export default {
    name: "BotMessage",

    props: {
      message: {
        type: Object,
        required: true,
      },
    },

    computed: {
      renderedContent() {
        if (!this.message.content) {
          return "";
        }
        return decorateLinks(renderMarkdown(this.message.content));
      },

      citations() {
        return this.message.citations || [];
      },

      images() {
        return this.message.images || [];
      },

      /**
       * 回答下方的信息条：告诉用户这次是"只查了论坛"还是"还联网了"。
       * 这是需求里"必须让用户知道信息来自哪里"的直接体现。
       */
      metaLine() {
        const m = this.message;
        if (m.role !== "assistant" || m.error) {
          return [];
        }
        const line = [];
        if (m.forumHitCount) {
          line.push({icon: "database", text: `论坛命中 ${m.forumHitCount} 条`});
        }
        if (m.usedWebSearch) {
          line.push({icon: "global", text: "已联网补充"});
        } else if (m.webSearchEnabled === false) {
          line.push({icon: "global", text: "未开启联网"});
        }
        if (m.answerScore) {
          line.push({icon: "safety-certificate", text: `质量分 ${Number(m.answerScore).toFixed(2)}`});
        }
        return line;
      },
    },

    methods: {
      isExternal(url) {
        return /^https?:\/\//i.test(url || "");
      },

      copy() {
        const text = this.message.content || "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(() => {
            this.$message.success("已复制回答");
          }).catch(() => {
            this.$message.warning("复制失败，请手动选择文本");
          });
        } else {
          const el = document.createElement("textarea");
          el.value = text;
          document.body.appendChild(el);
          el.select();
          document.execCommand("copy");
          document.body.removeChild(el);
          this.$message.success("已复制回答");
        }
      },

      previewImage(src) {
        this.$emit("preview", src);
      },
    },
  };
</script>

<style lang="less" scoped>
  /* 沙金配色：与论坛主色 #D4AF37 同一色系 */
  @sand-50: #FFFDF7;
  @sand-100: #FBF4E6;
  @sand-200: #F3E7CE;
  @gold: #D4AF37;
  @gold-deep: #B8952C;
  @ink: #3D3A34;
  @ink-soft: #6B6558;

  .bot-message {
    display: flex;
    align-items: flex-start;
    margin-bottom: 18px;

    &.bot-message-user {
      flex-direction: row-reverse;

      .bot-bubble-wrap {
        align-items: flex-end;
      }
    }

    &.bot-message-system {
      justify-content: center;
      margin: 10px 0 18px;
    }
  }

  .bot-avatar {
    flex: 0 0 auto;
    width: 36px;
    height: 36px;
    border-radius: 50%;
    overflow: hidden;
    background: @sand-100;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px rgba(180, 150, 60, 0.18);

    img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .bot-avatar-bot {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      color: #fff;
      background: linear-gradient(135deg, @gold 0%, @gold-deep 100%);
    }
  }

  .bot-bubble-wrap {
    display: flex;
    flex-direction: column;
    // 注意：Less 2.x 会尝试计算 calc() 内部的表达式（把 100% - 56px 算坏），
    // 所以这里必须用 ~"..." 原样输出
    max-width: ~"calc(100% - 56px)";
    margin: 0 12px;
  }

  .bot-bubble {
    position: relative;
    padding: 12px 16px;
    border-radius: 12px;
    background: #fff;
    border: 1px solid @sand-200;
    box-shadow: 0 1px 2px rgba(120, 100, 40, 0.04), 0 6px 18px rgba(120, 100, 40, 0.06);
    color: @ink;
    font-size: 14px;
    line-height: 1.75;
    word-break: break-word;
    overflow: hidden;
  }

  .bot-message-user .bot-bubble {
    background: linear-gradient(135deg, #FBF1D8 0%, #F6E5BC 100%);
    border-color: #EAD9A8;
  }

  .bot-text-plain {
    white-space: pre-wrap;
  }

  .bot-user-image {
    margin-bottom: 8px;

    img {
      max-width: 240px;
      max-height: 240px;
      border-radius: 8px;
      cursor: zoom-in;
      border: 1px solid @sand-200;
      display: block;
    }
  }

  /* 生成中的光标 */
  .bot-caret {
    display: inline-block;
    width: 7px;
    height: 15px;
    margin-left: 2px;
    vertical-align: -2px;
    background: @gold;
    animation: bot-blink 1s steps(2, start) infinite;
  }

  @keyframes bot-blink {
    to {
      visibility: hidden;
    }
  }

  .bot-system {
    display: inline-flex;
    align-items: center;
    padding: 5px 14px;
    border-radius: 14px;
    background: @sand-100;
    border: 1px solid @sand-200;
    color: @ink-soft;
    font-size: 12px;

    .anticon {
      margin-right: 6px;
      color: @gold-deep;
    }
  }

  .bot-meta-line {
    display: flex;
    flex-wrap: wrap;
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px dashed @sand-200;

    .bot-meta-item {
      display: inline-flex;
      align-items: center;
      margin-right: 14px;
      font-size: 12px;
      color: @ink-soft;

      .anticon {
        margin-right: 4px;
        color: @gold-deep;
      }
    }
  }

  .bot-citations {
    margin-top: 10px;
    padding: 8px 10px;
    background: @sand-50;
    border: 1px solid @sand-200;
    border-radius: 8px;

    .bot-citations-title {
      font-size: 12px;
      color: @ink-soft;
      margin-bottom: 4px;

      .anticon {
        margin-right: 4px;
        color: @gold-deep;
      }
    }

    ul {
      margin: 0;
      padding-left: 0;
      list-style: none;
    }

    li {
      font-size: 12px;
      line-height: 1.9;
      color: @ink-soft;

      a {
        color: @gold-deep;
        text-decoration: none;

        &:hover {
          text-decoration: underline;
        }
      }
    }

    .bot-cite-tag {
      display: inline-block;
      margin-right: 6px;
      padding: 0 5px;
      border-radius: 3px;
      font-size: 11px;

      &.is-forum {
        color: #8A6D1B;
        background: #FBF0D2;
      }

      &.is-web {
        color: #1F6F86;
        background: #E2F1F5;
      }
    }

    .bot-cite-author {
      margin-left: 4px;
      color: #A79E8A;
    }
  }

  .bot-images {
    margin-top: 10px;

    img {
      max-width: 200px;
      max-height: 200px;
      margin: 0 6px 6px 0;
      border-radius: 8px;
      border: 1px solid @sand-200;
      cursor: zoom-in;
    }
  }

  .bot-actions {
    display: flex;
    align-items: center;
    margin-top: 6px;
    padding-left: 4px;
    color: #B4AB97;
    font-size: 13px;

    .anticon {
      margin-right: 14px;
      cursor: pointer;

      &:hover {
        color: @gold-deep;
      }
    }

    .bot-elapsed {
      font-size: 12px;
    }
  }

  /* Markdown 正文样式（沙金风） */
  .markdown-body {
    /deep/ h1, /deep/ h2, /deep/ h3, /deep/ h4 {
      margin: 14px 0 8px;
      font-weight: 600;
      color: @ink;
      line-height: 1.4;
    }

    /deep/ h1 {
      font-size: 19px;
      padding-bottom: 6px;
      border-bottom: 1px solid @sand-200;
    }

    /deep/ h2 {
      font-size: 17px;
    }

    /deep/ h3 {
      font-size: 15px;
    }

    /deep/ p {
      margin: 8px 0;
    }

    /deep/ ul, /deep/ ol {
      margin: 8px 0;
      padding-left: 22px;
    }

    /deep/ li {
      margin: 3px 0;
    }

    /deep/ a {
      color: @gold-deep;
      text-decoration: none;
      border-bottom: 1px solid rgba(212, 175, 55, 0.4);

      &:hover {
        border-bottom-color: @gold-deep;
      }
    }

    /deep/ strong {
      color: #2E2B26;
      font-weight: 600;
    }

    /deep/ blockquote {
      margin: 10px 0;
      padding: 6px 12px;
      border-left: 3px solid @gold;
      background: @sand-50;
      color: @ink-soft;
    }

    /deep/ code {
      padding: 1px 5px;
      border-radius: 4px;
      background: #F7F2E6;
      color: #A8621B;
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      font-size: 13px;
    }

    /deep/ pre {
      margin: 10px 0;
      padding: 12px 14px;
      border-radius: 8px;
      background: #2F2C26;
      overflow-x: auto;

      code {
        padding: 0;
        background: transparent;
        color: #F2E9D5;
        font-size: 12.5px;
        line-height: 1.6;
      }
    }

    /deep/ table {
      width: 100%;
      margin: 10px 0;
      border-collapse: collapse;
      font-size: 13px;
    }

    /deep/ th, /deep/ td {
      padding: 7px 10px;
      border: 1px solid @sand-200;
      text-align: left;
    }

    /deep/ th {
      background: @sand-100;
      font-weight: 600;
    }

    /deep/ tr:nth-child(even) td {
      background: #FEFBF4;
    }

    /deep/ img {
      max-width: 100%;
      border-radius: 8px;
    }

    /deep/ hr {
      margin: 14px 0;
      border: none;
      border-top: 1px dashed @sand-200;
    }
  }
</style>
