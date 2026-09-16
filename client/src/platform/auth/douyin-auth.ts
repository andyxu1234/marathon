import Taro from '@tarojs/taro'
import api from '@/services/api'
import type { AuthAdapter, AuthResult } from './types'

/**
 * 抖音 / 字节跳动小程序登录适配器。
 *
 * 抖音的 Taro.login / Taro.getAccountInfoSync 与微信签名一致，差异仅在后端
 * endpoint：抖音 code 走 /users/login/douyin，后端调字节 jscode2session
 * （https://developer.toutiao.com/api/apps/v2/jscode2session）。
 *
 * 字节系一个 appid 自动覆盖抖音 + 抖音极速版 + 今日头条 + 今日头条极速版 4 端，
 * 此处不再按宿主分流。
 */
class DouyinAuth implements AuthAdapter {
  getAppId(): string | undefined {
    try {
      // 字节小程序 Taro.getAccountInfoSync().miniProgram.appId 同样可用
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
      // 抖音 code 走专属 endpoint，后端按 appid 匹配抖音 secret
      const r = await api.loginDouyin(code, { appid: this.getAppId() })
      return r?.token ? { token: r.token, user: r.user } : null
    } catch (e) {
      console.warn('[DouyinAuth] loginSilent 失败', e)
      return null
    }
  }

  async upgradeRealOpenid(): Promise<boolean> {
    const r = await this.loginSilent()
    return !!r?.token
  }
}

export default new DouyinAuth()
