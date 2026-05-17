<template>
  <div class="layout-container">
    <el-container>
      <!-- 现代化侧边栏 -->
      <el-aside width="240px" class="modern-sidebar">
        <div class="sidebar-header">
          <div class="logo">
            <div class="logo-icon">📦</div>
            <div class="logo-content">
              <div class="logo-title">julan</div>
              <div class="logo-subtitle">智能采购平台</div>
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
          <!-- 询价管理 -->
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

          <!-- 预警管理 -->
          <el-sub-menu index="/dashboard" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><DataBoard /></el-icon>
              <span class="menu-text">预警管理</span>
            </template>
            <el-menu-item index="/dashboard/supplier" class="submenu-item">供应商预警</el-menu-item>
            <el-menu-item index="/dashboard/warehouse" class="submenu-item">仓库预警</el-menu-item>
          </el-sub-menu>
          
          <!-- 统计分析 -->
          <el-sub-menu index="/analysis" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><PieChart /></el-icon>
              <span class="menu-text">统计分析</span>
            </template>
            <el-menu-item index="/analysis/supplier" class="submenu-item">供应商分析</el-menu-item>
            <el-menu-item index="/analysis/material" class="submenu-item">物料分析</el-menu-item>
            <el-menu-item index="/analysis/buyer" class="submenu-item" v-if="userRole === 'admin'">采购员分析</el-menu-item>
          </el-sub-menu>

          <!-- 供应商管理 -->
          <el-sub-menu index="/suppliers" class="sub-menu">
            <template #title>
              <el-icon class="menu-icon"><User /></el-icon>
              <span class="menu-text">供应商管理</span>
            </template>
            <el-menu-item index="/suppliers/pending" class="submenu-item">待审核供应商</el-menu-item>
            <el-menu-item index="/suppliers/manage" class="submenu-item">供应商名册</el-menu-item>
          </el-sub-menu>
          <!-- 系统管理 (仅管理员) -->
          <el-sub-menu index="/system" class="sub-menu" v-if="userRole === 'admin'">
            <template #title>
              <el-icon class="menu-icon"><Setting /></el-icon>
              <span class="menu-text">系统管理</span>
            </template>
            <el-menu-item index="/system/users" class="submenu-item">账号管理</el-menu-item>
            <el-menu-item index="/system/logs" class="submenu-item">操作日志</el-menu-item>
          </el-sub-menu>
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
            <el-dropdown trigger="click">
              <span class="el-dropdown-link">
                {{ userRole === 'admin' ? '超级管理员' : '采购员' }} <span v-if="userName">({{ userName }})</span> <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </span>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item>个人中心</el-dropdown-item>
                  <el-dropdown-item divided @click="handleLogout">退出登录</el-dropdown-item>
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
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { DataBoard, User, Goods, Expand, ArrowDown, List, PieChart, Setting } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const isCollapse = ref(false)

const userRole = computed(() => localStorage.getItem('role') || '')
const userName = computed(() => localStorage.getItem('username') || '')

const activeMenu = computed(() => {
  return route.path
})

const currentRouteName = computed(() => {
  const map = {
    '/dashboard/supplier': '供应商预警',
    '/dashboard/warehouse': '仓库预警',
    '/inquiries/requests': '采购申请列表',
    '/inquiries/compare': '智能比价工作台',
    '/inquiries/tasks': '询价单',
    '/inquiries/contracts': '合同管理',
    '/inquiries/templates': '模板设置',
    '/suppliers/pending': '待审核供应商',
    '/suppliers/manage': '供应商名册',
    '/analysis/supplier': '供应商分析',
    '/analysis/material': '物料分析',
    '/analysis/buyer': '采购员效能分析',
    '/system/users': '账号管理',
    '/system/logs': '系统操作日志'
  }
  return map[route.path] || '未知页面'
})

const toggleSidebar = () => {
  isCollapse.value = !isCollapse.value
}

const handleLogout = () => {
  localStorage.removeItem('token')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background: var(--bg-secondary);
}

.el-container {
  height: 100%;
}

/* ===== 现代化侧边栏样式 ===== */
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
  font-size: 24px;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--primary-color), var(--info-color));
  border-radius: var(--radius-lg);
  color: white;
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

/* 现代化菜单样式 */
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

/* 菜单项基础样式 */
.menu-item {
  height: 48px !important;
  line-height: 48px !important;
  margin: 0 var(--space-3) !important;
  border-radius: var(--radius-lg) !important;
}

.menu-item :deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  color: var(--text-secondary) !important;
  font-weight: 500 !important;
}

.menu-item :deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
}

.menu-item.is-active {
  background: var(--primary-color) !important;
  color: white !important;
  box-shadow: var(--shadow-sm);
}

.menu-item.is-active :deep(.el-icon),
.menu-item.is-active .menu-text {
  color: white !important;
}

.menu-icon {
  font-size: 18px !important;
  margin-right: var(--space-3) !important;
}

.menu-text {
  font-size: 14px;
  font-weight: 500;
}

/* 子菜单容器样式 */
:deep(.el-sub-menu) {
  margin-bottom: 0;
}

:deep(.el-menu--inline) {
  background: transparent !important;
  padding: 0 !important;
}

/* 子菜单项样式 */
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

/* 侧边栏底部用户信息 */
.sidebar-footer {
  padding: var(--space-4);
  border-top: 1px solid var(--border-color);
  background: var(--bg-secondary);
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-lg);
  transition: background var(--transition-fast);
}

.user-info:hover {
  background: var(--bg-tertiary);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-color), var(--info-color));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.user-details {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.user-role {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ===== 头部样式 ===== */
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
  overflow: hidden; /* 锁定最外层高度，防止页面本身被撑开 */
}

.main-content-wrapper {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 允许 flex child 收缩，防止子元素溢出撑大 wrapper */
  overflow-y: auto; /* 对于没有做 100% 内部限制的页面，允许其在这里滚动 */
}

/* 面包屑样式优化 */
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
</style>
