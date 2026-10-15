<template>
  <a-layout>
    <a-layout id="about-index">
      <IndexHeader class="header"/>
      <a-layout-content>
        <main class="about_content" :style="$store.state.collapsed ? 'width: 100%;' : 'width: 800px;'">
          <div style="background: #fff; margin-bottom: 10px">
            <section class="mission">
              <div class="inner">
                <div class="mission-content">
                  <div class="title">目的</div>
                  <div class="sub">开罗论坛旨在打造一个国内<span style="color: #cb2222">跨学科</span>小众社区，给<span style="color: #cb2222">复合型</span>爱好者提供深度长文分享、理性交流的独立阵地。
                  </div>
                  <div class="sub">兼顾<span style="color: #cb2222">技术理性、社会现实与人文思想</span>，沉淀有留存价值的知识内容。
                  </div>
                </div>
                <div class="author-content">
                  <div class="title">作者</div>
                  <div class="sub">Eammon</div>
                </div>
                <div class="code-content">
                  <div class="title">重点阅读</div>
                  <div class="sub">
                    深入了解：TODO
                  </div>
                </div>
              </div>
            </section>
          </div>
        </main>
      </a-layout-content>
      <FooterButtons v-if="!$store.state.collapsed"/>
    </a-layout>
  </a-layout>
</template>

<script>
import IndexHeader from "@/components/index/head/IndexHeader";
import FooterButtons from "@/components/utils/FooterButtons";

export default {
  name: "About",

  components: {IndexHeader, FooterButtons},

  mounted() {
    // 滚动条恢复初始位置的方法
    this.$nextTick(() => {
      let dom = document.querySelector('#app');
      if (dom !== null) {
        dom.scrollTop = 0;
      }
    })
  }
};
</script>


<style lang="less">
#about-index {

  .header {
    position: fixed;
    width: 100%;
    z-index: 999;
    background: #fff;
    border-bottom: 1px solid #00000021;
  }

  .about_content {
    margin-top: 64px;
  }

  .ant-layout-header, .ant-layout-content {
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .ant-layout-header {
    background: #fff;
    height: auto;
    line-height: 2.3;
  }

  .mission {
    padding: 30px 30px;
    box-sizing: border-box;

    .title {
      font-size: 32px;
      font-weight: bold;
    }

    .sub {
      margin: 10px 0;
      font-size: 16px;
      color: #999;
    }
  }
}

</style>
