<template>
  <div class="clock" role="timer" :aria-label="ariaLabel">
    <!-- 时 -->
    <div class="clock__block" data-time-group aria-hidden="true">
      <div class="clock__digit-group">
        <div class="clock__digits">{{ a[0] }}</div>
        <div class="clock__digits">{{ b[0] }}</div>
      </div>
    </div>

    <div class="clock__colon" aria-hidden="true">:</div>

    <!-- 分 -->
    <div class="clock__block" data-time-group aria-hidden="true">
      <div class="clock__digit-group">
        <div class="clock__digits">{{ a[1] }}</div>
        <div class="clock__digits">{{ b[1] }}</div>
      </div>
    </div>

    <div class="clock__colon" aria-hidden="true">:</div>

    <!-- 秒 -->
    <div class="clock__block" data-time-group aria-hidden="true">
      <div class="clock__digit-group">
        <div class="clock__digits">{{ a[2] }}</div>
        <div class="clock__digits">{{ b[2] }}</div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "Clock",

  data() {
    return {
      // a 为上一帧，b 为当前帧（驱动翻转动画）
      a: [],
      b: [],
      rollClass: "clock__block--bounce"
    };
  },

  computed: {
    ariaLabel() {
      return (this.b && this.b.length ? this.b.slice(0, 3).join(":") : "");
    }
  },

  methods: {
    pad(n) {
      return n < 10 ? "0" + n : "" + n;
    },

    updateTime() {
      const d = new Date();
      const h = d.getHours();
      const m = d.getMinutes();
      const s = d.getSeconds();

      this.a = [...this.b];
      this.b = [this.pad(h), this.pad(m), this.pad(s)];
      if (!this.a.length) this.a = [...this.b];
    },

    animateDigits() {
      const groups = this.$el.querySelectorAll("[data-time-group]");
      let changed = false;
      Array.from(groups).forEach((group, i) => {
        if (this.a[i] !== this.b[i]) {
          group.classList.add(this.rollClass);
          changed = true;
        }
      });
      if (changed) {
        clearTimeout(this._rollTimer);
        this._rollTimer = setTimeout(this.removeAnimations, 900);
      }
    },

    removeAnimations() {
      const groups = this.$el.querySelectorAll("[data-time-group]");
      Array.from(groups).forEach(group => {
        group.classList.remove(this.rollClass);
      });
    },

    loop() {
      this.updateTime();
      this.animateDigits();
      clearTimeout(this._tickTimer);
      this._tickTimer = setTimeout(this.loop, 1000);
    }
  },

  mounted() {
    this.loop();
  },

  beforeDestroy() {
    clearTimeout(this._tickTimer);
    clearTimeout(this._rollTimer);
  }
};
</script>

<style scoped>
/* 与全站玻璃风格一致的小型翻转时钟 */
.clock {
  display: flex;
  align-items: center;
  
}

.clock__block {
  position: relative;
  overflow: hidden;
  width: 46px;
  height: 56px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.5);
  backdrop-filter: blur(12px) saturate(160%);
  -webkit-backdrop-filter: blur(12px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.55);
  box-shadow: 0 4px 16px rgba(31, 34, 41, 0.06);
  color: #2c3e50;
  /* 发丝边框：中性浅灰 1px，让过于透明的卡边缘可辨 */
  border: 1px solid rgba(31, 34, 41, 0.16);
}

.clock__digit-group {
  display: flex;
  flex-direction: column-reverse;
}

.clock__digits {
  width: 46px;
  height: 56px;
  line-height: 56px;
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.clock__colon {
  margin: 0 5px;
  font-size: 22px;
  line-height: 56px;
  font-weight: 700;
  color: #d4af37;
  opacity: 0.85;
}

/* 变化时的翻转动画 */
.clock__block--bounce {
  animation: clock-bounce 0.75s;
}

.clock__block--bounce .clock__digit-group {
  animation: clock-roll 0.75s ease-in-out forwards;
  transform: translateY(-50%);
}

@keyframes clock-bounce {
  from,
  to {
    transform: translateY(0);
    animation-timing-function: ease-in;
  }
  50% {
    transform: translateY(6%);
    animation-timing-function: ease-out;
  }
}

@keyframes clock-roll {
  from {
    transform: translateY(-50%);
  }
  to {
    transform: translateY(0);
  }
}
</style>
