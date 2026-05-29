<template>
  <div class="layout-container">
    <el-container class="main-container">
      <el-aside v-if="!isMobile" width="220px" class="aside">
        <div class="logo">
          <h2>供应商服务平台</h2>
        </div>
        <el-menu
          :default-active="activeMenu"
          class="el-menu-vertical"
          background-color="#304156"
          text-color="#bfcbd9"
          active-text-color="#409EFF"
          router
        >
          <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header class="header">
          <div class="header-left">
            <el-button
              v-if="isMobile"
              class="menu-toggle-btn"
              :icon="Menu"
              circle
              text
              @click="mobileMenuVisible = true"
            />
            <h3>{{ pageTitle }}</h3>
          </div>
          <div class="header-right">
            <el-dropdown @command="handleCommand">
              <span class="el-dropdown-link user-info">
                <el-avatar size="small" icon="UserFilled" style="margin-right: 8px;" />
                {{ displayName }}
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="logout">退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>

    <el-drawer
      v-model="mobileMenuVisible"
      direction="ltr"
      size="240px"
      :with-header="false"
      class="mobile-menu-drawer"
    >
      <div class="mobile-drawer-logo">
        <h2>供应商服务平台</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="el-menu-vertical mobile-menu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        router
        @select="mobileMenuVisible = false"
      >
        <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Document, Menu, OfficeBuilding, Plus, UserFilled, Warning } from '@element-plus/icons-vue'
import { jwtDecode } from 'jwt-decode'
import api from '../api/index'

const router = useRouter()
const route = useRoute()
const isMobile = ref(window.innerWidth <= 768)
const mobileMenuVisible = ref(false)
const supplierStatus = ref(localStorage.getItem('supplier_status') || '')
const boundStatus = ref(localStorage.getItem('bound_status') || '')

const allMenus = [
  { path: '/supplier/inquiries', label: '我的询价单', icon: Document },
  { path: '/supplier/warnings', label: '发货预警', icon: Warning },
  { path: '/supplier/members', label: '成员管理', icon: UserFilled },
  { path: '/supplier/company-info', label: '公司信息', icon: OfficeBuilding },
  { path: '/supplier/onboard', label: '入驻/绑定', icon: Plus },
]

const visibleMenus = computed(() => {
  const isBound = boundStatus.value === 'bound' || (supplierStatus.value === 'approved' && localStorage.getItem('member_status') === 'active')
  if (isBound) return allMenus.filter((item) => item.path !== '/supplier/onboard')
  const isPending = boundStatus.value === 'pending_review' || supplierStatus.value === 'pending'
  if (isPending) return allMenus.filter((item) => item.path === '/supplier/onboard')
  return allMenus.filter((item) => item.path === '/supplier/onboard')
})

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const map = {
    '/supplier/inquiries': '我的询价单',
    '/supplier/warnings': '发货预警',
    '/supplier/members': '成员管理',
    '/supplier/company-info': '公司信息',
    '/supplier/onboard': '入驻/绑定',
  }
  return map[route.path] || '供应商服务平台'
})

const displayName = ref('Supplier')
try {
  const token = localStorage.getItem('token')
  if (token) {
    const decoded = jwtDecode(token)
    displayName.value = decoded.sub || 'Supplier'
  }
} catch (error) {
  console.error('Failed to parse token', error)
}

const fetchSupplierDisplayName = async () => {
  const memberStatus = localStorage.getItem('member_status') || ''
  const shouldFetchProfile =
    boundStatus.value === 'bound' ||
    supplierStatus.value === 'approved' ||
    supplierStatus.value === 'pending' ||
    boundStatus.value === 'pending_review' ||
    memberStatus === 'active'

  if (!shouldFetchProfile) {
    if (route.path !== '/supplier/onboard') {
      router.replace('/supplier/onboard')
    }
    return
  }

  try {
    const res = await api.get('/supplier/me', { silentError: true })
    const companyName = res?.data?.company_name
    if (companyName) {
      displayName.value = companyName
    }
    supplierStatus.value = res?.data?.status || supplierStatus.value
    localStorage.setItem('supplier_status', supplierStatus.value || '')
    if (res?.data?.member_status) {
      localStorage.setItem('member_status', res.data.member_status)
    }
    if (res?.data?.status === 'approved' && res?.data?.member_status === 'active') {
      boundStatus.value = 'bound'
      localStorage.setItem('bound_status', 'bound')
    }
    if (boundStatus.value !== 'bound' && supplierStatus.value !== 'approved') {
      if (route.path !== '/supplier/onboard') {
        router.replace('/supplier/onboard')
      }
    }
  } catch (error) {
    console.error('Failed to fetch supplier profile', error)
    if ([403, 404].includes(error.response?.status) && route.path !== '/supplier/onboard') {
      boundStatus.value = ''
      supplierStatus.value = ''
      localStorage.removeItem('bound_status')
      localStorage.removeItem('supplier_status')
      localStorage.removeItem('member_status')
      router.replace('/supplier/onboard')
    }
  }
}

const handleResize = () => {
  isMobile.value = window.innerWidth <= 768
  if (!isMobile.value) {
    mobileMenuVisible.value = false
  }
}

const clearSupplierAuth = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('department')
  localStorage.removeItem('username')
  localStorage.removeItem('supplier_id')
  localStorage.removeItem('supplier_name')
  localStorage.removeItem('supplier_status')
  localStorage.removeItem('member_status')
  localStorage.removeItem('bound_status')
}

onMounted(() => {
  fetchSupplierDisplayName()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

const handleCommand = (command) => {
  if (command === 'logout') {
    clearSupplierAuth()
    router.push('/login')
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100%;
}

.main-container {
  height: 100%;
}

.aside {
  background-color: #304156;
  color: white;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #1f2d3d;
}

.logo h2 {
  margin: 0;
  font-size: 18px;
  color: #fff;
  white-space: nowrap;
}

.el-menu-vertical {
  border-right: none;
  flex: 1;
}

.header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 10;
}

.header-left {
  display: flex;
  align-items: center;
}

.header-left h3 {
  margin: 0;
  color: #303133;
  font-weight: 500;
  font-size: 18px;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  color: #606266;
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  position: relative;
  min-height: 0;
  overflow: auto;
}

.menu-toggle-btn {
  margin-right: 6px;
  font-size: 18px;
}

.mobile-drawer-logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #1f2d3d;
  background: #304156;
}

.mobile-drawer-logo h2 {
  margin: 0;
  font-size: 16px;
  color: #fff;
}

.mobile-menu {
  height: calc(100% - 56px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .header {
    padding: 0 12px;
  }

  .header-left h3 {
    font-size: 16px;
  }

  .user-info {
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .main-content {
    padding: 10px;
  }
}
</style>
