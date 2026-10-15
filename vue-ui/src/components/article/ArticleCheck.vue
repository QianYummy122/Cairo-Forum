<template>
  <div id="article-check" :style="$store.state.collapsed ? 'left: 2%;' : ''">
    <!-- 通过审核 -->
    <div class="enable-div">
      <a-badge class="badge" :count="data.enableCount" :overflow-count="999" :number-style="{
        backgroundColor: '#A52A2A',
        boxShadow: '0 0 0 0 #fff inset',
      }">
        <div class="icon-container" @click="articleCheck('enable')"
             :style="$store.state.articleCheck === 'enable' ?
             {'background': '#FFFFF0', 'box-shadow':  '10px 10px 19px #D4AF37, -2px -2px 19px #C0C0C0'} : ''">
          <a-icon type="check-circle" style="color: #07c19a"/>
        </div>
      </a-badge>
    </div>

    <!-- 拒绝审核 -->
    <div class="disabled-div">
      <a-badge class="badge" :count="data.disabledCount" :overflow-count="999" :number-style="{
        backgroundColor: '#A52A2A',
        boxShadow: '0 0 0 0 #fff inset',
      }">
        <div class="icon-container" @click="articleCheck('disabled')"
             :style="$store.state.articleCheck === 'disabled' ?
             {'background': '#FFFFF0', 'box-shadow':  '10px 10px 19px #D4AF37, -2px -2px 19px #C0C0C0'} : ''">
          <a-icon type="close-circle" style="color: red"/>
        </div>
      </a-badge>
    </div>

    <!-- 待审核 -->
    <div class="pendingReview-div">
      <a-badge class="badge" :count="data.pendingReviewCount" :overflow-count="999" :number-style="{
        backgroundColor: '#A52A2A',
        boxShadow: '0 0 0 0 #fff inset',
      }">
        <div class="icon-container" @click="articleCheck('pendingReview')"
             :style="$store.state.articleCheck === 'pendingReview' ?
              {'background': '#FFFFF0', 'box-shadow':  '10px 10px 19px #D4AF37, -2px -2px 19px #C0C0C0'} : ''">
          <a-icon type="pause-circle" style="color: #faad14;"/>
        </div>
      </a-badge>
    </div>

  </div>
</template>

<script>

import articleService from "@/service/articleService";

export default {

  data() {
    return {
      data: {},
    }
  },

  methods: {
    // 文章审核数据量
    getArticleCheckCount() {
      articleService.getArticleCheckCount({title: this.$route.query.query})
          .then((res) => {
            this.data = res.data;
          })
          .catch(err => {
            this.$message.error(err.desc);
          });
    },

    articleCheck(value) {
      this.$store.state.articleCheck = value;
      this.$emit("initArticles")
    },
  },

  mounted() {
    this.getArticleCheckCount();
  }
};
</script>

<style lang="less">
#article-check {
  position: fixed;
  z-index: 888;

  .icon-container {
    border-radius: 50%;
    width: 45px;
    height: 45px;
    text-align: center;
    cursor: pointer;
    background: #fff;

    i {
      font-size: 20px;
      line-height: 50px;
    }

  }

  .icon-container:hover {
    box-shadow:  10px 10px 19px #D4AF37, -2px -2px 19px #C0C0C0;
  }

  .disabled-div, .pendingReview-div {
    margin-top: 20px;
  }

}
</style>
