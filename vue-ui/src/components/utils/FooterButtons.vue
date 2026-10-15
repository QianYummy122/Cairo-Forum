<template>
  <div class="footer-buttons">
    <!-- 回到顶部 -->
    <div v-show="showTop" class="fb-item fb-backtop" @click="backToTop">
      <i class="iconfont icon-backTop"></i>
      <span class="fb-tip">{{ $t("common.backToTop") }}</span>
    </div>

    <!-- 反馈 -->
    <div class="fb-item fb-feedback" @click="createFeedback">
      <i class="iconfont icon-bug"></i>
      <span class="fb-tip">{{ $t("common.feedback") }}</span>
    </div>

    <!-- 管理员微信 -->
    <div class="fb-item fb-qr fb-wechat" :class="{active: activeQr === 'wechat'}"
         @click.stop="toggleQr('wechat')">
      <i class="iconfont icon-weixin"></i>
      <span class="fb-tip">{{ $t("common.adminWechat") }}</span>
      <transition name="qr-fade">
        <div v-if="activeQr === 'wechat'" class="fb-qr-card" @click.stop>
          <i class="fb-qr-arrow"></i>
          <p class="fb-qr-title">{{ $t("common.adminWechat") }}</p>
          <img class="fb-qr-img" :src="wechatQr" alt="WeChat QR"/>
          <p class="fb-qr-tip">{{ $t("common.scanTip") }}</p>
        </div>
      </transition>
    </div>

    <!-- 管理员QQ -->
    <div class="fb-item fb-qr fb-qq" :class="{active: activeQr === 'qq'}"
         @click.stop="toggleQr('qq')">
      <i class="iconfont icon-QQ-circle-fill"></i>
      <span class="fb-tip">{{ $t("common.adminQq") }}</span>
      <transition name="qr-fade">
        <div v-if="activeQr === 'qq'" class="fb-qr-card" @click.stop>
          <i class="fb-qr-arrow"></i>
          <p class="fb-qr-title">{{ $t("common.adminQq") }}</p>
          <img class="fb-qr-img" :src="qqQr" alt="QQ QR"/>
          <p class="fb-qr-tip">{{ $t("common.scanTip") }}</p>
        </div>
      </transition>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      // 回到顶部按钮是否可见（滚动超过阈值时显示）
      showTop: false,
      // 当前展开的二维码卡片：'' | 'wechat' | 'qq'
      activeQr: "",
      wechatQr: require("@/assets/img/contactway/mywechat.jpg"),
      qqQr: require("@/assets/img/contactway/myqq.jpg"),
    };
  },

  methods: {
    // 监听页面滚动容器 #app，超过阈值时显示“回到顶部”
    onAppScroll() {
      const app = document.querySelector("#app");
      this.showTop = !!app && app.scrollTop > 600;
    },

    // 平滑滚回顶部
    backToTop() {
      const app = document.querySelector("#app");
      if (app) {
        app.scrollTo({top: 0, behavior: "smooth"});
      }
    },

    // 点击反馈：未登录先弹出登录框，已登录则新窗口跳转反馈页
    createFeedback() {
      if (this.$store.state.isLogin) {
        window.open((this.$store.state.manageDomain || "") + "/createFeedback", "_blank");
      } else {
        this.$store.state.loginVisible = true;
      }
    },

    // 点击微信/QQ 气泡：切换二维码卡片展开/收起
    toggleQr(type) {
      this.activeQr = this.activeQr === type ? "" : type;
    },

    // 点击页面其它任意位置时收起二维码卡片
    closeQr() {
      this.activeQr = "";
    },
  },

  mounted() {
    const app = document.querySelector("#app");
    if (app) {
      app.addEventListener("scroll", this.onAppScroll);
    }
    document.addEventListener("click", this.closeQr);
    this.onAppScroll();
  },

  beforeDestroy() {
    const app = document.querySelector("#app");
    if (app) {
      app.removeEventListener("scroll", this.onAppScroll);
    }
    document.removeEventListener("click", this.closeQr);
  },
};
</script>

<style lang="less">


.footer-buttons {
  position: fixed;
  right: 6.6rem;
  bottom: 10rem;
  z-index: 888;
  display: flex;
  flex-direction: column;
  align-items: flex-end;

  .icon-weixin{
    color:#9ACD32;
  }

  .icon-QQ-circle-fill{
    color:#00BFFF;
  }


  .fb-item {
    position: relative;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #fff;
    color: #404040;
    border-radius: 50%;
    border: 1px solid transparent;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    cursor: pointer;
    transition: border-color 0.18s, box-shadow 0.18s, transform 0.18s;

    i {
      font-size: 20px;
      line-height: 1;
    }

    // hover：主题色描边高亮
    &:hover {
      border-color: var(--theme-color, #D4AF37);
      box-shadow: 0 0 0 1px var(--theme-color, #D4AF37), 0 2px 8px rgba(0, 0, 0, 0.12);
      transform: scale(1.06);
    }
  }

  .fb-item + .fb-item {
    margin-top: 10px;
  }

  // 选中态（二维码卡片已弹出）：气泡保持主题色高亮
  .fb-item.active {
    border-color: var(--theme-color, #D4AF37);
    box-shadow: 0 0 0 1px var(--theme-color, #D4AF37), 0 2px 8px rgba(0, 0, 0, 0.12);

    i {
      color: var(--theme-color, #D4AF37);
    }
  }

  // 语义图标色：回到顶部用主题色，反馈用红色
  .fb-backtop i {
    color: var(--theme-color, #D4AF37);
  }

  .fb-feedback i {
    color: #f5222d;
  }

  // hover 时右侧弹出的文字提示
  .fb-tip {
    position: absolute;
    left: calc(100% + 12px);
    top: 50%;
    transform: translateY(-50%) translateX(6px);
    padding: 6px 10px;
    background: #333;
    color: #fff;
    font-size: 12px;
    line-height: 1;
    white-space: nowrap;
    border-radius: 6px;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transition: all 0.18s;
    z-index: 40;
  }

  .fb-item:hover .fb-tip {
    opacity: 1;
    visibility: visible;
    transform: translateY(-50%) translateX(0);
  }

  // 已弹出卡片的按钮不再显示文字提示，避免与卡片重叠
  .fb-item.active .fb-tip {
    display: none;
  }

  // 二维码卡片（带指向按钮的箭头）
  .fb-qr-card {
    position: absolute;
    right: calc(100% + 40px);
    top: 50%;
    transform: translateY(-50%);
    width: 158px;
    padding: 14px 12px 12px;
    background: #fff;
    border: 1px solid var(--theme-color, #D4AF37);
    border-radius: 12px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.18);
    text-align: center;
    z-index: 50;

    // 指向触发按钮的三角箭头（垂直居中于卡片右侧）
    .fb-qr-arrow {
      position: absolute;
      right: -6px;
      top: 50%;
      margin-top: -6px;
      width: 11px;
      height: 11px;
      background: #fff;
      border-top: 1px solid var(--theme-color, #D4AF37);
      border-right: 1px solid var(--theme-color, #D4AF37);
      transform: rotate(45deg);
    }

    .fb-qr-title {
      margin: 0 0 10px;
      font-size: 14px;
      font-weight: 700;
      color: #222;
      line-height: 1;
    }

    .fb-qr-img {
      display: block;
      width: 124px;
      height: 124px;
      margin: 0 auto;
      object-fit: cover;
      border-radius: 6px;
    }

    .fb-qr-tip {
      margin: 8px 0 0;
      font-size: 11px;
      color: #999;
      line-height: 1;
    }

  }



}

// 二维码卡片弹出/收起动画
.qr-fade-enter-active,
.qr-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.qr-fade-enter,
.qr-fade-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(8px);
}
</style>
