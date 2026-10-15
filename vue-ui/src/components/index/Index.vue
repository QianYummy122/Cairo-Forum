<template>
  <a-layout>
    <a-layout id="components-layout-basic">
      <IndexHeader class="header"
                   @refresh="refresh"
                   :searchContent="searchContent"/>
      <a-layout-content>
        <main class="content glass">
          <a-col :span="$store.state.collapsed ? 24 : 18"
                 :style="$store.state.collapsed ? '' : 'border-right: 20px solid transparent'">
            <CustomEmpty v-if="spinning"/>
            <div v-else>
              <!-- 轮播图 -->
              <SlideShow v-if="!$store.state.collapsed && $store.state.isCarousel"/>
              <a-row v-if="!$store.state.collapsed && $store.state.isCarousel">
                <a-col :span="24" style="height: 2px;"/>
              </a-row>
              <div class="article-check-left-buttons"
                   :style="$store.state.collapsedMax ? '' : 'right:120px'"
                   v-if="$store.state.isManage">
                <!-- 文章审核 -->
                <ArticleCheck
                    ref="child"
                    @initArticles="initArticles"/>
              </div>
              <!-- 文章列表（管理员） -->
              <FrontPageArticle v-if="$store.state.isManage && !spinning"
                                :finish="finish"
                                :hasNext="hasNext"
                                :data="listData"
                                :isAdminAudit="true"
                                @updateData="updateData"
                                @articleTopCallBack="articleTopCallBack"
                                @refresh="refresh"
                                style="background: #fff;"/>
              <!-- 文章列表（普通） -->
              <FrontPageArticle v-if="!$store.state.isManage && !spinning"
                                :finish="finish"
                                :hasNext="hasNext"
                                :data="listData"
                                @refresh="refresh"
                                style="background: #fff;"/>
            </div>
          </a-col>
          <a-col v-if="!$store.state.collapsed" :span="6">
            <!-- 系统简介 -->
            <ProjectIntro style="background: #fff;"/>
            <a-row>
              <a-col :span="24" style="height: 10px;"/>
            </a-row>
            <!-- 作者榜 -->
            <AuthorsList style="background: #fff;"/>
            <a-row>
              <a-col :span="24" style="height: 10px;"/>
            </a-row>
            <!-- 最新评论 -->
            <LatestComment style="background: #fff;"/>
            <a-row>
              <a-col :span="24" style="height: 10px;"/>
            </a-row>
            <!-- 友情捐赠 -->
            <FriendDonate style="background: #fff;"/>
            <a-row>
              <a-col :span="24" style="height: 10px;"/>
            </a-row>
            <!-- 备案信息 -->
            <FilingInfo/>
          </a-col>
        </main>
      </a-layout-content>
      <FooterButtons v-if="!$store.state.collapsed"/>
    </a-layout>
    <!-- 首页左栏顶部时钟（fixed，滚动不跟随）。
         backdrop-filter 会让 .glass 容器成为“定位包含块”，fixed 子元素会相对它而非视口定位；
         因此时钟必须放在玻璃容器之外，位置仍由 updateClockPos 实测得出 -->
    <div class="home-clock" v-if="!$store.state.collapsed"
         ref="homeClock"
         :style="{left: clockPos.left, top: clockPos.top}">
      <Clock/>
    </div>
  </a-layout>
</template>

<script>
import IndexHeader from "@/components/index/head/IndexHeader";
import SlideShow from "@/components/concern/SlideShow";
import FrontPageArticle from "@/components/article/FrontPageArticle";
import ProjectIntro from "@/components/right/ProjectIntro";
import articleService from "@/service/articleService";
import AuthorsList from "@/components/right/AuthorsList";
import FilingInfo from "@/components/right/FilingInfo";
import FooterButtons from "@/components/utils/FooterButtons";
import CustomEmpty from "@/components/utils/CustomEmpty";
import LatestComment from "@/components/right/LatestComment";
import FriendDonate from "@/components/right/FriendDonate";
import ArticleCheck from "@/components/article/ArticleCheck";
import Clock from "@/components/utils/Clock";

export default {
  components: {
    IndexHeader,
    FooterButtons,
    SlideShow,
    FrontPageArticle,
    ProjectIntro,
    AuthorsList,
    FilingInfo,
    CustomEmpty,
    LatestComment,
    FriendDonate,
    ArticleCheck,
    Clock
  },
  data() {
    return {
      // 加载中...
      spinning: true,
      listData: [],
      hasNext: true,
      finish: false,
      params: {currentPage: 1, pageSize: 12},
      searchContent: '',
      // 时钟 fixed 定位（由 updateClockPos 测量得出）
      clockPos: { left: '12px', top: '76px' },
    };
  },

  methods: {
    // 加载更多（滚动加载）
    loadMore() {
      this.params.currentPage++;
      if (this.$store.state.articleCheck === 'enable') {
        this.getArticleList(this.params, true);
      }
      if (this.$store.state.articleCheck === 'pendingReview') {
        this.getPendingReviewArticles(this.params, true);
      }
      if (this.$store.state.articleCheck === 'disabled') {
        this.getDisabledArticles(this.params, true);
      }
    },

    // 计算时钟 fixed 的屏幕坐标：顶栏下方、对齐左栏内容左边界
    updateClockPos() {
      if (this.$store.state.collapsed) return;
      this.$nextTick(() => {
        const root = this.$el;
        if (!root) return;
        const head = root.querySelector('.header');
        const content = root.querySelector('.content');
        const headH = head ? head.getBoundingClientRect().height : 64;

        let left = 12;
        let top = headH + 12;
        if (content) {
          const cr = content.getBoundingClientRect();
          const wrap = this.$refs.homeClock;
          const wrapW = wrap ? wrap.offsetWidth : 0;
          // 尽量把时钟放进列左侧空白：右缘与列保留 16px；
          // 空白不足（窄屏/无侧栏留白）时退而贴靠列左，避免把列内容压得太厉害
          left = Math.max(12, cr.left - wrapW - 16);
          // 若列起点比“顶栏下方”更低，则对齐列起点
          if (cr.top > top) top = cr.top;
        }
        this.clockPos = { left: left + 'px', top: top + 'px' };
      });
    },

    // 初始文章列表（管理员）
    initArticles() {
      // 滚动条恢复初始位置的方法
      this.$nextTick(() => {
        let dom = document.querySelector('#app');
        if (dom !== null) {
          dom.scrollTop = 0;
        }
      })

      this.hasNext = true;
      if (this.$store.state.articleCheck === "enable") {
        this.getArticleList(this.params);
      }
      if (this.$store.state.articleCheck === "pendingReview") {
        this.getPendingReviewArticles(this.params);
      }
      if (this.$store.state.articleCheck === "disabled") {
        this.getDisabledArticles(this.params);
      }
    },

    // 获取文章列表信息
    getArticleList(params, isLoadMore) {
      if (!isLoadMore) {
        this.params.currentPage = 1;
      }
      this.finish = false;
      articleService.getArticleList(params)
          .then(res => {
            if (isLoadMore) {
              this.listData = this.listData.concat(res.data.list);
              this.hasNext = res.data.list.length !== 0;
            } else {
              this.listData = res.data.list;
            }
            this.spinning = false;
            this.finish = true;
          })
          .catch(err => {
            this.finish = true;
            this.$message.error(err.desc);
          });
    },

    // 获取待审核的文章
    getPendingReviewArticles(params, isLoadMore) {
      if (!isLoadMore) {
        this.params.currentPage = 1;
      }
      this.finish = false;
      articleService.getPendingReviewArticles(params)
          .then(res => {
            if (isLoadMore) {
              this.listData = this.listData.concat(res.data.list);
              this.hasNext = res.data.list.length !== 0;
            } else {
              this.listData = res.data.list;
            }
            this.spinning = false;
            this.finish = true;
          })
          .catch(err => {
            this.finish = true;
            this.$message.error(err.desc);
          });
    },

    // 获取禁用的文章
    getDisabledArticles(params, isLoadMore) {
      if (!isLoadMore) {
        this.params.currentPage = 1;
      }
      this.finish = false;
      articleService.getDisabledArticles(params)
          .then(res => {
            if (isLoadMore) {
              this.listData = this.listData.concat(res.data.list);
              this.hasNext = res.data.list.length !== 0;
            } else {
              this.listData = res.data.list;
            }
            this.spinning = false;
            this.finish = true;
          })
          .catch(err => {
            this.finish = true;
            this.$message.error(err.desc);
          });
    },

    // 刷新列表
    refresh() {
      this.params = {currentPage: 1, pageSize: 10};
      this.getArticleList(this.params);
    },

    // 同步data变化
    updateData(tempData) {
      this.listData = tempData;
      if (this.$store.state.isManage) {
        // 文章审核数据量
        this.$refs.child.getArticleCheckCount();
      }
    },

    // 文章置顶（管理员）
    articleTopCallBack() {
      // 滚动条恢复初始位置的方法
      this.$nextTick(() => {
        let dom = document.querySelector('#app');
        if (dom !== null) {
          dom.scrollTop = 0;
        }
      })

      if (this.$store.state.articleCheck === "enable") {
        this.getArticleList(this.params);
      }
      if (this.$store.state.articleCheck === "pendingReview") {
        this.getPendingReviewArticles(this.params);
      }
      if (this.$store.state.articleCheck === "disabled") {
        this.getDisabledArticles(this.params);
      }
    }
  },

  mounted() {
    // 滚动条恢复初始位置的方法
    this.$nextTick(() => {
      let dom = document.querySelector('#app');
      if (dom !== null) {
        dom.scrollTop = 0;
      }
    })

    let query = this.$route.query.query;
    this.searchContent = query;
    this.params.title = query;
    this.getArticleList(this.params);
    // 监听滚动，做滚动加载
    this.$utils.scroll.call(this, document.querySelector('#app'));
    // 时钟 fixed 定位 + 跟随窗口变化
    this.updateClockPos();
    window.addEventListener('resize', this.updateClockPos);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateClockPos);
  },

  watch: {
    // 路由值改变时触发
    $route() {
      // 跳转到该页面后需要进行的操作
      let query = this.$route.query.query;
      this.searchContent = query;
      this.params.title = query;
      if (this.$store.state.isManage) {
        if (this.$store.state.articleCheck === "enable") {
          this.getArticleList(this.params);
        }
        if (this.$store.state.articleCheck === "pendingReview") {
          this.getPendingReviewArticles(this.params);
        }
        if (this.$store.state.articleCheck === "disabled") {
          this.getDisabledArticles(this.params);
        }

        // 文章审核数据量
        this.$refs.child.getArticleCheckCount();
      } else {
        this.getArticleList(this.params);
      }
    }
  }
};
</script>


<style>
#components-layout-basic .header {
  position: fixed;
  z-index: 999;
  width: 100%;
  background: #fff;
  border-bottom: 1px solid #00000021;
}

/* 首页左栏顶部时钟：fixed 悬浮于顶栏下方，不随内容滚动；
   left/top 由 updateClockPos 动态算出，pointer-events:none 不挡下层操作 */
.home-clock {
  position: fixed;
  z-index: 60;
  pointer-events: none;
}

#components-layout-basic .content {
  margin-top: 64px;
  width: 100%;
  max-width: 1100px;
}

#components-layout-basic .ant-layout-header, .ant-layout-content {
  display: flex;
  align-items: center;
  justify-content: center;
}

#components-layout-basic .ant-layout-header {
  background: #fff;
  height: auto;
  line-height: 2.3;
}

#components-layout-basic .article-check-left-buttons {
  position: relative;
  top: 20px;
}

.index-drawer-wrap .ant-drawer-content-wrapper {
  width: 250px !important;
}

#components-layout-demo-custom-trigger .trigger {
  font-size: 18px;
  line-height: 64px;
  padding: 0 24px;
  cursor: pointer;
  transition: color 0.3s;
}

#components-layout-demo-custom-trigger .trigger:hover {
  color: var(--theme-color, #D4AF37);
}

#components-layout-demo-custom-trigger .logo {
  height: 64px;
  background: rgba(255, 255, 255, 0.2);
  margin: 0;
}

.glass {
   background: rgba(255, 255, 255, 0.35) !important;
  backdrop-filter: blur(18px) saturate(150%);
  -webkit-backdrop-filter: blur(18px) saturate(150%);
  /* 发丝边框：中性浅灰 1px，让过于透明的卡边缘可辨 */
  border: 1px solid rgba(31, 34, 41, 0.16);
  padding: 20px;
}
</style>