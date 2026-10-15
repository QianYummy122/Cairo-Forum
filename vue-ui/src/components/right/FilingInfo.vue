<template>
  <div class="div-content">
    <a-row>
      <a-tooltip placement="bottom">
        <template slot="title">
          {{ $t("common.getTheWord") }}
        </template>
        <a-col class="user_agreement" :span="6" @click="designDocument">{{ $t("common.designDocument") }}</a-col>
      </a-tooltip>
      <a-col class="user_guidance" :span="6">
        <a href="https://www.bilibili.com/video/BV1he4y1C7rk?spm_id_from=333.999.0.0&vd_source=d0a5d07985a7fbbfb889c874632343c6" target="_blank">{{ $t("common.userGuidance") }}</a>
      </a-col>
      <a-col class="links" :span="6">
        <a href="https://juejin.cn/" target="_blank">{{ $t("common.links") }}</a>
      </a-col>
      <a-col class="about_us" :span="6" @click="routerAbout">{{ $t("common.about") }}</a-col>
    </a-row>
    <a-row>
      版权 © <a href="/" target="_blank"> 开罗论坛 </a>丨
      <a href="https://beian.miit.gov.cn" target="_blank">蜀ICP备19014736号-1 </a>
    </a-row>
  </div>
</template>

<script>
export default {
  name: "FilingInfo",

  methods: {
    designDocument() {
      window.open('https://XXX.doc', '_blank');
      // this.$message.warning(this.$t("common.excuseMe"));
      // this.$confirm({
      //   centered: true,
      //   title: this.$t("common.learnHowToGetCairoPoints"),
      //   content: this.$t("common.excuseMe"),
      //   onOk: () => {
      //     this.routerBook();
      //   },
      // });
    },

    // 路由到Book说明页面
    routerBook() {
      window.open('/book', '_blank');
    },

    // 点击跳转到 关于我们 页面
    routerAbout() {
      window.open('/about', '_blank');
    }
  }
}
</script>

<style scoped>
.div-content {
  margin-left: 20px;
}

.div-content, a {
  font-size: 12px;
  line-height: 2;
  color: #909090;
  cursor: pointer;
}

.user_agreement:hover, .user_guidance:hover, .links:hover, .about_us:hover, a:hover {
  color: var(--theme-color, #D4AF37);
}

</style>
