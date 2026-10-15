<template>
  <a-layout id="bot-index">
    <IndexHeader class="header"/>

    <a-layout-content>
      <main class="content">
        <!-- 页面标题：呼应"沙滩泛金"的整体色调 -->
        <div class="bot-hero">
          <div class="bot-hero-text">
            <h1>
              小罗Bot
              <span class="bot-hero-badge">AI 搜索引擎</span>
            </h1>
            <p>
              先把开罗论坛翻一遍，翻不到再上网帮你找 —— 一个会自己决定"去哪儿找答案"的智能体。
            </p>
          </div>
          <div class="bot-hero-stats" v-if="stats.length">
            <div v-for="(item, index) in stats" :key="index" class="bot-hero-stat">
              <strong>{{ item.value }}</strong>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </div>

        <BotChat :default-web-search="defaultWebSearch"/>
      </main>
    </a-layout-content>

    <FooterButtons v-if="!$store.state.collapsed"/>
  </a-layout>
</template>

<script>
  import IndexHeader from "@/components/index/head/IndexHeader";
  import FooterButtons from "@/components/utils/FooterButtons";
  import BotChat from "@/components/bot/BotChat";

  export default {
    name: "BotIndex",

    components: {IndexHeader, FooterButtons, BotChat},

    data() {
      return {
        // 联网搜索默认关闭：由用户在页面上按需开启（对应用户需求 6）
        defaultWebSearch: false,
        stats: [],
      };
    },

    mounted() {
      // 读一次知识库规模，做成页面上的小统计；失败就安静地不显示
      const savedWeb = window.localStorage.getItem("botWebSearch");
      this.defaultWebSearch = savedWeb === "1";

      import("@/service/aiBotService").then(({default: aiBotService}) => {
        aiBotService.kbStatus()
            .then((res) => {
              const data = res.data || {};
              const byType = data.bySourceType || {};
              this.stats = [
                {label: "知识条目", value: data.total || 0},
                {label: "论坛文章", value: byType.article || 0},
                {label: "评论 / 资源", value: (byType.comment || 0) + (byType.resource || 0)},
              ];
            })
            .catch(() => {
              this.stats = [];
            });
      });
    },
  };
</script>

<style>
  /* 页面级样式沿用论坛既有约定：根 id 选择器 + 非 scoped，方便覆盖 antd 内部样式 */
  #bot-index .header {
    position: fixed;
    z-index: 999;
    width: 100%;
    background: #fff;
    border-bottom: 1px solid #00000021;
  }

  #bot-index .ant-layout-header {
    background: #fff;
    height: auto;
    line-height: 2.3;
  }

  #bot-index .ant-layout-header,
  #bot-index .ant-layout-content {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* 内容区做成纵向 flex：hero 固定高度，聊天卡片用 flex 吃掉剩余空间，
     这样输入框永远贴在视口底部，不会被挤到屏幕外（也就不用给聊天卡片写死高度）。
     这里是纯 CSS（不是 Less），calc() 可以放心用。 */
  #bot-index .ant-layout-content {
    align-items: stretch;
    min-height: 0;
  }

  #bot-index .content {
    display: flex;
    flex-direction: column;
    margin-top: 72px;
    margin-bottom: 20px;
    width: 100%;
    max-width: 1100px;
    padding: 0 12px;
    box-sizing: border-box;
    height: calc(100vh - 92px);
    min-height: 560px;
    position: relative;
  }

  /* 沙滩"底板"：论坛全局样式里 `.ant-layout { background: transparent !important }`，
     页面根节点（a-layout）上的背景会被强制抹掉，只剩 webpack 粒子背景。
     所以这里用 ::before 在内容列下方铺一层半透明沙色渐变 ——
     既让 hero 标题和聊天卡片在粒子背景上有足够对比度，又保留论坛原有的粒子质感。 */
  #bot-index .content::before {
    content: "";
    position: absolute;
    top: -14px;
    right: -10px;
    bottom: -6px;
    left: -10px;
    border-radius: 20px;
    background: linear-gradient(180deg,
      rgba(255, 251, 240, 0.78) 0%,
      rgba(253, 244, 226, 0.62) 45%,
      rgba(248, 235, 211, 0.5) 100%);
    box-shadow: 0 18px 50px rgba(150, 120, 40, 0.08);
    pointer-events: none;
    z-index: 0;
  }

  #bot-index .content > * {
    position: relative;
    z-index: 1;
  }

  /* ================= 沙滩泛金 主题 ================= */
  /* 与论坛主色 #D4AF37（镀金）同源，把"背景"整体换成沙滩暖金，
     对应 DeepSeek 官网那种"整页统一底色 + 居中主区域"的观感。
     注意：根节点 a-layout 的背景被 App.vue 的
     `.ant-layout { background: transparent !important }` 强制透明，
     所以底色铺在 .content::before 上（见上方），这里只兜一个渐变给不支持伪元素的场景。 */
  #bot-index {
    background: radial-gradient(120% 80% at 50% 0%, #FFF9EC 0%, #FDF3E0 38%, #F8EBD3 100%);
    min-height: 100vh;
  }

  #bot-index .bot-hero {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex: 0 0 auto;
    margin-bottom: 14px;
    padding: 4px 4px 0;
  }

  #bot-index .bot-hero-text h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 700;
    color: #3D3A34;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
  }

  #bot-index .bot-hero-badge {
    margin-left: 10px;
    padding: 2px 9px;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 500;
    color: #8A6D1B;
    background: linear-gradient(135deg, #FBEFCF 0%, #F4E0AC 100%);
    border: 1px solid rgba(212, 175, 55, 0.4);
  }

  #bot-index .bot-hero-text p {
    margin: 6px 0 0;
    font-size: 13px;
    color: #8B8272;
    line-height: 1.7;
  }

  #bot-index .bot-hero-stats {
    display: flex;
    flex: 0 0 auto;
  }

  #bot-index .bot-hero-stat {
    min-width: 76px;
    padding: 6px 14px;
    margin-left: 10px;
    text-align: center;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid rgba(212, 175, 55, 0.25);
  }

  #bot-index .bot-hero-stat strong {
    display: block;
    font-size: 18px;
    color: #B8952C;
    line-height: 1.3;
  }

  #bot-index .bot-hero-stat span {
    font-size: 11px;
    color: #8B8272;
  }

  /* 聊天主区域：白底卡片 + 沙金描边，和论坛其它页面的卡片观感一致 */
  #bot-index .bot-chat {
    box-shadow: 0 1px 2px rgba(120, 100, 40, 0.05), 0 14px 40px rgba(150, 120, 40, 0.1);
    border: 1px solid rgba(212, 175, 55, 0.22);
  }

  /* 滚动条换成沙金色（全局滚动条是论坛主色，这里单独微调容器内部） */
  #bot-index .bot-messages::-webkit-scrollbar,
  #bot-index .bot-trace-body::-webkit-scrollbar {
    width: 6px;
  }

  #bot-index .bot-messages::-webkit-scrollbar-thumb,
  #bot-index .bot-trace-body::-webkit-scrollbar-thumb {
    background: rgba(212, 175, 55, 0.5);
    border-radius: 3px;
  }

  @media screen and (max-width: 900px) {
    #bot-index .content {
      margin-top: 64px;
      margin-bottom: 0;
      padding: 0 6px;
      height: calc(100vh - 70px);
      min-height: 480px;
    }

    #bot-index .bot-hero {
      flex-direction: column;
      align-items: flex-start;
    }

    #bot-index .bot-hero-stats {
      margin-top: 10px;
    }

    #bot-index .bot-hero-stat:first-child {
      margin-left: 0;
    }
  }
</style>
