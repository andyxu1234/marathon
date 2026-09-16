import Taro from '@tarojs/taro'
import api from '@/services/api'
import type { AuthAdapter, AuthResult } from './types'

/**
 * 微信小程序登录适配器。
 *
 * 实现原 stores/index.ts 中 ensureLoggedIn / ensureRealOpenid 的 weapp 分支：
 * Taro.login → getAccountInfoSync → POST /users/login/wechat。
 *
 * 经验修正(646739)：必须传真实 appid，后端按 appid 精确匹配 secret。
 */
class WeappAuth implements AuthAdapter {
  getAppId(): string | undefined {
    try {
      // wx.getAccountInfoSync 抖音也支持，但本类仅 weapp 编译期被 import
      const info = Taro.getAccountInfoSync()
      return info?.miniProgram?.appId
    } catch {
      return undefined
    }
  }

  async loginSilent(): Promise<AuthResult | null> {
    try {
      const code = await new Promise<string>((resolve) => {
        Taro.login({
          success: (res) => resolve(res.code || ''),
          fail: () => resolve('')
        })
      })
      if (!code) return null
      const r = await api.loginWechat(code, { appid: this.getAppId() })
      return r?.token ? { token: r.token, user: r.user } : null
    } catch (e) {
      console.warn('[WeappAuth] loginSilent 失败', e)
      return null
    }
  }

  async upgradeRealOpenid(): Promise<boolean> {
    // 复用 loginSilent：后端识别请求头携带的旧 dev_ token，就地升级 openid
    const r = await this.loginSilent()
    return !!r?.token
  }
}

export default new WeappAuth()
