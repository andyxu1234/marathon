import api from '@/services/api'
import type { AuthAdapter, AuthResult } from './types'

/**
 * H5 端登录适配器（开发沙盒）。
 *
 * H5 端没有 Taro.login，使用浏览器 userAgent 后 8 位生成的稳定哈希作为
 * "沙盒 code"，保证同一个浏览器打开始终是同一个用户，便于本地联调。
 *
 * 沙盒账号永远无法升级为真实 openid，upgradeRealOpenid 直接返回 false。
 */
class H5Auth implements AuthAdapter {
  getAppId(): undefined {
    return undefined
  }

  async loginSilent(): Promise<AuthResult | null> {
    try {
      const code = 'h5-sandbox-' + (typeof navigator !== 'undefined'
        ? (navigator.userAgent || '').slice(-8) || 'local'
        : 'local')
      const r = await api.loginWechat(code, { appid: 'h5-dev' })
      // H5 沙盒账号无需真实 secret，复用 wechat endpoint 即可
      // （后端识别 h5-dev appid 走沙盒分支）
      return r?.token ? { token: r.token, user: r.user } : null
    } catch (e) {
      console.warn('[H5Auth] loginSilent 失败', e)
      return null
    }
  }

  async upgradeRealOpenid(): Promise<boolean> {
    // H5 无真实微信登录，沙盒账号保持现状，不折腾
    return false
  }
}

export default new H5Auth()
