<template>
  <a-config-provider :locale="lang[$store.state.locale]">
    <!-- 注意：a-config-provider 只渲染默认插槽的第一个子节点（见其源码
         filterEmpty($slots.default)[0]），所以背景与 #app 必须包在同一个根节点里，
         否则 #app（整个应用）会被 ant 丢弃，只剩背景板 -->
    <div class="app-root">
      <iframe class="bg-iframe" :src="bgIframeSrc" aria-hidden="true" tabindex="-1"/>
      <div v-if="$store.state.width" id="app">
        <router-view/>
      </div>
      <!-- 全局点击星火特效：常驻最顶层，pointer-events:none 不拦截交互 -->
      <div ref="sparkLayer" class="spark-layer" aria-hidden="true"/>
    </div>
  </a-config-provider>
</template>

<script>
import {mapMutations} from "vuex";
import userService from "./service/userService";
import zh_CN from "ant-design-vue/lib/locale-provider/zh_CN";
import en_US from "ant-design-vue/lib/locale-provider/en_US";

export default {
  data() {
    return {
      lang: {
        zh_CN: zh_CN,
        en_US: en_US
      }
    };
  },
  computed: {
    // 背景 iframe 地址（public/backgroundHtml/bg.html，构建时原样拷到产物根目录）
    // 用 BASE_URL 前缀，兼容部署在子路径下
    bgIframeSrc() {
      return (process.env.BASE_URL || "/") + "backgroundHtml/bg.html";
    }
  },
  methods: {
    ...mapMutations(["changeColor"]),
    // 初始化获取用户权限状态
    getAccess() {
      userService.getCurrentUserAccess()
          .then(res => {
            /**
             * @function checkErrorPage 判断当前是否在500页面刷新，如果是，刷新后如果返回{code: 200},则跳转到首页
             */
            this.checkErrorPage(res);
            if (res.code === 0) {
              this.$store.state.userId = res.data.userId;
              this.$store.state.isLogin = true;
              res.data.roles.forEach(data => {
                // 是超级管理员
                if (data.grade === 'NS_SUPER_ADMIN_ROLE') {
                  this.$store.state.isManage = true;
                }
              })
            }
          })
          .catch((err) => {
            // this.$message.error(err.desc);
          });
    },
    // 获取所有管理员用户id，用于头像上的“会员”标识展示
    getAdminUserIds() {
      userService.getAdminUserIds()
          .then(res => {
            this.$store.state.adminUserIds = res.data || [];
          })
          .catch(() => {
            // 后端不可用等情况静默失败，仅不展示会员标识
          });
    },
    // 初始化页面。获取屏幕尺寸以及监听屏幕尺寸
    initDom() {
      // 在Vue中this始终指向Vue，但一些其他组件如axios中this为undefined,通过let that = this将this保存在that中，再在函数中使用that均可
      const that = this;

      function setWidth() {
        that.$store.state.width = window.innerWidth;
        that.$store.state.height = window.innerHeight;
        // 900/1050
        that.$store.state.collapsed = window.innerWidth < 1000;
        that.$store.state.collapsedMax = window.innerWidth < 1300;
      }

      // 立即执行一次，保证 width>0、内层 #app（v-if="width"）能渲染。
      // 之前只挂在 window.onload 上，若 Vue 在 load 之后才挂载（热更新/慢资源），
      // 该一次性事件永不触发 → width 一直为 0 → 内容不渲染，只剩背景板。
      setWidth();
      window.onresize = setWidth;
      window.onload = setWidth;
    },
    checkErrorPage() {
      // 如果当前是服务器错误（500页面），刷新后自动跳转到首页
      if (this.$route.path === "/500") {
        this.$router.push({path: "/"});
      }
    },
    /**
     * @function setLanguageAndTheme 设置语言和主题色（尝试从localStorage获取，没有就使用默认值）
     */
    setLanguageAndTheme() {
      let navLanguage;
      if (navigator.language === "zh-CN") {
        navLanguage = "zh_CN";
      } else {
        navLanguage = "en_US";
      }
      this.$store.state.locale = localStorage.language ? localStorage.language : navLanguage;
      this.changeColor(localStorage.themeColor || "#D4AF37");
    },
    setIsCarousel() {
      // 禁用
      if (Number(window.localStorage.isCarousel) === 0) {
        this.$store.state.isCarousel = 0;
      } else {
        this.$store.state.isCarousel = 1;
      }
    },

    // ===== 全局点击星火特效 =====
    // 页面任意位置点击，在最顶层绽放一圈金色星点并消散
    onGlobalClick(e) {
      // 尊重系统“减弱动态效果”偏好
      if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        return;
      }
      this.spawnSpark(e.clientX, e.clientY);
    },
    spawnSpark(x, y) {
      const layer = this.$refs.sparkLayer;
      if (!layer || typeof x !== "number") return;
      // 旧浏览器无 Web Animations，则静默不做特效
      if (!Element || !Element.prototype.animate) return;

      const burst = document.createElement("span");
      burst.className = "spark-burst";
      burst.style.left = x + "px";
      burst.style.top = y + "px";
      layer.appendChild(burst);

      const colors = ["#000000", "#778899", "#000000", "#000000"];
      const count = 6 + Math.floor(Math.random() * 3);
      for (let i = 0; i < count; i++) {
        const dot = document.createElement("i");
        const ang = Math.random() * Math.PI * 2;
        const dist = 20 + Math.random() * 26;
        const dx = Math.cos(ang) * dist;
        const dy = Math.sin(ang) * dist - 8; // 略微向上飘
        const size = 2.5 + Math.random() * 3.5;
        const color = colors[i % colors.length];
        dot.className = "spark-dot";
        dot.style.width = size + "px";
        dot.style.height = size + "px";
        dot.style.background = color;
        dot.style.boxShadow = "0 0 6px 1px " + color;
        burst.appendChild(dot);

        const anim = dot.animate(
          [
            {transform: "translate(-50%, -50%) translate(0, 0) scale(1)", opacity: 1},
            {transform: "translate(-50%, -50%) translate(" + dx + "px, " + dy + "px) scale(0.2)", opacity: 0}
          ],
          {duration: 380 + Math.random() * 220, easing: "cubic-bezier(0, 0.6, 0.4, 1)"}
        );
        anim.onfinish = () => dot.remove();
      }

      // 点击处一圈柔光
      const ring = document.createElement("i");
      ring.className = "spark-ring";
      burst.appendChild(ring);
      const ringAnim = ring.animate(
        [
          {transform: "translate(-50%, -50%) scale(0.2)", opacity: 0.7},
          {transform: "translate(-50%, -50%) scale(1.4)", opacity: 0}
        ],
        {duration: 320, easing: "ease-out"}
      );
      ringAnim.onfinish = () => ring.remove();

      // 兜底清理节点
      window.setTimeout(() => burst.remove(), 800);
    }
  },
  created() {
    this.setLanguageAndTheme();
    this.setIsCarousel();
  },
  mounted() {
    // 初始化dom，获取用户界面宽高，并且添加监听
    this.initDom();
    // 获取用户权限，判断用户是否是登录状态
    this.getAccess();
    // 获取管理员用户id（头像“会员”标识）
    this.getAdminUserIds();
    // 全局点击星火
    document.addEventListener("click", this.onGlobalClick);
  },
  beforeDestroy() {
    document.removeEventListener("click", this.onGlobalClick);
  }
};
</script>

<style>
:root {
  --theme-color: #D4AF37;
}

/* a-config-provider 只保留唯一根节点；此处作为整棵应用的单根容器，
   height:100% 让内层 #app（height:100%）的高度链保持成立 */
.app-root {
  height: 100%;
}

/* ===== 全局点击星火特效层 ===== */
.spark-layer {
  position: fixed;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  pointer-events: none; /* 不拦截任何点击/选择/滚动 */
  z-index: 100000;      /* 处于页面最顶层，覆盖顶栏/弹窗/抽屉 */
}
.spark-layer .spark-burst {
  position: absolute;
  width: 0;
  height: 0;
}
.spark-layer .spark-dot {
  position: absolute;
  left: 0;
  top: 0;
  border-radius: 50%;
}
.spark-layer .spark-ring {
  position: absolute;
  left: 0;
  top: 0;
  width: 34px;
  height: 34px;
  border: 2px solid rgba(14, 12, 2, 0.55);
  border-radius: 50%;
}

/* antd 默认给 .ant-layout 一个不透明灰底 #f0f2f5，会整片盖住背景粒子板；
   此处全局透明化，让粒子板透过各页面布局透出（卡片/面板自身白底不受影响） */
.ant-layout {
  background: transparent !important;
}

/* ===== 磨砂玻璃卡片（全站内容卡片统一） =====
   半透明白 + backdrop 模糊，让粒子背景从卡片里透出并被虚化成磨砂效果。
   覆盖：
   1) 模板中以“内联 background:#fff”呈现的卡片/面板
      （大量面板组件通过 style 把白色底打到自己的根元素上）
   2) .info-box（资源/标签信息卡）
   顶部白色导航条（.ant-layout-header / .main-header）刻意保留不透明白，不在此列。 */
#app [style*="background:#fff"],
#app [style*="background: #fff"],
#app [style*="background:#FFF"],
#app [style*="background: #FFF"],
#app [style*="background:white"],
#app [style*="background: white"],
#app [style*="background:#ffffff"],
#app [style*="background: #ffffff"],
#app .info-box {
  background-clip: padding-box;
  background: rgba(255, 255, 255, 0.35) !important;
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
}

/* 不支持 backdrop-filter 的浏览器：半透明会看不清文字，退回高不透明白 */
@supports not ((backdrop-filter: blur(4px)) or (-webkit-backdrop-filter: blur(4px))) {
  #app [style*="background:#fff"],
  #app [style*="background: #fff"],
  #app [style*="background:#FFF"],
  #app [style*="background: #FFF"],
  #app [style*="background:white"],
  #app [style*="background: white"],
  #app [style*="background:#ffffff"],
  #app [style*="background: #ffffff"],
  #app .info-box {
    background-clip: padding-box;
    background: rgba(255, 255, 255, 0.85) !important;
  }
}

/* ===== 磨砂玻璃扩展：顶部导航 / 底部悬浮条 / 弹窗浮层 =====
   统一手法：半透明白 + backdrop 模糊。顶栏与底部按钮用中透明(0.55~0.6)，
   弹窗/浮层涉及输入阅读，用高透明(0.88)保可读。粒子板与滚动内容都会被虚化，形成磨砂。 */

/* 1) 顶部导航栏：让滚动内容从半透明条下透出并虚化 */
#app .header {
  background: rgba(255, 255, 255, 0.55) !important;
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
}
/* .main-header 本身是不透明白，会盖住根元素的玻璃，改为透明透出 */
#app .main-header {
  background: transparent !important;
}

/* 1.5) 顶栏菜单（IndexMenu）：ant 默认给 .ant-menu 整块不透明白底，
   与磨砂顶栏割裂，改为透明融入玻璃（选中/悬停仍用文字色与主题态区分） */
#app .header .ant-menu,
#app .header-left-content .ant-menu {
  background: transparent !important;
}

/* 2) 底部悬浮操作按钮 + 二维码卡片 */
.fb-item {
  background: rgba(255, 255, 255, 0.6) !important;
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
}
.fb-qr-card {
  background: rgba(255, 255, 255, 0.88) !important;
  backdrop-filter: blur(16px) saturate(150%);
  -webkit-backdrop-filter: blur(16px) saturate(150%);
}

/* 3) 弹窗 / 浮层：ant 弹层通常渲染在 body 下，需无 #app 前缀 */
.ant-modal-content,
.ant-drawer-content,
.ant-popover-inner,
.ant-dropdown-menu {
  background: rgba(255, 255, 255, 0.88) !important;
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
}
/* 头部/内容贴合玻璃底，避免再叠一层白 */
.ant-modal-header,
.ant-drawer-header,
.ant-popover-title,
.ant-modal-body,
.ant-drawer-body,
.ant-popover-inner-content {
  background: transparent !important;
}
/* 下拉项 hover 用主题金低透明高亮，与玻璃协调 */
.ant-dropdown-menu-item:hover {
  background-color: rgba(212, 175, 55, 0.14) !important;
}

/* ===== 玻璃面板外观统一：圆角 + 发丝亮边 + 柔和投影 =====
   让首页/标签/资源/关于等页面的白色内容块与顶栏是同一套“玻璃面板”材质：
   圆角使大块不再像“贴纸”，发丝边+柔和投影把它们从粒子底上抬起来、更有层次。 */
#app [style*="background:#fff"],
#app [style*="background: #fff"],
#app [style*="background:#FFF"],
#app [style*="background: #FFF"],
#app [style*="background:white"],
#app [style*="background: white"],
#app [style*="background:#ffffff"],
#app [style*="background: #ffffff"],
#app .info-box {
  border-radius: 10px;
  border: 1px solid rgba(31, 34, 41, 0.16);
  box-shadow: 0 1px 2px rgba(31, 34, 41, 0.04),
              0 10px 30px rgba(31, 34, 41, 0.06);
}

/* 顶栏与内容交界更柔和：给顶栏底部一个轻投影，让它“浮”在内容之上而非生硬切换 */
#app .header {
  box-shadow: 0 2px 14px rgba(31, 34, 41, 0.08);
}

/* ===== About 页元素 ===== */
#about-index .about_content > div {
  background: rgba(255, 255, 255, 0.35) !important;
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  /* 发丝边框：中性浅灰 1px，让过于透明的卡边缘可辨 */
  border: 1px solid rgba(31, 34, 41, 0.16);
}

/* 不支持 backdrop-filter 的浏览器：浮层退回高不透明白 */
@supports not ((backdrop-filter: blur(4px)) or (-webkit-backdrop-filter: blur(4px))) {
  #app .header,
  .fb-item,
  .fb-qr-card,
  .ant-modal-content,
  .ant-drawer-content,
  .ant-popover-inner,
  .ant-dropdown-menu {
    background: rgba(255, 255, 255, 0.92) !important;
  }
}

/* 背景粒子板：iframe 承载 public/backgroundHtml/bg.html（其内部的
   particles.min.js / 1.js 在 iframe 文档中会原生执行）。
   放在 z-index:-1 位于内容之下；配合 #app 透明背景，粒子板才可见。 */
.bg-iframe {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  border: 0;
  margin: 0;
  padding: 0;
  z-index: -1;
  pointer-events: none; /* 仅作背景，不拦截滚动与点击 */
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: auto;
  /* 由原先不透明 #f0f2f5 改为透明，露出背景粒子板 */
  background: transparent;
}

/* 默认宽度有：width: 1100px;和width: 900px;两种 */

/* 头像上的“会员/管理员”标识（右上角 icon-huiyuan）
   默认 14px（不随头像缩放）。各组件可在 <i> 上用内联 font-size 单独设置该处的大小。
   （注意：不要在这里加 !important，否则会覆盖各组件的内联设置。） */
.member-avatar {
  position: relative;
  display: inline-block;
  flex-shrink: 0;
}

.member-badge {
  position: absolute;
  top: 0;
  left: 100%;
  transform: translate(-75%, -30%);
  font-size: 14px;
  line-height: 1;
  color: #D4AF37;
  text-shadow: 0 0 2px #fff, 0 0 2px #fff, 0 0 2px #fff;
  z-index: 2;
  pointer-events: none;
}
</style>
