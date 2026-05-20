<template>
  <div class="login-container">
    <div class="login-box">
      <!-- 左侧品牌展示区 -->
      <div class="login-left">
        <div class="logo-area">
          <div class="logo-icon">📦</div>
          <div class="logo-text">julan</div>
        </div>
        <div class="slogan-area">
          <h2 class="slogan-title">供应链智能管理系统</h2>
          <p>智能化采购比价 · 高效协同 · 数据驱动</p>
        </div>
        <div class="decorative-shapes">
          <div class="shape-circle-1"></div>
          <div class="shape-circle-2"></div>
          <div class="shape-dots"></div>
        </div>
      </div>

      <!-- 右侧登录表单区 -->
      <div class="login-right">
        <div class="login-form-container">
          <div class="mobile-logo">📦 julan</div>
          <h3 class="form-title">欢迎登录</h3>
          <p class="form-subtitle">请输入您的账号密码进入系统</p>

          <el-form ref="formRef" :model="loginForm" :rules="rules" size="large">
            <el-form-item prop="username">
              <el-input 
                v-model="loginForm.username" 
                prefix-icon="User" 
                placeholder="手机号 / 账号" 
                class="custom-input"
              />
            </el-form-item>
            <el-form-item prop="password">
              <el-input 
                v-model="loginForm.password" 
                prefix-icon="Lock" 
                type="password" 
                placeholder="密码" 
                show-password
                class="custom-input"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            
            <div class="form-actions">
              <el-checkbox v-model="rememberMe">记住账号</el-checkbox>
              <el-button link type="primary" @click="router.push('/register')">供应商入驻注册</el-button>
            </div>

            <el-form-item>
              <el-button type="primary" :loading="loading" class="submit-btn" @click="handleLogin">
                登 录
              </el-button>
            </el-form-item>
          </el-form>
          
          <div class="form-footer">
            <span class="copyright">© 2026 Supply Chain Agent. All rights reserved.</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const rememberMe = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

onMounted(() => {
  const savedUsername = localStorage.getItem('saved_username')
  if (savedUsername) {
    loginForm.username = savedUsername
    rememberMe.value = true
  }
})

const handleLogin = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        // 使用 URLSearchParams 格式发送 form data，因为后端 OAuth2PasswordRequestForm 需要
        const params = new URLSearchParams()
        params.append('username', loginForm.username)
        params.append('password', loginForm.password)

        const res = await axios.post('/api/auth/login', params, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        })
        
        const { access_token, role, username, department } = res.data
        localStorage.setItem('token', access_token)
        localStorage.setItem('role', role)
        localStorage.setItem('department', department || '')
        if (username) {
          localStorage.setItem('username', username)
        } else {
          // Fallback just in case
          localStorage.setItem('username', loginForm.username)
        }

        if (rememberMe.value) {
          localStorage.setItem('saved_username', loginForm.username)
        } else {
          localStorage.removeItem('saved_username')
        }
        
        ElMessage.success('登录成功')
        
        // 根据角色跳转不同页面
        if (role === 'supplier') {
          router.push('/supplier/inquiries')
        } else {
          router.push('/')
        }
      } catch (error) {
        console.error('Login failed:', error)
        if (error.response && error.response.data && error.response.data.detail) {
          ElMessage.error(error.response.data.detail)
        } else {
          ElMessage.error('登录失败：网络错误或服务异常')
        }
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: var(--bg-secondary);
  background-image: radial-gradient(var(--border-color) 1px, transparent 1px);
  background-size: 20px 20px;
}

.login-box {
  display: flex;
  width: 960px;
  height: 560px;
  background: var(--bg-primary);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
}

/* 左侧区域 */
.login-left {
  position: relative;
  width: 440px;
  background: linear-gradient(135deg, var(--primary-color), var(--info-color));
  color: white;
  padding: 48px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.logo-area {
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 2;
}

.logo-icon {
  font-size: 28px;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.2);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(4px);
}

.logo-text {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.slogan-area {
  margin-top: auto;
  margin-bottom: 60px;
  z-index: 2;
}

.slogan-title {
  font-size: 32px;
  font-weight: 600;
  margin: 0 0 16px 0;
  line-height: 1.3;
  color: #ffffff;
}

.slogan-area p {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.85);
  margin: 0;
}

/* 左侧装饰图形 */
.decorative-shapes {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.shape-circle-1 {
  position: absolute;
  top: -100px;
  right: -50px;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0));
}

.shape-circle-2 {
  position: absolute;
  bottom: -80px;
  left: -80px;
  width: 250px;
  height: 250px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.1);
}

/* 右侧表单区 */
.login-right {
  flex: 1;
  padding: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
}

.login-form-container {
  width: 100%;
  max-width: 360px;
}

.mobile-logo {
  display: none;
  font-size: 24px;
  font-weight: bold;
  color: var(--primary-color);
  margin-bottom: 30px;
  text-align: center;
}

.form-title {
  font-size: 28px;
  color: var(--text-primary);
  margin: 0 0 8px 0;
  font-weight: 600;
}

.form-subtitle {
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0 0 40px 0;
}

.custom-input :deep(.el-input__wrapper) {
  padding: 8px 15px;
  box-shadow: 0 0 0 1px var(--border-color) inset;
  border-radius: var(--radius-md);
  transition: all var(--transition-normal);
}

.custom-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary-color) inset;
}

.form-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  border-radius: var(--radius-md);
  letter-spacing: 4px;
  font-weight: 600;
  margin-top: 8px;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
  transition: all var(--transition-normal);
}

.submit-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(37, 99, 235, 0.3);
}

.form-footer {
  margin-top: 60px;
  text-align: center;
}

.copyright {
  color: var(--text-muted);
  font-size: 13px;
}

/* 响应式适配 */
@media (max-width: 900px) {
  .login-box {
    width: 90%;
    max-width: 440px;
    height: auto;
    flex-direction: column;
  }
  
  .login-left {
    display: none;
  }
  
  .login-right {
    padding: 40px 30px;
  }

  .mobile-logo {
    display: block;
  }
  
  .form-title {
    text-align: center;
  }
  
  .form-subtitle {
    text-align: center;
  }
  
  .form-footer {
    margin-top: 40px;
  }
}
</style>
