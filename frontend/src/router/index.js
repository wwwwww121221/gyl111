import { createRouter, createWebHistory } from 'vue-router'
import { jwtDecode } from 'jwt-decode'
import SupplierWarning from '../views/SupplierWarning.vue'
import WarehouseWarning from '../views/WarehouseWarning.vue'
import Login from '../views/Login.vue'
import MainLayout from '../layout/MainLayout.vue'
import Register from '../views/Register.vue'
import SupplierLayout from '../layout/SupplierLayout.vue'
import WechatCallback from '../views/WechatCallback.vue'
import WechatBind from '../views/WechatBind.vue'

const clearAuth = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('role')
  localStorage.removeItem('department')
  localStorage.removeItem('username')
  localStorage.removeItem('supplier_id')
  localStorage.removeItem('supplier_name')
  localStorage.removeItem('supplier_status')
  localStorage.removeItem('member_status')
}

const getSupplierHomePath = () => {
  const supplierStatus = localStorage.getItem('supplier_status')
  return supplierStatus === 'approved' ? '/supplier/inquiries' : '/supplier/company-info'
}

const isTokenValid = (token) => {
  if (!token) return false
  try {
    const decoded = jwtDecode(token)
    if (!decoded?.exp) return true
    return decoded.exp * 1000 > Date.now()
  } catch {
    return false
  }
}

const isScoringOnlyUser = () => {
  const role = localStorage.getItem('role') || ''
  if (['admin', 'buyer_manager'].includes(role)) return false
  return role === 'scorer'
}

const routes = [
  {
    path: '/',
    redirect: () => {
      const token = localStorage.getItem('token')
      const role = localStorage.getItem('role')
      if (!isTokenValid(token)) {
        clearAuth()
        return '/login'
      }
      if (role === 'supplier') {
        return getSupplierHomePath()
      }
      if (isScoringOnlyUser()) {
        return '/suppliers/assessment-scoring'
      }
      return '/dashboard'
    }
  },
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: Register,
    meta: { requiresAuth: false }
  },
  {
    path: '/wechat/callback',
    name: 'WechatCallback',
    component: WechatCallback,
    meta: { requiresAuth: false }
  },
  {
    path: '/wechat/bind',
    name: 'WechatBind',
    component: WechatBind,
    meta: { requiresAuth: false }
  },
  {
    path: '/dashboard',
    component: MainLayout,
    redirect: '/dashboard/supplier',
    children: [
      {
        path: 'supplier',
        name: 'SupplierWarning',
        component: SupplierWarning,
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'warehouse',
        name: 'WarehouseWarning',
        component: WarehouseWarning,
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      }
    ]
  },
  {
    path: '/inquiries',
    component: MainLayout,
    redirect: '/inquiries/requests',
    children: [
      {
        path: 'requests',
        name: 'PurchaseRequests',
        component: () => import('../views/inquiries/PurchaseRequests.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'tasks',
        name: 'InquiryTasks',
        component: () => import('../views/inquiries/InquiryTasks.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'compare',
        name: 'IntelligentCompare',
        component: () => import('../views/inquiry/IntelligentCompare.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'contracts',
        name: 'ContractManagement',
        component: () => import('../views/ContractManagement.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'templates',
        name: 'TemplateManagement',
        component: () => import('../views/TemplateManagement.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      }
    ]
  },
  {
    path: '/suppliers',
    component: MainLayout,
    redirect: '/suppliers/manage',
    children: [
      {
        path: 'manage',
        name: 'SupplierManagement',
        component: () => import('../views/suppliers/SupplierManagement.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'pending',
        name: 'SupplierPending',
        component: () => import('../views/suppliers/SupplierPending.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'assessment',
        name: 'AssessmentManagement',
        component: () => import('../views/assessment/AssessmentManagement.vue'),
        meta: { requiresRole: ['admin', 'buyer_manager'] }
      },
      {
        path: 'assessment-scoring',
        name: 'AssessmentScoring',
        component: () => import('../views/assessment/AssessmentScoring.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'], allowScoringUser: true }
      },
      {
        path: 'assessment-summary',
        name: 'AssessmentSummary',
        component: () => import('../views/assessment/AssessmentSummary.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      }
    ]
  },
  {
    path: '/analysis',
    component: MainLayout,
    redirect: '/analysis/supplier',
    children: [
      {
        path: 'supplier',
        name: 'SupplierAnalysis',
        component: () => import('../views/analysis/SupplierAnalysis.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'material',
        name: 'MaterialAnalysis',
        component: () => import('../views/analysis/MaterialAnalysis.vue'),
        meta: { requiresRole: ['admin', 'buyer', 'buyer_manager'] }
      },
      {
        path: 'buyer',
        name: 'BuyerAnalysis',
        component: () => import('../views/analysis/BuyerAnalysis.vue'),
        meta: { requiresRole: ['admin', 'buyer_manager'] } // 管理角色可看采购员分析
      }
    ]
  },
  {
    path: '/system',
    component: MainLayout,
    redirect: '/system/users',
    children: [
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('../views/UserManagement.vue'),
        meta: { requiresRole: ['admin', 'buyer_manager'] } // 管理角色可访问
      },
      {
        path: 'logs',
        name: 'OperationLogs',
        component: () => import('../views/OperationLogs.vue'),
        meta: { requiresRole: ['admin', 'buyer_manager'] } // 管理角色可访问
      }
    ]
  },
  {
    path: '/contracts',
    redirect: '/inquiries/contracts'
  },
  {
    path: '/templates',
    redirect: '/inquiries/templates'
  },
  {
    path: '/supplier',
    component: SupplierLayout,
    children: [
      {
        path: 'inquiries',
        name: 'MyInquiries',
        component: () => import('../views/supplier/MyInquiries.vue'),
        meta: { requiresRole: ['supplier'] }
      },
      {
        path: 'warnings',
        name: 'MyWarnings',
        component: () => import('../views/supplier/MyWarnings.vue'),
        meta: { requiresRole: ['supplier'] }
      },
      {
        path: 'members',
        name: 'MemberRequests',
        component: () => import('../views/supplier/MemberRequests.vue'),
        meta: { requiresRole: ['supplier'] }
      },
      {
        path: 'company-info',
        name: 'CompanyInfo',
        component: () => import('../views/supplier/CompanyInfo.vue'),
        meta: { requiresRole: ['supplier'] }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation Guard
router.beforeEach((to, from) => {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  const tokenValid = isTokenValid(token)
  
  if (to.meta.requiresAuth === false) {
    if (tokenValid && to.path === '/login') {
      return '/' // 已经登录就不要去login了
    }
    return true
  }

  if (!tokenValid) {
    clearAuth()
    return '/login'
  }

  // Check role authorization
  if (to.meta.requiresRole && !to.meta.requiresRole.includes(role)) {
    if (to.meta.allowScoringUser && isScoringOnlyUser()) {
      return true
    }
    if (isScoringOnlyUser()) {
      return '/suppliers/assessment-scoring'
    }
    // Role not authorized
    if (!role) {
      localStorage.removeItem('token')
      return '/login'
    }
    if (role === 'supplier') {
      const supplierHomePath = getSupplierHomePath()
      if (to.path !== supplierHomePath) {
        return supplierHomePath
      }
    } else {
      if (to.path !== '/dashboard') {
        return '/dashboard'
      }
    }
  }

  if (isScoringOnlyUser() && to.path !== '/suppliers/assessment-scoring') {
    return '/suppliers/assessment-scoring'
  }

  if (role === 'supplier' && localStorage.getItem('supplier_status') !== 'approved' && to.path !== '/supplier/company-info') {
    return '/supplier/company-info'
  }

  return true
})

export default router
