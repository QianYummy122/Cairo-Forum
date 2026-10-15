<template>
  <div class="header-left-content">
    <a-menu v-model="current" :mode="$store.state.collapsed ? 'inline' : 'horizontal'">
      <!-- 首页 -->
      <a-menu-item key="frontPage" @click="refresh">{{ $t("common.home") }}</a-menu-item>
      <!-- 标签 -->
      <a-menu-item key="boilingPoint" @click="routerLabel">{{ $t("common.label") }}</a-menu-item>
      <!-- 资源 -->
      <a-menu-item key="liveStreaming" @click="routerResource">{{ $t("common.resource") }}</a-menu-item>

      <!-- 作者榜 -->
      <a-menu-item key="authorList" @click="routerAuthorList" v-if="$store.state.collapsed">{{ $t("common.authorList") }}</a-menu-item>
      <!-- 最新评论 -->
      <a-menu-item key="commentDonate" @click="routerCommentDonate" v-if="$store.state.collapsed">{{ $t("common.commentDonate") }}</a-menu-item>
      <!-- 写文章 -->
      <a-menu-item key="writeArticle" @click="routerWriteArticle" v-if="$store.state.collapsed">{{ $t("common.writeArticle") }}</a-menu-item>
      <a-divider style="margin: 3px 0 3px 0" v-if="$store.state.collapsed"/>
      <!-- 关于 -->
      <a-menu-item key="about" @click="routerAbout">{{ $t("common.about") }}</a-menu-item>
      <!-- 小罗Bot（AI搜索引擎） -->
      <a-menu-item key="bot" @click="routerBot">
        <span class="bot-menu-item">
          <i class="iconfont icon-chat"></i>
          <span>{{ $t("common.bot") }}</span>
        </span>
      </a-menu-item>
      <!-- 国际化 -->
      <a-menu-item key="globalization" @click="changeLanguage" v-if="$store.state.collapsed">
        <a-icon type="global"/>
        <span>{{ languageTitle }}</span>
      </a-menu-item>
    </a-menu>
  </div>
</template>

<script>
  export default {
    name: "",

    data() {
      return {
        current: ['frontPage'],
      }
    },

    computed: {
      languageTitle() {
        if (this.$store.state.locale === "en_US") {
          return "中文";
        }
        return "English";
      }
    },

    methods: {
      // 设置语言
      changeLanguage() {
        if (this.$store.state.locale === "zh_CN") {
          this.$store.state.locale = "en_US";
          localStorage.language = "en_US";
        } else {
          this.$store.state.locale = "zh_CN";
          localStorage.language = "zh_CN";
        }
      },

      // 刷新
      refresh() {
        // 跳转到首页
        this.$router.push('/');
      },

      // 路由到标签页面
      routerLabel() {
        this.$router.push("/label");
      },

      // 路由到资源导航页面
      routerResource() {
        this.$router.push("/resource");
      },

      // 路由到小罗Bot（AI搜索引擎）页面
      routerBot() {
        this.$router.push("/bot");
      },

      // 路由到作者榜页面
      routerAuthorList() {
        this.$router.push("/recommended");
      },

      // 路由到写文章页面
      routerWriteArticle() {
        this.$router.push("/write");
      },

      // 路由到最新评论页面
      routerCommentDonate() {
        this.$router.push("/commentDonate");
      },

      // 路由到关于页面
      routerAbout() {
        this.$router.push("/about");
      },
    },

    mounted() {
      let name = this.$route.name;

      // 清空数组
      this.current.pop();
      // 首页
      if (name === 'home') {
        // 添加新值
        this.current.push('frontPage');
      }
      // 标签
      if (name === 'label') {
        // 添加新值
        this.current.push('boilingPoint');
      }
      // 资源导航
      if (name === 'resource') {
        // 添加新值
        this.current.push('liveStreaming');
      }
      // 小罗Bot
      if (name === 'bot') {
        // 添加新值
        this.current.push('bot');
      }
      // 作者榜（手机）
      if (name === 'recommended') {
        // 添加新值
        this.current.push('authorList');
      }
      // 评论捐赠（手机）
      if (name === 'commentDonate') {
        // 添加新值
        this.current.push('commentDonate');
      }
      // 关于
      if (name === 'about') {
        // 添加新值
        this.current.push('about');
      }
    },
  }
</script>

<style lang="less" scoped>
  .header-left-content {
    display: flex;
    justify-content: left;
    align-items: center;
  }

  /* 小罗Bot 菜单项：图标与文字对齐（移动端抽屉里也一样） */
  .bot-menu-item {
    display: inline-flex;
    align-items: center;
    gap: 0px;
    padding: 0px 10px;
    border: 1.5px solid #7a7a5e48;       /* 边框颜色 */
    border-radius: 10px;               /* 圆角半径，值越大越圆 */
    background: rgba(240, 230, 140, 0.363); /* 轻微底色 */
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);        /* 平滑过渡动画 */
    margin: 5px 0px 0px 0px;

    .iconfont {
      margin-right: 4px;
      font-size: 14px;
    }
  }

  .bot-menu-item:hover {
    border-color: #7a7a5ebb;                /* 边框加深到约 73% */
    background: rgba(240, 230, 140, 0.329);  /* 底色从 0.363 → 0.62 */
    box-shadow: 0 2px 12px rgba(122, 122, 94, 0.12);   /* 同色系微光 */
  }

  /* -------- horizontal-start -------- */
  // 去掉a-menu组件的下划线
  .ant-menu-horizontal {
    border-bottom: 0;
  }
  // 去掉选中active加粗下划线
  .ant-menu-horizontal > .ant-menu-item-active, .ant-menu-horizontal > .ant-menu-item-open, .ant-menu-horizontal > .ant-menu-item-selected, .ant-menu-horizontal:not(.ant-menu-dark) > .ant-menu-item:hover, .ant-menu-horizontal > .ant-menu-submenu-active, .ant-menu-horizontal > .ant-menu-submenu-open, .ant-menu-horizontal:not(.ant-menu-dark) > .ant-menu-submenu-selected, .ant-menu-horizontal:not(.ant-menu-dark) > .ant-menu-submenu {
    border-bottom: 2px solid transparent;
  }
  /* 调整a-menu-item的padding */
  .ant-menu-item, .ant-menu-submenu-title {
    padding: 0 16px;
  }
  /* -------- horizontal-end -------- */

  /* -------- inline-start -------- */
  // 去掉a-menu组件的下划线
  .ant-menu-inline {
    border-right: 0;
  }
  // 去掉选中active加粗下划线
  .ant-menu-inline .ant-menu-item::after, .ant-menu-vertical .ant-menu-item::after, .ant-menu-vertical-left .ant-menu-item::after, .ant-menu-vertical-right .ant-menu-item::after {
    border-right: 3px solid transparent;
  }
  // 去掉选中active背景色
  .ant-menu:not(.ant-menu-horizontal) .ant-menu-item-selected {
    background-color: transparent;
  }
  /* -------- inline-end -------- */
</style>