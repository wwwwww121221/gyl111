<template>
  <div class="layout-container">
    <el-container>
      <el-aside v-if="!isMobileViewport" width="240px" class="modern-sidebar">
        <div class="sidebar-header">
          <div class="logo">
            <div class="logo-icon">SCM</div>
            <div class="logo-content">
              <div class="logo-title">julan</div>
              <div class="logo-subtitle">采购协同平台</div>
            </div>
          </div>
        </div>

        <el-menu
          :default-active="activeMenu"
          class="modern-menu"
          background-color="transparent"
          text-color="var(--text-secondary)"
          active-text-color="var(--primary-color)"
          router
        >
          <template v-if="!isScoringOnlyUser">
            <el-sub-menu index="/inquiries" class="sub-menu">
              <template #title>
                <el-icon class="menu-icon"><List /></el-icon>
                <span class="menu-text">询价管理</span>
              </template>
              <el-menu-item index="/inquiries/requests" class="submenu-item">采购申请列表</el-menu-item>
              <el-menu-item index="/inquiries/compare" class="submenu-item">智能比价工作台</el-menu-item>
              <el-menu-item index="/inquiries/tasks" class="submenu-item">询价任务</el-menu-item>
              <el-menu-item index="/inquiries/contracts" class="submenu-item">合同管理</el-menu-item>
              <el-menu-item index="/inquiries/templates" class="submenu-item">模板设置</el-menu-item>
            </el-sub-menu>

            <el-sub-menu index="/dashboard" class="sub-menu">
              <template #title>
                <el-icon class="menu-icon"><DataBoard /></el-icon>
                <span class="menu-text">预警管理</span>
              </template>
              <el-menu-item index="/dashboard/supplier" class="submenu-item">供应商预警</el-menu-item>
              <el-menu-item index="/dashboard/warehouse" class="submenu-item">仓库预警</el-menu-item>
            </el-sub-menu>

            <el-sub-menu index="/analysis" class="sub-menu">
              <template #title>
                <el-icon class="menu-icon"><PieChart /></el-icon>
                <span class="menu-text">统计分析</span>
              </template>
              <el-menu-item index="/analysis/supplier" class="submenu-item">供应商分析</el-menu-item>
              <el-menu-item index="/analysis/material" class="submenu-item">物料分析</el-menu-item>
              <el-menu-item v-if="isAdminLike" index="/analysis/buyer" class="submenu-item">采购员分析</el-menu-item>
            </el-sub-menu>

            <el-sub-menu index="/suppliers" class="sub-menu">
              <template #title>
                <el-icon class="menu-icon"><User /></el-icon>
                <span class="menu-text">供应商管理</span>
              </template>
              <el-menu-item index="/suppliers/pending" class="submenu-item">待审核供应商</el-menu-item>
              <el-menu-item index="/suppliers/manage" class="submenu-item">供应商名册</el-menu-item>
              <el-menu-item v-if="canManageAssessment" index="/suppliers/assessment" class="submenu-item">考核管理</el-menu-item>
              <el-menu-item index="/suppliers/assessment-scoring" class="submenu-item">部门打分</el-menu-item>
              <el-menu-item index="/suppliers/assessment-summary" class="submenu-item">考核汇总</el-menu-item>
            </el-sub-menu>

            <el-sub-menu v-if="isAdminLike" index="/system" class="sub-menu">
              <template #title>
                <el-icon class="menu-icon"><Setting /></el-icon>
                <span class="menu-text">系统管理</span>
              </template>
              <el-menu-item index="/system/users" class="submenu-item">账号管理</el-menu-item>
              <el-menu-item index="/system/logs" class="submenu-item">操作日志</el-menu-item>
            </el-sub-menu>
          </template>

          <el-menu-item v-if="isScoringOnlyUser" index="/suppliers/assessment-scoring" class="submenu-item">
            <el-icon class="menu-icon"><EditPen /></el-icon>
            <span class="menu-text">部门打分</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-container>
        <el-header>
          <div class="header-left">
            <el-icon class="hamburger" @click="toggleSidebar"><Expand /></el-icon>
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item>{{ currentRouteName }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>

          <div class="header-right">
            <el-dropdown trigger="click" @command="handleUserCommand">
              <span class="el-dropdown-link">
                {{ roleLabel }}
                <span v-if="userDepartment && userRole !== 'admin'">-{{ userDepartment }}</span>
                <span v-if="userName">({{ userName }})</span>
                <el-icon class="el-icon--right"><ArrowDown /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                  <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </el-header>

        <el-main>
          <div class="main-content-wrapper">
            <router-view />
          </div>
        </el-main>
      </el-container>
    </el-container>

    <el-drawer
      v-model="mobileMenuVisible"
      direction="ltr"
      size="280px"
      :with-header="false"
      class="mobile-nav-drawer"
    >
      <div class="sidebar-header mobile-sidebar-header">
        <div class="logo">
          <div class="logo-icon">SCM</div>
          <div class="logo-content">
            <div class="logo-title">julan</div>
            <div class="logo-subtitle">采购协同平台</div>
          </div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        class="modern-menu"
        background-color="transparent"
        text-color="var(--text-secondary)"
        active-text-color="var(--primary-color)"
        router
        @select="handleMenuSelect"
      >
        <template v-if="!isScoringOnlyUser">
          <el-sub-menu index="/inquiries" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><List /></el-icon>
              <span class="menu-text">询价管理</span>
            </template>
            <el-menu-item index="/inquiries/requests" class="submenu-item">采购申请列表</el-menu-item>
            <el-menu-item index="/inquiries/compare" class="submenu-item">智能比价工作台</el-menu-item>
            <el-menu-item index="/inquiries/tasks" class="submenu-item">询价任务</el-menu-item>
            <el-menu-item index="/inquiries/contracts" class="submenu-item">合同管理</el-menu-item>
            <el-menu-item index="/inquiries/templates" class="submenu-item">模板设置</el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="/dashboard" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><DataBoard /></el-icon>
              <span class="menu-text">预警管理</span>
            </template>
            <el-menu-item index="/dashboard/supplier" class="submenu-item">供应商预警</el-menu-item>
            <el-menu-item index="/dashboard/warehouse" class="submenu-item">仓库预警</el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="/analysis" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><PieChart /></el-icon>
              <span class="menu-text">统计分析</span>
            </template>
            <el-menu-item index="/analysis/supplier" class="submenu-item">供应商分析</el-menu-item>
            <el-menu-item index="/analysis/material" class="submenu-item">物料分析</el-menu-item>
            <el-menu-item v-if="isAdminLike" index="/analysis/buyer" class="submenu-item">采购员分析</el-menu-item>
          </el-sub-menu>

          <el-sub-menu index="/suppliers" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><User /></el-icon>
              <span class="menu-text">供应商管理</span>
            </template>
            <el-menu-item index="/suppliers/pending" class="submenu-item">待审核供应商</el-menu-item>
            <el-menu-item index="/suppliers/manage" class="submenu-item">供应商名册</el-menu-item>
            <el-menu-item v-if="canManageAssessment" index="/suppliers/assessment" class="submenu-item">考核管理</el-menu-item>
            <el-menu-item index="/suppliers/assessment-scoring" class="submenu-item">部门打分</el-menu-item>
            <el-menu-item index="/suppliers/assessment-summary" class="submenu-item">考核汇总</el-menu-item>
          </el-sub-menu>

          <el-sub-menu v-if="isAdminLike" index="/system" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><Setting /></el-icon>
              <span class="menu-text">系统管理</span>
            </template>
            <el-menu-item index="/system/users" class="submenu-item">账号管理</el-menu-item>
            <el-menu-item index="/system/logs" class="submenu-item">操作日志</el-menu-item>
          </el-sub-menu>
        </template>

        <el-menu-item v-if="isScoringOnlyUser" index="/suppliers/assessment-scoring" class="submenu-item">
          <el-icon class="menu-icon"><EditPen /></el-icon>
          <span class="menu-text">部门打分</span>
        </el-menu-item>
      </el-menu>
    </el-drawer>

    <el-dialog v-model="profileDialogVisible" title="个人中心" width="420px" destroy-on-close>
      <el-form ref="profileFormRef" :model="profileForm" :rules="profileRules" label-position="top" size="large">
        <el-form-item label="账号">
          <el-input v-model="profileForm.username" disabled />
        </el-form-item>
        <el-form-item label="角色">
          <el-input :model-value="roleLabel" disabled />
        </el-form-item>
        <el-form-item label="所属部门" prop="department">
          <el-input v-model="profileForm.department" placeholder="请输入所属部门" maxlength="30" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="profileForm.phone" placeholder="请输入手机号" maxlength="11" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="profileSaving" @click="saveProfile">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, DataBoard, EditPen, Expand, List, PieChart, Setting, User } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const router = useRouter()
const route = useRoute()
const isMobileViewport = ref(false)
const mobileMenuVisible = ref(false)
const profileDialogVisible = ref(false)
const profileSaving = ref(false)
const profileFormRef = ref(null)
const profileForm = reactive({
  username: '',
  role: '',
  department: '',
  phone: '',
})

const userRole = computed(() => localStorage.getItem('role') || '')
const userName = computed(() => localStorage.getItem('username') || '')
const userDepartment = computed(() => localStorage.getItem('department') || '')
const isAdminLike = computed(() => ['admin', 'buyer_manager'].includes(userRole.value))
const canManageAssessment = computed(() => ['admin', 'buyer_manager'].includes(userRole.value))
const isScoringOnlyUser = computed(() => userRole.value === 'scorer' && !isAdminLike.value)

const roleLabel = computed(() => {
  if (userRole.value === 'admin') return '超级管理员'
  if (userRole.value === 'buyer_manager') return '采购经理'
  if (userRole.value === 'buyer') return '采购员'
  if (userRole.value === 'scorer') return '考核专员'
  return userRole.value || '未知角色'
})

const activeMenu = computed(() => route.path)

const currentRouteName = computed(() => {
  if (route.path === '/agent/workspace') return '采购助手'
  const map = {
    '/dashboard/supplier': '供应商预警',
    '/dashboard/warehouse': '仓库预警',
    '/inquiries/requests': '采购申请列表',
    '/inquiries/compare': '智能比价工作台',
    '/inquiries/tasks': '询价任务',
    '/inquiries/contracts': '合同管理',
    '/inquiries/templates': '模板设置',
    '/suppliers/pending': '待审核供应商',
    '/suppliers/manage': '供应商名册',
    '/suppliers/assessment': '考核管理',
    '/suppliers/assessment-scoring': '部门打分',
    '/suppliers/assessment-summary': '考核汇总',
    '/analysis/supplier': '供应商分析',
    '/analysis/material': '物料分析',
    '/analysis/buyer': '采购员分析',
    '/system/users': '账号管理',
    '/system/logs': '操作日志',
  }
  return map[route.path] || '页面'
})

const syncViewportState = () => {
  isMobileViewport.value = window.innerWidth <= 768
  if (!isMobileViewport.value) {
    mobileMenuVisible.value = false
  }
}

const toggleSidebar = () => {
  if (isMobileViewport.value) {
    mobileMenuVisible.value = !mobileMenuVisible.value
  }
}

const handleMenuSelect = () => {
  if (isMobileViewport.value) {
    mobileMenuVisible.value = false
  }
}

const phoneValidator = (_, value, callback) => {
  const phone = String(value || '').trim()
  if (!phone) {
    callback()
    return
  }
  if (!/^1[3-9]\d{9}$/.test(phone)) {
    callback(new Error('请输入有效的 11 位手机号'))
    return
  }
  callback()
}

const profileRules = {
  phone: [{ validator: phoneValidator, trigger: 'blur' }],
}

const openProfileDialog = async () => {
  profileDialogVisible.value = true
  try {
    const { data } = await api.get('/system/profile', { silentError: true })
    profileForm.username = data.username || ''
    profileForm.role = data.role || ''
    profileForm.department = data.department || ''
    profileForm.phone = data.phone || ''
  } catch (error) {
    profileForm.username = userName.value
    profileForm.role = userRole.value
    profileForm.department = userDepartment.value
    profileForm.phone = ''
    ElMessage.error(error.response?.data?.detail || '获取个人信息失败')
  }
}

const saveProfile = async () => {
  const valid = await profileFormRef.value?.validate().catch(() => false)
  if (!valid) return

  profileSaving.value = true
  try {
    const { data } = await api.put('/system/profile', {
      phone: profileForm.phone || null,
      department: profileForm.department || null,
    })
    localStorage.setItem('department', data.department || '')
    localStorage.setItem('username', data.username || userName.value)
    window.dispatchEvent(new Event('auth-changed'))
    ElMessage.success('个人信息已更新')
    profileDialogVisible.value = false
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    profileSaving.value = false
  }
}

const handleUserCommand = (command) => {
  if (command === 'profile') {
    openProfileDialog()
    return
  }
  if (command === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('department')
    localStorage.removeItem('username')
    window.dispatchEvent(new Event('auth-changed'))
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

onMounted(() => {
  syncViewportState()
  window.addEventListener('resize', syncViewportState)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncViewportState)
})

watch(() => route.fullPath, () => {
  handleMenuSelect()
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background: var(--bg-secondary);
}

.el-container {
  height: 100%;
}

.modern-sidebar {
  background: var(--bg-primary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-md);
}

.sidebar-header {
  padding: var(--space-6) var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.logo-icon {
  min-width: 40px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--primary-color), var(--info-color));
  border-radius: var(--radius-lg);
  color: white;
  font-size: 12px;
  font-weight: 700;
}

.logo-content {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.logo-subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
  font-weight: 500;
}

.modern-menu {
  border-right: none !important;
  background: transparent !important;
  flex: 1;
  padding: var(--space-4) 0;
  overflow-y: auto;
  overflow-x: hidden;
}

:deep(.el-menu) {
  border-right: none;
}

:deep(.el-sub-menu__title) {
  height: 48px !important;
  line-height: 48px !important;
  margin: 0 var(--space-3) !important;
  border-radius: var(--radius-lg) !important;
}

.menu-icon {
  font-size: 18px !important;
  margin-right: var(--space-3) !important;
}

.menu-text {
  font-size: 14px;
  font-weight: 500;
}

:deep(.el-sub-menu__title) {
  color: var(--text-secondary) !important;
  font-weight: 500 !important;
}

:deep(.el-sub-menu__title:hover) {
  background: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
}

:deep(.el-menu--inline) {
  background: transparent !important;
  padding: 0 !important;
}

.submenu-item {
  height: 40px !important;
  line-height: 40px !important;
  margin: 0 var(--space-4) !important;
  padding-left: 48px !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-secondary) !important;
  font-size: 13px !important;
}

.submenu-item:hover {
  background: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
}

.submenu-item.is-active {
  background: var(--primary-color) !important;
  color: white !important;
}

.el-header {
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  line-height: 60px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 var(--space-6);
  z-index: 9;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.hamburger {
  font-size: 20px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: color var(--transition-fast);
}

.hamburger:hover {
  color: var(--text-primary);
}

.header-right {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  cursor: pointer;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  transition: color var(--transition-fast);
}

.el-dropdown-link:hover {
  color: var(--text-primary);
}

.el-main {
  background: var(--bg-secondary);
  padding: 0;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content-wrapper {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

.mobile-sidebar-header {
  padding-bottom: var(--space-4);
}

:deep(.el-breadcrumb__inner) {
  color: var(--text-secondary) !important;
  font-weight: 500;
}

:deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
  color: var(--text-primary) !important;
  font-weight: 600;
}

:deep(.el-breadcrumb__separator) {
  color: var(--text-tertiary) !important;
}

@media (min-width: 769px) {
  .hamburger {
    display: none;
  }
}

@media (max-width: 768px) {
  .el-header {
    padding: 0 var(--space-4);
  }

  .header-left {
    min-width: 0;
    flex: 1;
  }

  :deep(.el-breadcrumb) {
    min-width: 0;
    overflow: hidden;
  }

  :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
    display: inline-block;
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    vertical-align: bottom;
  }

  .header-right {
    margin-left: 12px;
    max-width: 46%;
    overflow: hidden;
  }

  .el-dropdown-link {
    max-width: 100%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .main-content-wrapper {
    overflow-x: hidden;
  }

  :deep(.mobile-nav-drawer .el-drawer__body) {
    padding: 0;
    overflow-y: auto;
  }
}
</style>
