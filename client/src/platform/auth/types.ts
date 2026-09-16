import type { UserProfile } from '@/services/api'

/**
 * 平台登录适配器接口。
 *
 * 业务代码只调用 `authAdapter.loginSilent()` / `authAdapter.upgradeRealOpenid()`，
 * 不关心当前是微信 / 抖音 / H5，由工厂按 `process.env.TARO_ENV` 选择实现。
 */
export interface AuthResult {
  token: string
  user: UserProfile
}

export interface AuthAdapter {
  /**
   * 静默登录：调 `Taro.login` 拿 code → 调后端对应 endpoint 换 token。
   * 返回 null 表示失败（用户拒绝 / 网络异常 / 后端报错），不抛错。
   */
  loginSilent(): Promise<AuthResult | null>

  /**
   * 沙盒账号升级为真实 openid 账号（自愈逻辑）：
   * - 当前 profile 非沙盒 → 直接 true
   * - 沙盒账号 → 重新调 loginSilent，后端按旧 token 就地升级 openid
   *   （user_id 与收藏/报名数据全部保留）
   * 返回是否升级成功，失败不抛错。
   */
  upgradeRealOpenid(): Promise<boolean>

  /**
   * 取当前小程序真实 appid，后端按 appid 精确匹配 secret，
   * 避免 A 小程序 appid 配 B 小程序 secret 导致 invalid appsecret。
   * 非小程序端（H5）返回 undefined。
   */
  getAppId(): string | undefined
}
