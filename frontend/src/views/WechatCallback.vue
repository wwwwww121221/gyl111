<template>
  <div class="wechat-callback-page">
    <div class="wechat-callback-card">
      <h1>微信登录处理中</h1>
      <p>{{ message }}</p>
      <button v-if="retryUrl" class="retry-btn" type="button" @click="goNext">
        继续跳转
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getApiOrigin } from '../api'

const route = useRoute()
const message = ref('正在校验微信授权，请稍候...')

const retryUrl = computed(() => {
  const params = new URLSearchParams()
  Object.entries(route.query || {}).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, String(item)))
      return
    }
    if (value != null && value !== '') {
      params.set(key, String(value))
    }
  })

  const queryString = params.toString()
  const target = `${getApiOrigin()}/wechat/verify`
  return queryString ? `${target}?${queryString}` : target
})

const goNext = () => {
  if (!retryUrl.value) return
  window.location.replace(retryUrl.value)
}

onMounted(() => {
  if (!route.query.code) {
    message.value = '未获取到微信授权参数，请返回公众号菜单重试。'
    return
  }
  goNext()
})
</script>

<style scoped>
.wechat-callback-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top, rgba(34, 197, 94, 0.18), transparent 45%),
    linear-gradient(180deg, #f8fafc 0%, #eef6ff 100%);
}

.wechat-callback-card {
  width: min(420px, 100%);
  padding: 32px 28px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.12);
  text-align: center;
}

.wechat-callback-card h1 {
  margin: 0 0 12px;
  font-size: 28px;
  color: #0f172a;
}

.wechat-callback-card p {
  margin: 0;
  line-height: 1.7;
  color: #475569;
}

.retry-btn {
  margin-top: 20px;
  border: none;
  border-radius: 999px;
  padding: 12px 24px;
  color: #fff;
  background: linear-gradient(135deg, #16a34a 0%, #22c55e 100%);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
</style>
