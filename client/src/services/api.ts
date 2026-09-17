import Taro from '@tarojs/taro'

// 优先级：TARO_APP_API_BASE（显式覆盖）> production 用域名 > dev 默认（局域网 IP，手机可访问）
//   模拟器调试：默认局域网 IP 192.168.1.4:8000 也兼容 PC 浏览器
//   真机预览/扫码调试：直接用默认值即可，如需改 IP 设 TARO_APP_API_BASE 环境变量
// 开发期注意：project.config.json 的 urlCheck=false 已关闭合法域名校验，http 协议随意用。
//
// ⚠️ 关键：必须「直接」书写 process.env.XXX 字面量，不能有任何运行时包装。
//
//   Taro 的 DefinePlugin 只会把代码里**静态出现**的 `process.env.NODE_ENV`
//   替换成字符串字面量。一旦写成下面这种"防御式"形式：
//
//       typeof process !== 'undefined' && process && process.env
//         ? process.env.NODE_ENV : 'default'
//
//   编译后 `process.env.NODE_ENV` 虽然被替换成了 "production"，但整段仍然被
//   `typeof process !== 'undefined'` 守卫着 —— 小程序运行时没有 process 全局，
//   条件恒为 false，于是永远拿不到注入值，静默回退到 fallback（连局域网 IP）。
//
//   正确做法：编译期直接用字面量比较，运行时不做任何 process 检测。
const DEFAULT_DEV = 'http://192.168.1.4:8000'
const DEFAULT_PROD = 'https://marathoninfo.top'

// eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
const _injectedApiBase: string = process.env.TARO_APP_API_BASE || ''
// eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
const _injectedNodeEnv: string = process.env.NODE_ENV || 'development'

const _isProd = _injectedNodeEnv === 'production'

export const API_BASE_URL =
  _injectedApiBase !== ''
    ? _injectedApiBase
    : _isProd
      ? DEFAULT_PROD
      : DEFAULT_DEV

const BASE_URL = `${API_BASE_URL}/api/v1`
const REQUEST_TIMEOUT = 15000
const MAX_RETRY = 1

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: any
  header?: Record<string, string>
  timeout?: number
  retry?: number
}

function getAuthHeader(): Record<string, string> {
  const token = Taro.getStorageSync('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function isRetryableError(err: any): boolean {
  const msg = String(err?.errMsg || err?.message || '').toLowerCase()
  return msg.includes('timeout') || msg.includes('network') || msg.includes('econnrefused')
}

/** 补全头像/封面相对路径为完整 URL */
export function resolveUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('preset://') || url.startsWith('wxfile://')) return url
  return `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`
}

async function request<T = any>(options: RequestOptions): Promise<T> {
  const {
    url,
    method = 'GET',
    data,
    header = {},
    timeout = REQUEST_TIMEOUT,
    retry = MAX_RETRY
  } = options
  const fullUrl = `${BASE_URL}${url}`

  for (let attempt = 0; attempt <= retry; attempt++) {
    try {
      const res = await Taro.request({
        url: fullUrl,
        method,
        data,
        timeout,
        header: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
          ...header
        }
      })
      if (res.statusCode >= 200 && res.statusCode < 300) {
        return res.data as T
      }
      if (res.statusCode === 401) {
        Taro.removeStorageSync('token')
        Taro.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
        throw { statusCode: 401, message: '未授权' }
      }
      const errorData = res.data as any
      const errMsg = (errorData && (errorData.detail || errorData.message)) || `请求失败 (${res.statusCode})`
      throw { statusCode: res.statusCode, message: errMsg }
    } catch (err: any) {
      if (attempt < retry && isRetryableError(err)) {
        await new Promise((r) => setTimeout(r, 500))
        continue
      }
      throw err
    }
  }
  throw new Error('请求失败')
}

// ====== 事件接口 ======
export interface EventBrief {
  event_id: number
  event_name: string
  cover_image?: string
  event_type: number
  event_type_label: string
  event_status: number
  event_status_label: string
  event_level: number
  event_level_label: string
  start_time?: string
  start_date_label?: string
  location?: string
  province?: string
  city?: string
  registration_fee?: number
  is_hot: number
  is_recommended: number
  favorite_count: number
  registration_count: number
}

export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface EventFilters {
  types: { value: number; label: string }[]
  levels: { value: number; label: string }[]
  statuses: { value: number; label: string }[]
  months: string[]
  provinces: string[]
}

export interface EventStats {
  total: number
  registering: number
  upcoming: number
  finished: number
}

export interface EventDetail extends EventBrief {
  end_time?: string
  registration_start_time?: string
  registration_end_time?: string
  registration_link?: string
  registration_qr_code?: string
  address?: string
  introduction?: string
  description?: string
  route_map?: string
  registration_guide?: string
  refund_policy?: string
  contact_phone?: string
  contact_email?: string
  organizer?: string
  max_participants: number
  current_participants: number
  is_favorite: boolean
  // enrich 流水线富字段
  items_json?: { type: string; fee?: number; scale?: number }[]
  certification?: string
  lottery_history?: string
  registration_channels?: string
  start_point?: string
  end_point?: string
  event_year?: number
}

export interface UserProfile {
  user_id: number
  nickname?: string
  avatar?: string
  username?: string
  runner_level?: string
  runner_no?: string
  /** 0未设置 1男 2女 */
  gender?: number
  /** 年龄段 0未设置 1=34岁以下 2-7=35~64 各5岁一档 8=65岁以上 */
  age_group?: number
  /** 是否 dev_ 沙盒账号（后端 WECHAT_APP_SECRET 缺失期产物） */
  is_sandbox?: boolean
}

/** 取当前登录态 token（未登录返回空串）*/
function _authBearer(): Record<string, string> {
  try {
    const t = Taro.getStorageSync('token') || ''
    return t ? { Authorization: `Bearer ${String(t)}` } : {}
  } catch {
    return {}
  }
}

export interface UploadAvatarResult {
  url: string
}

export interface RankingItem {
  rank: number
  user_id: number
  nickname: string
  avatar?: string | null
  gender?: number
  age_group?: number
  value: number
  value_label: string
  finished_count: number
  registered_count: number
}

export interface RankingListOut {
  metric: string
  gender: number
  age_group: number
  items: RankingItem[]
  my_rank: RankingItem | null
  my_value: number | null
  my_value_label: string | null
  my_insight: string | null
  total_users: number
}

export interface RankingQuery {
  metric?: 'distance' | 'half_marathon_pb' | 'full_marathon_pb' | 'spent'
  gender?: number  // 0全部 1男 2女
  age_group?: number  // 0全部 1..8
  limit?: number
}

export const api = {
  // 事件
  getEvents(params: Record<string, any> = {}): Promise<Page<EventBrief>> {
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
      .join('&')
    return request({ url: `/events${qs ? `?${qs}` : ''}` })
  },
  getEventFilters(): Promise<EventFilters> {
    return request({ url: '/events/filters' })
  },
  getEventStats(): Promise<EventStats> {
    return request({ url: '/events/stats' })
  },
  getEvent(id: number): Promise<EventDetail> {
    return request({ url: `/events/${id}` })
  },
  favoriteEvent(id: number): Promise<{ ok: boolean }> {
    return request({ url: `/events/${id}/favorite`, method: 'POST' })
  },
  unfavoriteEvent(id: number): Promise<{ ok: boolean }> {
    return request({ url: `/events/${id}/favorite`, method: 'DELETE' })
  },

  // 关注
  getFavorites(params: { page?: number; page_size?: number } = {}): Promise<Page<any>> {
    const qs = `page=${params.page || 1}&page_size=${params.page_size || 20}`
    return request({ url: `/favorites?${qs}` })
  },
  getFavoriteStats(): Promise<any> {
    return request({ url: '/favorites/stats' })
  },

  // 报名状态
  updateRegistration(eventId: number, payload: Record<string, any>): Promise<{ ok: boolean }> {
    return request({ url: `/events/${eventId}/registration`, method: 'PUT', data: payload })
  },
  updateCustomRegistration(customEventId: number, payload: Record<string, any>): Promise<{ ok: boolean }> {
    return request({ url: `/custom-events/${customEventId}/registration`, method: 'PUT', data: payload })
  },
  addRace(payload: Record<string, any>): Promise<{ event_id?: number; custom_event_id?: number; favorite_id: number; registration_id: number }> {
    return request({ url: '/races', method: 'POST', data: payload })
  },
  deleteCustomRace(customEventId: number): Promise<{ ok: boolean }> {
    return request({ url: `/races/${customEventId}`, method: 'DELETE' })
  },

  // ====== 用户 ======
  /**
   * 微信静默登录（启动自动调）
   * 经验修正(646739)：必须传真实 appid，后端按 appid 精确匹配 secret，避免 A 小程序
   * appid 配 B 小程序 secret 导致 invalid appsecret。
   */
  loginWechat(
    code: string,
    opts?: { appid?: string; nickname?: string; avatar?: string }
  ): Promise<any> {
    const { appid, nickname, avatar } = opts || {}
    return request({
      url: '/users/login/wechat',
      method: 'POST',
      data: { code, appid, nickname, avatar }
    })
  },
  /**
   * 抖音 / 字节跳动小程序静默登录。
   * 抖音 Taro.login 拿到的 code 与微信不通用，必须走专属 endpoint，
   * 后端按 appid 匹配抖音 secret 调字节 jscode2session。
   * 字节系一个 appid 自动覆盖抖音 + 抖音极速版 + 今日头条 + 今日头条极速版 4 端。
   */
  loginDouyin(
    code: string,
    opts?: { appid?: string; nickname?: string; avatar?: string }
  ): Promise<any> {
    const { appid, nickname, avatar } = opts || {}
    return request({
      url: '/users/login/douyin',
      method: 'POST',
      data: { code, appid, nickname, avatar }
    })
  },
  loginPassword(username: string, password: string): Promise<any> {
    return request({
      url: '/users/login/password',
      method: 'POST',
      data: { username, password }
    })
  },
  getMe(): Promise<UserProfile> {
    return request({ url: '/users/me' }) as Promise<UserProfile>
  },
  updateMe(data: { nickname?: string; avatar?: string; gender?: number; age_group?: number }): Promise<UserProfile> {
    return request({ url: '/users/me', method: 'PUT', data }) as Promise<UserProfile>
  },
  getMyStats(): Promise<any> {
    return request({ url: '/users/me/stats' })
  },
  logout(): Promise<{ ok: boolean }> {
    return request({ url: '/users/logout', method: 'POST' })
  },

  // ====== 跑者排行 ======
  listRankings(q: RankingQuery = {}): Promise<RankingListOut> {
    const qs = Object.entries(q)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
      .join('&')
    return request({ url: `/rankings${qs ? `?${qs}` : ''}` }) as Promise<RankingListOut>
  },

  /**
   * 上传头像到后端（POST /api/v1/users/avatar，form-data name=file）。
   * - MP-WEIXIN：filePath 是 wx.chooseImage / chooseAvatar 返回的 tempFilePath
   * - H5：filePath 可以是临时路径、blob URL 或本地路径，Taro.uploadFile 自动兼容
   */
  async uploadAvatar(filePath: string): Promise<UploadAvatarResult> {
    if (!filePath) throw new Error('未选择头像')
    return new Promise<UploadAvatarResult>((resolve, reject) => {
      Taro.uploadFile({
        url: `${BASE_URL}/users/avatar`,
        filePath,
        name: 'file',
        header: {
          ..._authBearer()
        },
        success: (res) => {
          try {
            const data = typeof res.data === 'string' ? JSON.parse(res.data) : res.data
            if (data && typeof data.url === 'string') {
              resolve({ url: data.url })
              return
            }
            const msg = data?.detail || data?.message || '上传失败'
            reject(new Error(msg))
          } catch (e) {
            reject(new Error('上传响应解析失败'))
          }
        },
        fail: (err) => reject(err)
      })
    })
  }
}

export default api
