import { create } from 'zustand'
import Taro from '@tarojs/taro'
import api, { UserProfile } from '@/services/api'
import authAdapter from '@/platform/auth'
import { isMiniProgram } from '@/utils/platform'

interface UserState {
  token: string | null
  user: UserProfile | null
  loginReady: boolean
  setLoginReady: () => void
  login: (code: string, opts?: { appid?: string; nickname?: string; avatar?: string }) => Promise<any>
  loginWithPassword: (username: string, password: string) => Promise<any>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
  /** 更新资料（昵称/头像/性别/年龄段），同步更新本地 store */
  updateProfile: (patch: { nickname?: string; avatar?: string; gender?: number; age_group?: number }) => Promise<UserProfile>
  /**
   * 确保有登录态：
   * - 已登录 → 返回 true
   * - 未登录 → 尝试静默登录（MP-WEIXIN：Taro.login；H5：沙盒 code）
   *   成功返回 true，失败返回 false（不抛错，不跳登录页，就是需求 2 提到的
   *   "点关注不需校验是否登录" —— 用户无感知自动完成登录）
   */
  ensureLoggedIn: () => Promise<boolean>
  /**
   * 自愈升级（secret 缺失期产生的 dev_ 沙盒账号 → 真实微信 openid）：
   * - 当前 profile 非沙盒 → 直接 true（真实账号无需升级）
   * - H5 端无真实微信登录 → false（保持沙盒，不折腾）
   * - 小程序端：Taro.login 拿新 code 再登一次。login 请求会自动带旧 dev_ token
   *   （storage 里还在），后端据此识别 current_user → 把 dev_ openid 就地升级为
   *   真实值（user_id 与收藏/报名数据全部保留），返回真实账号的新 token。
   */
  ensureRealOpenid: () => Promise<boolean>
}

export const useUserStore = create<UserState>((set, get) => ({
  token: null,
  user: null,
  loginReady: false,

  setLoginReady: () => set({ loginReady: true }),

  login: async (code: string, opts) => {
    const res = await api.loginWechat(code, opts)
    if (res.token) {
      Taro.setStorageSync('token', res.token)
      set({ token: res.token, user: res.user })
    }
    return res
  },

  loginWithPassword: async (username: string, password: string) => {
    const res = await api.loginPassword(username, password)
    if (res.token) {
      Taro.setStorageSync('token', res.token)
      set({ token: res.token, user: res.user })
    }
    return res
  },

  logout: async () => {
    try {
      await api.logout()
    } catch (e) {
      // 忽略网络错误
    }
    Taro.removeStorageSync('token')
    set({ token: null, user: null })
  },

  refreshProfile: async () => {
    try {
      const me = await api.getMe()
      set({ user: me })
    } catch (e) {
      // 未登录或失败
    }
  },

  updateProfile: async (patch) => {
    const profile = await api.updateMe(patch)
    const state = get()
    set({ user: { ...(state.user || profile), ...profile } })
    return profile
  },

  ensureLoggedIn: async (): Promise<boolean> => {
    // 1. 已经登录（有 token）→ 直接 OK
    if (get().token) return true

    // 2. 读 storage 里可能已经有的 token（例如 app.ts 刚启动还没 setState 时）
    try {
      const cached = Taro.getStorageSync('token')
      if (cached) {
        set({ token: cached })
        // 顺手拉一下 profile
        try {
          const me = await api.getMe()
          set({ user: me })
        } catch {}
        return true
      }
    } catch {}

    // 3. 委托给平台适配器做静默登录（weapp → /users/login/wechat，
    //    tt → /users/login/douyin，H5 → 沙盒 code），跨端差异由 authAdapter 内部分流
    try {
      const r = await authAdapter.loginSilent()
      if (r?.token) {
        Taro.setStorageSync('token', r.token)
        set({ token: r.token, user: r.user })
        return true
      }
    } catch (e) {
      console.warn('[ensureLogin] 静默登录失败', e)
    }
    return false
  },

  ensureRealOpenid: async (): Promise<boolean> => {
    // 1. user 未就绪时先拉一次 profile 确认（启动早期 ensureLoggedIn 可能短路、user 为 null）
    if (!get().user) {
      try {
        await get().refreshProfile()
      } catch {
        return false
      }
    }
    // 2. 已是真实 openid 账号 → 无需升级
    if (!get().user?.is_sandbox) return true
    // 3. H5 无真实微信/抖音登录（沙盒 code 是设计行为），不升级
    if (!isMiniProgram) return false

    // 4. 小程序端：委托平台适配器（weapp / douyin）换新 code 再登一次。
    //    请求自动带旧 dev_ token → 后端识别 current_user 就地升级 openid，
    //    user_id 与收藏/报名数据全部保留。
    try {
      const ok = await authAdapter.upgradeRealOpenid()
      if (!ok) return false
      // 升级成功后刷新 profile（此时 is_sandbox 应变 false，user_id 不变）
      try {
        await get().refreshProfile()
      } catch {}
      return true
    } catch {
      return false
    }
  }
}))

interface EventFilterState {
  type: number | null
  level: number | null
  status: number | null
  year: number | null
  month: number | null
  province: string | null   // 省：存 ProvinceOption.matchName（不带后缀，如 "江苏"）
  city: string | null       // 市：存 CityOption.matchName（不带后缀，如 "南京"）
  keyword: string
  setFilter: (key: string, value: any) => void
  resetFilters: () => void
  toParams: () => Record<string, any>
}

// 前端缓存：记住用户上次的过滤条件，进入小程序直接加载
const FILTER_STORAGE_KEY = 'home_filter'

function loadPersistedFilter(): Partial<EventFilterState> {
  try {
    const cached = Taro.getStorageSync(FILTER_STORAGE_KEY)
    if (cached && typeof cached === 'object') {
      const c = cached as any
      return {
        type: typeof c.type === 'number' ? c.type : null,
        level: typeof c.level === 'number' ? c.level : null,
        status: typeof c.status === 'number' ? c.status : null,
        year: typeof c.year === 'number' ? c.year : null,
        month: typeof c.month === 'number' ? c.month : null,
        province: typeof c.province === 'string' ? c.province : null,
        city: typeof c.city === 'string' ? c.city : null,
        keyword: typeof c.keyword === 'string' ? c.keyword : ''
      }
    }
  } catch {}
  return {}
}

function persistFilter(state: EventFilterState) {
  try {
    Taro.setStorageSync(FILTER_STORAGE_KEY, {
      type: state.type,
      level: state.level,
      status: state.status,
      year: state.year,
      month: state.month,
      province: state.province,
      city: state.city,
      keyword: state.keyword
    })
  } catch {}
}

export const useFilterStore = create<EventFilterState>((set, get) => {
  const persisted = loadPersistedFilter()
  return {
    type: persisted.type ?? null,
    level: persisted.level ?? null,
    status: persisted.status ?? null,
    year: persisted.year ?? null,
    month: persisted.month ?? null,
    province: persisted.province ?? null,
    city: persisted.city ?? null,
    keyword: persisted.keyword ?? '',

    setFilter: (key, value) => {
      // 级联规则：改了 province → 清空 city（选省=全国"时也清空）
      const patch: any = { [key]: value }
      if (key === 'province') patch.city = null
      set(patch)
      persistFilter(get())
    },

    resetFilters: () => {
      set({
        type: null, level: null, status: null,
        year: null, month: null, province: null, city: null, keyword: ''
      })
      try {
        Taro.removeStorageSync(FILTER_STORAGE_KEY)
      } catch {}
    },

    toParams: () => {
      const s = get()
      const p: Record<string, any> = {}
      if (s.type) p.event_type = s.type
      if (s.level) p.event_level = s.level
      if (s.status) p.event_status = s.status
      if (s.year) p.event_year = s.year
      if (s.month) p.month = s.month
      if (s.province) p.province = s.province
      if (s.city) p.city = s.city
      if (s.keyword) p.keyword = s.keyword
      return p
    }
  }
})
