import { PropsWithChildren } from 'react'
import Taro, { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import { isMiniProgram } from '@/utils/platform'
import './app.scss'

function App({ children }: PropsWithChildren) {
  const { setLoginReady, ensureLoggedIn, refreshProfile, ensureRealOpenid } = useUserStore()

  useLaunch(() => {
    // 隐藏微信原生 tabBar（原生 tabBar 管页面切换，自绘 TabBar 管视觉展示）
    // 不使用 custom: true，避免 custom-tab-bar 与页面 TabBar 双渲染
    try {
      Taro.hideTabBar({ animation: false })
    } catch (_) { /* ignore */ }

    // 从本地存储恢复登录态
    try {
      const token = Taro.getStorageSync('token') || null
      useUserStore.setState({ token })
      if (token) {
        // 已有 token → 后台拉一次最新资料（不阻塞）
        refreshProfile().catch(() => {})
      }
    } catch (e) {
      console.warn('[App] Failed to load storage:', e)
    }

    // 立即放行页面渲染，登录在后台静默完成
    setLoginReady()

    // 需求 1：进入小程序首页，任何环境（H5/小程序）都自动获取 openid 存 user 表
    ensureLoggedIn().then(async (ok) => {
      if (!ok) return
      // 自愈升级：secret 缺失期产生的 dev_ 沙盒账号 → 静默重登换真实 openid
      // （后端就地升级，user_id 与收藏/报名数据不丢）。失败不阻塞，下次启动重试。
      // 微信 + 抖音两端都需升级，H5 沙盒不折腾（适配器内部直接返回 false）
      if (isMiniProgram) {
        try {
          await ensureRealOpenid()
        } catch (e) {
          console.warn('[App] 沙盒账号升级失败，下次启动自动重试', e)
        }
      }
      refreshProfile().catch(() => {})
    }).catch((e) => {
      console.warn('[App] 自动登录失败', e)
    })
  })

  return children
}

export default App
