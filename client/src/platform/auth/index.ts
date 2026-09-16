/**
 * 平台登录适配器工厂。
 *
 * 按 `process.env.TARO_ENV` 编译期常量选择对应实现，未命中平台会被
 * webpack5 当死代码 tree-shake 掉，不会进包体也不会跨端误调用。
 *
 * 业务用法：
 *   import authAdapter from '@/platform/auth'
 *   const r = await authAdapter.loginSilent()
 */
import type { AuthAdapter } from './types'
import WeappAuth from './weapp-auth'
import DouyinAuth from './douyin-auth'
import H5Auth from './h5-auth'

// 静态三元 + import，保证 tree-shaking 生效（不要换 require() 动态加载）
const adapter: AuthAdapter =
  process.env.TARO_ENV === 'weapp' ? WeappAuth :
  process.env.TARO_ENV === 'tt'    ? DouyinAuth :
                                     H5Auth

export default adapter
