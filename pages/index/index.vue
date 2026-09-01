<template>
  <view class="app">
    <!-- 顶栏 -->
    <view class="topbar">
      <view class="icon-btn" @click="openSettings">
        <text class="gear">⚙</text>
      </view>
      <view class="top-title">7MA 用车助手</view>
      <view class="icon-spacer"></view>
    </view>

    <!-- 主界面 -->
    <scroll-view scroll-y class="content">
      <view class="hero">
        <text class="hero-title">扫码即可用车</text>
        <text class="hero-sub">{{ serverText }}</text>
      </view>

      <view class="card scan-card" @click="onScan">
        <view class="card-icon">&#128247;</view>
        <view class="card-body">
          <text class="card-title">扫码用车</text>
          <text class="card-desc">扫描车身上二维码，自动识别车辆编号并下单</text>
        </view>
        <text class="card-arrow">›</text>
      </view>

      <view class="card input-card">
        <text class="card-title">输入车辆编号</text>
        <view class="input-row">
          <input class="num-input" v-model="manualValue" type="text"
                 placeholder="请输入单车编号，如 123456" />
          <button class="btn" @click="submitManual">下单</button>
        </view>
        <text class="field-error" v-if="manualError">{{manualError}}</text>
      </view>

      <view class="history" v-if="history.length">
        <view class="history-head">
          <text>最近订单</text>
          <text class="history-hint">点击记录可再次下单</text>
        </view>
        <view class="history-list">
          <view class="history-item" v-for="(item, idx) in pagedHistory" :key="idx" @click="useHistory(item.num)">
            <text class="h-num">{{item.num}}</text>
            <view class="h-info">
              <text class="h-msg">{{item.msg}}</text>
              <text class="h-time">{{item.time}}</text>
            </view>
            <text class="h-status" :class="item.ok ? 'ok' : 'bad'">{{item.ok ? '成功' : '失败'}}</text>
          </view>
        </view>
        <view class="history-foot" v-if="history.length">
          <view class="size-row">
            <text class="size-label">每页显示</text>
            <view class="size-chip" v-for="s in pageSizeOptions" :key="s" :class="{ on: s === pageSize }" @click="setPageSize(s)">{{s}}</view>
          </view>
          <view class="pager" v-if="totalPages > 1">
            <view class="pager-btn" :class="{ off: currentPage <= 1 }" @click="prevPage">&#8249;</view>
            <view class="pager-num" v-for="p in pageList" :key="p" :class="{ on: p === currentPage }" @click="goPage(p)">{{p}}</view>
            <view class="pager-btn" :class="{ off: currentPage >= totalPages }" @click="nextPage">&#8250;</view>
          </view>
          <text class="pager-info">共 {{history.length}} 条 · 第 {{currentPage}}/{{totalPages}} 页</text>
        </view>
      </view>

      <view class="disclaimer">仅供技术学习 · 请遵守平台规则 · 风险自负</view>
    </scroll-view>

    <!-- 设置弹窗 -->
    <view class="overlay" v-if="showSettings" @click.self="closeOverlay">
      <view class="modal-card">
        <view class="modal-x" @click="closeModal">&#10005;</view>
        <view class="onboarding-badge" v-if="firstRun">首次使用：请填服务地址与 API 密钥（可不填先浏览）</view>
        <text class="modal-title">{{firstRun ? '首次使用 · 服务设置' : '服务设置'}}</text>
        <text class="modal-sub">域名与密钥保存在本机，点击保存生效。</text>

        <view class="modal-field">
          <text class="label">服务地址（域名）</text>
          <input class="field-input" v-model="domain" placeholder="http://192.168.1.100:4321 或 https://…">
          <text class="tip">支持 http/https；真机与本机同 WiFi 时填电脑局域网 IP</text>
        </view>
        <view class="modal-field">
          <text class="label">API 密钥</text>
          <input class="field-input" v-model="apiKey" password placeholder="后台 设置→API密钥 查看">
        </view>
        <view class="status-line" v-if="testText" :class="testOk ? 'ok' : 'bad'">{{testText}}</view>
        <view class="modal-actions">
          <view class="btn ghost" @click="testConnection">测试连接</view>
          <view class="btn" @click="saveSettings">保存</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
var KEY_DOMAIN = '7ma_domain';
var KEY_KEY = '7ma_apikey';
var KEY_HISTORY = '7ma_history';
var KEY_PAGE_SIZE = '7ma_page_size';

export default {
  data() {
    return {
      domain: '',
      apiKey: '',
      firstRun: false,
      showSettings: false,
      testText: '',
      manualValue: '',
      error: '',
      history: [],
      ordering: false,
      pageSize: 5,
      currentPage: 1,
      pageSizeOptions: [5, 10, 20, 50]
    };
  },
  computed: {
    serverText() {
      if (!this.domain) return '尚未配置服务地址，点左上角图标配置';
      return this.domain + '（密钥已配置）';
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.history.length / this.pageSize));
    },
    pageList() {
      var list = [];
      for (var i = 1; i <= this.totalPages; i++) list.push(i);
      return list;
    },
    pagedHistory() {
      var start = (this.currentPage - 1) * this.pageSize;
      return this.history.slice(start, start + this.pageSize);
    }
  },
  onLoad() {
    this.domain = uni.getStorageSync(KEY_DOMAIN) || '';
    this.apiKey = uni.getStorageSync(KEY_KEY) || '';
    this.loadHistory();
    var savedSize = uni.getStorageSync(KEY_PAGE_SIZE);
    if (this.pageSizeOptions.indexOf(Number(savedSize)) >= 0) this.pageSize = savedSize;
    if (!this.domain || !this.apiKey) {
      this.firstRun = true;
      this.showSettings = true;
    }
  },
  methods: {
    loadHistory() {
      try {
        this.history = JSON.parse(uni.getStorageSync(KEY_HISTORY) || '[]');
      } catch (e) {
        this.history = [];
      }
      this.currentPage = 1;
    },
    openSettings() {
      this.testText = '';
      this.showSettings = true;
    },
    closeOverlay() {
      if (!this.firstRun) this.showSettings = false;
    },
    closeModal() {
      this.showSettings = false;
      if (this.firstRun) this.firstRun = false;
    },
    normalizeBase(raw) {
      var s = String(raw || '').trim().replace(/\/+$/, '');
      if (!s) return '';
      if (!/^https?:\/\//i.test(s)) {
        var ipLocal = /^\d{1,3}(\.\d{1,3}){3}(:\d+)?$/.test(s) ||
                      /^localhost(:\d+)?$/i.test(s) || /^127\./.test(s);
        s = (ipLocal ? 'http://' : 'https://') + s;
      }
      return s.replace(/\/+$/, '');
    },
    getBase() {
      return this.normalizeBase(this.domain);
    },
    testConnection() {
      var base = this.getBase();
      var key = this.apiKey.trim();
      if (!base || !key) {
        this.testText = '请先填写服务地址与 API 密钥';
        return;
      }
      this.testText = '正在测试连接…';
      uni.request({
        url: base + '/api/v1/status',
        method: 'GET',
        header: { 'X-API-Key': key },
        timeout: 9000,
        success: (res) => {
          if (res.statusCode === 200 && res.data && res.data.ok) {
            this.testText = '连接成功：共 ' + (res.data.authorizations || 0) + ' 个可用账号';
          } else if (res.statusCode === 401) {
            this.testText = '连接失败：API 密钥无效，请检查';
          } else {
            this.testText = '连接失败：HTTP ' + res.statusCode;
          }
        },
        fail: () => {
          this.testText = '无法连接：请检查地址、端口与网络';
        }
      });
    },
    saveSettings() {
      var domain = this.getBase();
      var key = this.apiKey.trim();
      if (!domain || !key) {
        uni.showToast({ title: '请同时填写服务地址与 API 密钥', icon: 'none' });
        return;
      }
      uni.setStorageSync(KEY_DOMAIN, domain);
      uni.setStorageSync(KEY_KEY, key);
      this.firstRun = false;
      this.showSettings = false;
      uni.showToast({ title: '配置已保存' });
    },
    extractNumber(raw) {
      if (!raw) return '';
      var t = String(raw).trim();
      var m = t.match(/randnum[=:](\d+)/i);
      if (m) return m[1];
      var parts = t.split(/[\/?#]/).filter(Boolean);
      var last = parts.length ? parts[parts.length - 1] : '';
      if (/^\d+$/.test(last)) return last;
      if (/^\d+$/.test(t)) return t;
      var m2 = t.match(/\b\d{4,}\b/);
      if (m2) return m2[1];
      return '';
    },
    onScan() {
      var that = this;
      uni.scanCode({
        scanType: ['qrCode'],
        success: (res) => {
          var raw = res.result || '';
          var num = that.extractNumber(raw);
          if (!num) {
            uni.showModal({
              title: '未能识别车辆编号',
              content: '识别内容：\n' + raw + '\n\n请改用「输入车辆编号」下单',
              showCancel: false
            });
            return;
          }
          uni.showModal({
            title: '识别车辆编号',
            content: '车辆编号：' + num,
            confirmText: '下单',
            cancelText: '取消',
            success: (mres) => {
              if (mres.confirm) that.placeOrder(num);
            }
          });
        },
        fail: (err) => {
          uni.showToast({ title: '扫码失败：' + (err.errMsg || ''), icon: 'none' });
        }
      });
    },
    submitManual() {
      var val = (this.manualValue || '').trim();
      if (!val) {
        this.error = '请输入车辆编号后再下单。';
        return;
      }
      this.error = '';
      var extracted = this.extractNumber(val);
      this.placeOrder(extracted || val);
    },
    useHistory(num) {
      this.manualValue = num;
      uni.showToast({ title: '已将 ' + num + ' 填入输入框', icon: 'none' });
    },
    pushHistory(num, ok, msg) {
      this.history.unshift({
        num: num,
        ok: !!ok,
        msg: (msg || (ok ? '下单成功' : '下单失败')).slice(0, 60),
        time: new Date().toLocaleString('zh-CN', { hour12: false })
      });
      if (this.history.length > 20) this.history.length = 20;
      uni.setStorageSync(KEY_HISTORY, JSON.stringify(this.history));
      this.currentPage = 1;
    },
    setPageSize(p) {
      this.pageSize = p;
      this.currentPage = 1;
      uni.setStorageSync(KEY_PAGE_SIZE, p);
    },
    goPage(p) {
      if (p < 1 || p > this.totalPages || p === this.currentPage) return;
      this.currentPage = p;
    },
    prevPage() {
      this.goPage(this.currentPage - 1);
    },
    nextPage() {
      this.goPage(this.currentPage + 1);
    },
    placeOrder(num) {
      var base = this.getBase();
      var key = this.apiKey.trim();
      if (!base || !key) {
        uni.showModal({
          title: '尚未配置服务',
          content: '请点击左上角小图标填写服务地址与 API 密钥后再下单',
          showCancel: false
        });
        return;
      }
      if (this.ordering) return;
      this.ordering = true;
      uni.showLoading({ title: '正在下单，请耐心等待', mask: true });
      var that = this;
      uni.request({
        url: base + '/api/v1/order',
        method: 'POST',
        header: { 'Content-Type': 'application/json', 'X-API-Key': key },
        data: { bike_number: num },
        timeout: 130000,
        success: (res) => {
          uni.hideLoading();
          that.ordering = false;
          var d = res.data || {};
          if (res.statusCode === 401) {
            that.pushHistory(num, false, 'API 密钥无效或已更换，请重新设置');
            that.showResult(false, num, 'API 密钥无效或已更换，请点击左上角重新设置');
            return;
          }
          if (res.statusCode === 200 && d.ok) {
            var msg = d.message || '下单成功';
            if (d.unlock_result) msg += '\n开锁结果：' + d.unlock_result;
            if (d.return_result) msg += '\n还车结果：' + d.return_result;
            that.pushHistory(num, true, msg.split('\n')[0]);
            that.showResult(true, num, msg);
          } else {
            var em = (d.error || d.message || '下单失败，请稍后重试');
            that.pushHistory(num, false, em);
            that.showResult(false, num, em);
          }
        },
        fail: (err) => {
          uni.hideLoading();
          that.ordering = false;
          var msg = '网络错误：无法连接服务器，请检查服务地址或网络后重试';
          if (err && err.errMsg) msg += '\n(' + err.errMsg + ')';
          that.pushHistory(num, false, msg);
          that.showResult(false, num, msg);
        }
      });
    },
    showResult(ok, num, msg) {
      uni.showModal({
        title: ok ? '下单成功' : '下单失败',
        content: '车辆编号：' + num + '\n' + msg,
        showCancel: false,
        confirmText: '完成'
      });
    }
  }
};
</script>

<style>
page {
  background: #10162b;
  height: 100%;
}

.app {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: radial-gradient(120% 120% at 15% 8%, #2c3c68, #151c2f 55%, #0e1424);
  color: #fff;
  font-size: 15px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  padding-top: calc(10px + constant(safe-area-inset-top));
  padding-top: calc(10px + env(safe-area-inset-top));
}

.icon-btn {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
}

.gear {
  font-size: 24px;
  line-height: 26px;
}

.top-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
}

.icon-spacer {
  width: 42px;
}

.content {
  flex: 1;
  padding: 0 16px 24px;
  box-sizing: border-box;
}

.hero {
  background: linear-gradient(135deg, #4f6ef7, #7c3aed);
  border-radius: 18px;
  padding: 22px 20px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
}
.hero-title { font-size: 21px; font-weight: 800; }
.hero-sub { font-size: 12px; opacity: 0.9; margin-top: 6px; word-break: break-all; }

.card {
  background: #fff;
  border-radius: 18px;
  padding: 18px;
  margin-bottom: 14px;
  color: #1f2937;
}

.scan-card {
  display: flex;
  align-items: center;
}
.card-icon {
  width: 54px;
  height: 54px;
  border-radius: 15px;
  background: linear-gradient(135deg, #4f6ef7, #7c3aed);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  margin-right: 14px;
}
.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.card-title { font-size: 17px; font-weight: 700; margin-bottom: 4px; }
.card-desc { font-size: 12px; color: #7c8894; line-height: 1.4; }
.card-arrow { color: #c3ccda; font-size: 22px; }

.input-card .card-title { margin-bottom: 12px; }
.input-row {
  display: flex;
}
.num-input {
  flex: 1;
  margin-right: 10px;
  height: 44px;
  line-height: 44px;
  padding: 0 12px;
  border: 1px solid #dbe2ec;
  border-radius: 12px;
  background: #fbfcfe;
  font-size: 16px;
}
.btn {
  height: 44px;
  line-height: 44px;
  padding: 0 22px;
  border-radius: 12px;
  background: linear-gradient(135deg, #4f6ef7, #6a5bf3);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  text-align: center;
  box-shadow: 0 8px 18px rgba(79, 110, 247, 0.35);
}
.btn.ghost {
  background: transparent;
  color: #64748b;
  border: 1px solid #dbe2ec;
  box-shadow: none;
}
.field-error { display: block; margin-top: 8px; color: #dc2626; font-size: 13px; }

.history {
  margin-bottom: 14px;
}
.history-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 4px 2px 8px;
  font-size: 15px;
  font-weight: 700;
}
.history-hint { font-size: 11px; font-weight: 400; opacity: 0.75; }
.history-list {
  display: flex;
  flex-direction: column;
}
.history-item {
  background: #fff;
  border-radius: 14px;
  padding: 12px 14px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  color: #1f2937;
}
.h-num {
  font-size: 19px;
  font-weight: 800;
  color: #4f6ef7;
  min-width: 92px;
}
.h-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.h-msg { font-size: 13px; color: #374151; }
.h-time { font-size: 11px; color: #7c8894; margin-top: 2px; }
.h-status {
  font-size: 12px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 999px;
}
.h-status.ok { color: #16a34a; background: #dcfce7; }
.h-status.bad { color: #dc2626; background: #fee2e2; }

.disclaimer {
  text-align: center;
  padding: 12px 0 8px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
}

/* 设置弹窗 */
.overlay {
  position: fixed;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  background: rgba(8, 12, 24, 0.8);
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.modal-card {
  width: 100%;
  max-width: 420px;
  background: #fff;
  border-radius: 20px;
  padding: 24px 22px;
  color: #1f2937;
  position: relative;
}
.modal-x {
  position: absolute;
  top: 12px;
  right: 14px;
  color: #94a3b8;
  font-size: 14px;
  padding: 6px;
}
.onboarding-badge {
  background: linear-gradient(135deg, rgba(79, 110, 247, 0.12), rgba(124, 58, 237, 0.12));
  color: #3730a3;
  border-radius: 12px;
  padding: 10px;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 12px;
}
.modal-title { display: block; font-size: 19px; font-weight: 700; }
.modal-sub {
  display: block;
  font-size: 12px;
  color: #7c8894;
  margin: 4px 0 16px;
}
.modal-field { margin-bottom: 14px; }
.label {
  display: block;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}
.field-input {
  width: 100%;
  height: 44px;
  line-height: 44px;
  padding: 0 12px;
  border: 1px solid #dbe2ec;
  border-radius: 11px;
  background: #fbfcfe;
  font-size: 14px;
}
.tip {
  display: block;
  font-size: 11px;
  color: #7c8894;
  margin-top: 5px;
}
.status-line {
  margin-bottom: 12px;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
}
.status-line.ok { background: #dcfce7; color: #166534; }
.status-line.bad { background: #fee2e2; color: #b91c1c; }
.modal-actions {
  display: flex;
}
.modal-actions .btn {
  flex: 1;
  margin-right: 10px;
}
.modal-actions .btn:last-child {
  margin-right: 0;
}
/* 最近订单分页 */
.history-foot {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4px 2px 2px;
}
.size-row {
  display: flex;
  align-items: center;
  justify-content: center;
}
.size-label {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
  margin-right: 8px;
}
.size-chip {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.16);
  padding: 4px 13px;
  margin-right: 6px;
  border-radius: 999px;
}
.size-chip.on {
  background: linear-gradient(135deg, #4f6ef7, #6a5bf3);
  border-color: transparent;
  color: #fff;
  font-weight: 700;
}
.pager {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 10px;
}
.pager-btn {
  width: 34px;
  height: 34px;
  line-height: 32px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 10px;
  font-size: 18px;
  color: rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.08);
}
.pager-btn.off {
  opacity: 0.35;
}
.pager-num {
  min-width: 34px;
  height: 34px;
  line-height: 34px;
  text-align: center;
  border-radius: 10px;
  margin: 0 4px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.08);
}
.pager-num.on {
  background: linear-gradient(135deg, #4f6ef7, #7c3aed);
  color: #fff;
  font-weight: 700;
}
.pager-info {
  margin-top: 8px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
}
</style>
