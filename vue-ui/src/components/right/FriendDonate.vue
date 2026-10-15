<template>
  <div id="friend-donate">
    <header class="user-block-header friend-donate-toggle" @click="donateOpen = !donateOpen">
      <span>{{ $t("common.friendDonate") }}</span>
      <!-- 展开时显示“收起”图标，默认折叠时显示“折叠”图标 -->
      <i class="iconfont donate-toggle-icon" :class="donateOpen ? 'icon-shouqi' : 'icon-caozuo-zhedie'"></i>
    </header>
    <a-divider style="margin: 10px 0 0 0;"/>
    <div class="friend-donate-body friend-donate-collapse" :class="{ 'is-open': donateOpen }">
      <p>
        <small class="text-warning">{{ $t("common.donateContent1") }}</small>
        <br>
        <small class="text-warning">{{ $t("common.donateContent2") }}</small>
      </p>
      <!-- 境外收款 -->
      <div style="line-height: 30px; padding: 0 15px" v-if="$store.state.locale !== 'zh_CN'">
        <li><b>Where can I send money?</b></li>
        <small style="color: #8a919f">Alipay Cooperative overseas remittance platform: </small>
        <a href="https://remit.alipay.com" target="_blank">https://remit.alipay.com</a>
        <li><b>What information should I fill in at the money transfer platform?</b></li>
        <small style="color: #8a919f">Alipay ID: </small>
        <span :style="{color: $store.state.themeColor}">2949871488@qq.com</span><br/>
        <small style="color: #8a919f">Last Name: </small>
        <span :style="{color: $store.state.themeColor}">QIAN</span><br/>
        <small style="color: #8a919f">First Name: </small>
        <span :style="{color: $store.state.themeColor}">YIMING</span>
      </div>
      <!-- 中文收款码 -->
      <div class="donate" v-else>
        <a-tabs default-active-key="1">
          <a-tab-pane key="1" tab="随意">
            <!--我是土豪-->
            <div role="tabpanel" class="tab-pane" id="rmb-custom">
              <img src="@/assets/img/chinaPay/1.jpg" alt="微信" style="width: 100%">
            </div>
          </a-tab-pane>
          <a-tab-pane key="2" tab="😏">
            <!--我是土豪-->
            <div role="tabpanel" class="tab-pane" id="rmb-99">
              <img src="@/assets/img/chinaPay/2.jpg" alt="微信" style="width: 100%">
            </div>
          </a-tab-pane>
          <a-tab-pane key="3" tab="20 元" force-render>
            <!--20元-->
            <div role="tabpanel" class="tab-pane" id="rmb-20">
              <img src="@/assets/img/chinaPay/4.jpg" alt="微信" style="width: 100%">
            </div>
          </a-tab-pane>
          <a-tab-pane key="4" tab="10 元">
            <!--10元-->
            <div role="tabpanel" class="tab-pane active" id="rmb-10">
              <img src="@/assets/img/chinaPay/3.jpg" alt="微信" style="width: 100%">
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "FriendDonate",

  data() {
    return {
      // 是否展开友情捐赠内容（默认折叠）
      donateOpen: false,
    };
  },
};
</script>

<style lang="less">

#friend-donate {
  padding-bottom: 10px;

  .user-block-header {
    padding: 15px 10px 0 15px;
  }

  // 友情捐赠标题整行可点击展开/收起
  .friend-donate-toggle {
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    user-select: none;

    &:hover {
      color: var(--theme-color, #D4AF37);

      .donate-toggle-icon {
        color: var(--theme-color, #D4AF37);
      }
    }

    .donate-toggle-icon {
      color: #8a919f;
      font-size: 12px;
      margin-right: 6px;
    }
  }

  // 展开/折叠的插值过渡：用 max-height + opacity 模拟高度动画
  .friend-donate-collapse {
    overflow: hidden;
    max-height: 0;
    opacity: 0;
    transition: max-height .45s ease, opacity .4s ease;

    &.is-open {
      max-height: 900px;
      opacity: 1;
    }
  }

  .friend-donate-body {
    .text-warning {
      color: #8a6d3b;
      line-height: 30px;
    }

    .text-info {
      color: #31708f;
      line-height: 30px;
    }
  }

  p {
    padding: 15px 15px 0 15px;
  }
}

#friend-donate .ant-tabs-nav .ant-tabs-tab {
  margin: 0;
}
</style>
