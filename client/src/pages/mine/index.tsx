import { View, Text, Input, Button, Image } from '@tarojs/components'
import { useState, useMemo, useRef } from 'react'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import Icon from '@/components/Icon'
import TabBar from '@/components/TabBar'
import api, { resolveUrl } from '@/services/api'
import { useUserStore } from '@/stores'
import { isWeapp, isDouyin, isMiniProgram } from '@/utils/platform'
import './index.scss'

interface RecentFinishedItem {
  event_id: number
  event_name: string
  start_time: string | null
  finish_time: string | null
  result_status: number
  is_pb: boolean
}
interface NextRaceItem {
  event_id: number | null
  custom_event_id: number | null
  event_name: string
  event_type: number
  event_type_label: string
  start_date: string
  days_away: number
  is_custom: boolean
}
interface MyRankItem {
  metric: string
  rank: number
  total_users: number
  value_label: string
  insight: string | null
}
interface UserStats {
  user_id: number
  nickname: string | null
  avatar: string | null
  runner_level: string
  runner_no: string | null
  gender?: number
  age_group?: number
  registered_count: number       // 报名中
  finished_count: number         // 完赛
  total_spent: number           // 累计花费
  total_distance: number         // 跑步里程
  half_pb: string | null
  full_pb: string | null
  favorited_count: number       // 关注赛事数
  next_race: NextRaceItem | null
  my_rank: MyRankItem | null
  recent_finished: RecentFinishedItem[]
}

/**
 * 年龄段枚举（后端 age_group 列语义保持一致）。
 * 注意必须与 server/app/schemas/user.py 中的 age_group 字段描述同步。
 */
const AGE_GROUPS: { value: number; label: string }[] = [
  { value: 1, label: '34岁以下' },
  { value: 2, label: '35-39岁' },
  { value: 3, label: '40-44岁' },
  { value: 4, label: '45-49岁' },
  { value: 5, label: '50-54岁' },
  { value: 6, label: '55-59岁' },
  { value: 7, label: '60-64岁' },
  { value: 8, label: '65岁以上' },
]
const AGE_LABEL: Record<number, string> = Object.fromEntries(
  AGE_GROUPS.map((g) => [g.value, g.label])
)

/**
 * 跑者等级说明（必须与 server/app/services/user_service.py 的 _runner_level 同步）：
 * 完赛 0 场=新手，1-4 场=跑者，5-9 场=精英跑者，≥10 场=金标跑者。
 */
const RUNNER_LEVELS: { name: string; need: string; desc: string }[] = [
  { name: '新手', need: '完赛 0 场', desc: '开启你的马拉松之旅' },
  { name: '跑者', need: '完赛 1-4 场', desc: '已迈出坚实的第一步' },
  { name: '精英跑者', need: '完赛 5-9 场', desc: '坚持让你与众不同' },
  { name: '金标跑者', need: '完赛 10 场及以上', desc: '赛道上的老朋友' },
]

/**
 * 头像路径归一化（参考 646739 经验修正）：
 *  - chooseAvatar 返回的 http://tmp / wxfile:// 伪路径，Taro.uploadFile 通常可直接处理，
 *    但仍有环境会报 "file not found"，这里做一级兜底：
 *    · http(s)://wx 临时图 / tmp → 先 downloadFile 拿 tempFilePath
 *    · wxfile:// / blob / file → 直接用
 */
async function normalizeAvatarForUpload(src: string): Promise<string> {
  if (!src) throw new Error('图片路径为空')
  if (
    src.startsWith('blob:') ||
    src.startsWith('file://') ||
    src.startsWith('wxfile://')
  ) {
    return src
  }
  if (/^https?:\/\//.test(src)) {
    try {
      const res = await Taro.downloadFile({ url: src })
      if (res.statusCode === 200 && res.tempFilePath) return res.tempFilePath
    } catch (e) {
      console.warn('[normalizeAvatar] downloadFile 失败，尝试直接用', e)
    }
    return src
  }
  return src
}

/**
 * 估算昵称文本宽度（设计px），用于让昵称 Input 的容器宽度贴合文字——
 * 这样容器右沿 == 文字右沿，性别徽章绝对定位在 left:100% 时才能真的贴住昵称，
 * 而不是贴在 min-width 撑出来的留白上（居中文字两侧会各空 (容器宽-文字宽)/2）。
 * 字号需与 scss 中 .profile-name 的 font-size(36px) 保持一致。
 */
const NICK_FONT_SIZE = 36
function estimateNickWidth(s: string): number {
  let w = 0
  for (const ch of Array.from(s)) {
    const cp = ch.codePointAt(0) ?? 0
    if (cp > 0xffff) w += NICK_FONT_SIZE // emoji / 扩展区字符按全角算
    else if (/[\u3000-\u9fff\uff00-\uffef]/.test(ch)) w += NICK_FONT_SIZE // CJK / 全角标点
    else w += NICK_FONT_SIZE * 0.56 // 英数半角
  }
  return w
}
/** 昵称为空时给 placeholder「点击设置昵称」留出的宽度 */
const NICK_EMPTY_WIDTH = 220

/** 昵称是否仍是默认格式（^跑友\d{5,}$）。空昵称也视为默认。 */
function isDefaultNickname(n: string | null | undefined): boolean {
  if (!n) return true
  return /^跑友\d{5,}$/.test(n)
}

export default function Mine() {
  /**
   * isWeapp / isMiniProgram 来自 @/utils/platform，集中管理平台差异点。
   * - isWeapp       仅微信端（Button openType=chooseAvatar 走原生头像面板）
   * - isMiniProgram 微信 + 抖音两端共性（静默登录失败不弹任何提示）
   */
  const [stats, setStats] = useState<UserStats | null>(null)
  /** 头像保存中：picker 关闭到 saveProfile 完成期间禁用再次触发 */
  const [avatarSaving, setAvatarSaving] = useState(false)
  /** 自绘底部 picker：'gender' 性别 / 'age' 年龄段 / null 关闭 */
  const [pickerType, setPickerType] = useState<'gender' | 'age' | null>(null)
  /** 跑者等级说明弹层（点等级 chip 打开，纯展示无操作） */
  const [levelInfoOpen, setLevelInfoOpen] = useState(false)

  const userStore = useUserStore()
  const token = userStore.token || Taro.getStorageSync('token')
  const loggedIn = !!token

  const fetchStats = async () => {
    try {
      const s = await api.getMyStats()
      setStats(s as UserStats)
    } catch (e) {
      console.warn('[Mine] fetchStats failed', e)
    }
  }

  useDidShow(async () => {
    try { Taro.hideTabBar({ animation: false }) } catch (_) {}
    if (!loggedIn) await userStore.ensureLoggedIn()
    userStore.refreshProfile().catch(() => {})
    if (Taro.getStorageSync('token')) fetchStats()
  })

  // 下拉刷新：config 里开了 enablePullDownRefresh，必须实现本回调并
  // 调用 stopPullDownRefresh()，否则转圈动画会一直停不下来。
  usePullDownRefresh(async () => {
    try {
      await userStore.refreshProfile().catch(() => {})
      if (Taro.getStorageSync('token')) await fetchStats()
    } finally {
      Taro.stopPullDownRefresh()
    }
  })

  const user = userStore.user
  const profile = useMemo<UserStats | null>(() => {
    if (stats) return stats
    if (user)
      return {
        user_id: user.user_id,
        nickname: user.nickname || null,
        avatar: user.avatar || null,
        runner_level: user.runner_level || '跑者',
        runner_no: user.runner_no || null,
        gender: user.gender || 0,
        age_group: user.age_group || 0,
        registered_count: 0,
        finished_count: 0,
        total_spent: 0,
        total_distance: 0,
        half_pb: null,
        full_pb: null,
        favorited_count: 0,
        next_race: null,
        my_rank: null,
        recent_finished: [],
      }
    return null
  }, [stats, user])

  const finalAvatarUrl = resolveUrl(profile?.avatar || undefined)

  /** 昵称 Input 宽度：贴合文字，使徽章能紧贴昵称（昵称本身始终居中于头像下方） */
  const nickInputWidth = profile?.nickname
    ? Math.round(estimateNickWidth(profile.nickname)) + 8
    : NICK_EMPTY_WIDTH

  // ============= 头像：选完即上传保存（无草稿、无显式保存按钮） =============
  const saveAvatar = async (tempPath: string) => {
    if (!loggedIn) {
      await userStore.ensureLoggedIn()
      return
    }
    setAvatarSaving(true)
    Taro.showLoading({ title: '上传中', mask: true })
    try {
      const normalized = await normalizeAvatarForUpload(tempPath)
      const up = await api.uploadAvatar(normalized)
      await userStore.updateProfile({ avatar: up.url })
      fetchStats()
      Taro.showToast({ title: '头像已更新', icon: 'success' })
    } catch (e: any) {
      Taro.showToast({ title: '上传失败', icon: 'none' })
    } finally {
      Taro.hideLoading()
      setAvatarSaving(false)
    }
  }

  /** MP-WEIXIN Button[open-type=chooseAvatar] 回调，弹微信原生面板（用微信头像/相册/拍照） */
  const onChooseAvatar = (e: any) => {
    const url = e?.detail?.avatarUrl
    if (url) saveAvatar(url)
  }

  /** 非微信端（H5 + 抖音）：onClick 触发选图
   *  抖音不支持 Button openType=chooseAvatar 原生面板，统一走 Taro.chooseImage */
  const handlePickAvatarNonWeapp = async () => {
    if (!loggedIn) await userStore.ensureLoggedIn()
    try {
      const res: any = await Taro.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera']
      })
      const fp = res?.tempFilePaths?.[0]
        || res?.tempFiles?.[0]?.path
        || res?.tempFiles?.[0]?.tempFilePath
      if (fp) saveAvatar(fp)
    } catch (e) { /* 用户取消 */ }
  }

  /** 抖音专属：一键授权使用抖音头像 + 昵称
   *
   *  tt.getUserProfile 每次调用弹授权，同意后返回抖音头像 CDN URL 和昵称，
   *  头像 URL 是抖音 CDN 直链，需 downloadFile 转本地临时路径后再 uploadFile
   *  存到自己服务器。
   *
   *  ⚠️ 平台合规（2023.6.6 起抖音收紧审核）：
   *     必须在抖音开放平台「设置 → 隐私协议」中声明用户信息 scope，
   *     否则 getUserProfile 直接失败，错误码：
   *       111679 — api scope is not declared in the privacy agreement
   *       111680 — privacy permission is not authorized
   *     另：必须由用户 tap 手势触发，不能自动调用（否则 111601）。
   *
   *  ⚠️ 域名白名单：downloadFile 拉的是抖音 CDN（*.douyinpic.com 等），
   *     需在「开发设置 → 服务器域名 → downloadFile 合法域名」里配置，
   *     否则真机上下载头像会失败。
   */
  const handleUseDouyinProfile = async () => {
    if (!loggedIn) await userStore.ensureLoggedIn()

    Taro.showLoading({ title: '同步中', mask: true })
    try {
      const res: any = await Taro.getUserProfile({
        desc: '用于完善个人资料',
      })
      const userInfo = res?.userInfo
      if (!userInfo) {
        Taro.hideLoading()
        return
      }

      // 1. 昵称直接存
      const newNick = userInfo.nickName
      if (newNick && newNick !== profile?.nickname) {
        await userStore.updateProfile({ nickname: newNick })
      }

      // 2. 头像：抖音 CDN URL → downloadFile 转临时路径 → uploadAvatar
      const avatarUrl = userInfo.avatarUrl
      if (avatarUrl) {
        try {
          const dl = await Taro.downloadFile({ url: avatarUrl })
          if (dl.statusCode === 200 && dl.tempFilePath) {
            const up = await api.uploadAvatar(dl.tempFilePath)
            await userStore.updateProfile({ avatar: up.url })
          }
        } catch (e) {
          console.warn('[DouyinProfile] 头像下载/上传失败', e)
          // 昵称可能已成功，仅提示头像失败
          Taro.hideLoading()
          Taro.showToast({ title: '头像同步失败，请手动选择', icon: 'none' })
          fetchStats()
          return
        }
      }

      await fetchStats()
      Taro.hideLoading()
      Taro.showToast({ title: '已同步抖音资料', icon: 'success' })
    } catch (e: any) {
      Taro.hideLoading()
      // 用户主动拒绝授权 → 静默忽略；其余失败给出可读提示，
      // 便于区分「隐私协议没配」和「用户点了拒绝」。
      const code = e?.errNo ?? e?.errorCode
      const msg = String(e?.errMsg || '')
      const denied = msg.includes('auth deny') || code === 111690
      if (denied) return
      if (code === 111679 || code === 111680) {
        Taro.showToast({ title: '需在抖音后台配置隐私协议', icon: 'none' })
      } else if (code === 111601) {
        Taro.showToast({ title: '请直接点击按钮授权', icon: 'none' })
      } else {
        console.warn('[DouyinProfile] 授权失败', e)
        Taro.showToast({ title: '同步失败，请手动设置', icon: 'none' })
      }
    }
  }

  // ============= 昵称：常驻 Input + type='nickname'
  //   关键：之前用 Text ↔ Input 的 editing 切换，<Text onClick> 在小程序里 tap 不稳，
  //   且切到 Input 后 autoFocus 不一定生效，导致"点了没反应"。
  //   直接让 Input 始终渲染，type='nickname' 在 MP-WEIXIN 上点输入框自动弹
  //   微信昵称选择面板（截图里那个面板），blur/confirm 自动保存。
  // ============================================================
  const nickSavingRef = useRef(false)
  const saveNick = async (next: string) => {
    // 防重复触发（blur + onConfirm 会双触发）
    if (nickSavingRef.current) return
    const v = next?.trim()
    if (!v || v === profile?.nickname) return
    nickSavingRef.current = true
    try {
      await userStore.updateProfile({ nickname: v })
      fetchStats()
      Taro.showToast({ title: '昵称已更新', icon: 'success' })
    } catch {
      Taro.showToast({ title: '保存失败', icon: 'none' })
    } finally {
      nickSavingRef.current = false
    }
  }

  const handleLogin = async () => {
    const ok = await userStore.ensureLoggedIn()
    if (ok) return fetchStats()
    if (isMiniProgram) return // 小程序端静默登录失败不弹任何东西
    // H5 兜底：密码登录
    Taro.showModal({
      title: '开发登录',
      content: '小程序端自动登录；H5 开发期可用密码登录 admin/admin',
      showCancel: true,
      confirmText: '密码登录',
      success: async (r) => {
        if (!r.confirm) return
        try {
          await userStore.loginWithPassword('admin', 'admin')
          Taro.showToast({ title: '登录成功', icon: 'success' })
          fetchStats()
        } catch {
          Taro.showToast({ title: '登录失败', icon: 'none' })
        }
      }
    })
  }

  // ============= 性别：昵称右上角小徽章，点选即存（单态即时保存） =============
  const saveGender = async (g: number) => {
    try {
      await userStore.updateProfile({ gender: g })
      fetchStats()
      Taro.showToast({
        title: g === 1 ? '已设为男性' : g === 2 ? '已设为女性' : '性别已清除',
        icon: 'success'
      })
    } catch {
      Taro.showToast({ title: '保存失败', icon: 'none' })
    }
  }

  /** 自绘底部 picker：与 ActionSheet 体验等价，但视觉跨端一致、可承载更长的列表。 */
  const openGenderPicker = () => {
    if (!loggedIn) {
      handleLogin()
      return
    }
    setPickerType('gender')
  }

  /** 年龄段：8 档，超出 ActionSheet 推荐长度，做成同一个 picker 组件。 */
  const saveAgeGroup = async (v: number) => {
    try {
      await userStore.updateProfile({ age_group: v })
      fetchStats()
      Taro.showToast({ title: '年龄段已更新', icon: 'success' })
    } catch {
      Taro.showToast({ title: '保存失败', icon: 'none' })
    }
  }
  const openAgePicker = () => {
    if (!loggedIn) {
      handleLogin()
      return
    }
    setPickerType('age')
  }
  const closePicker = () => setPickerType(null)

  const handleMenuClick = (key: string) => {
    if (!loggedIn) return handleLogin()
    Taro.showToast({ title: `${key}（开发中）`, icon: 'none' })
  }

  // ============= 副标语："点击头像/昵称修改" 提示 =============
  // 已上传头像 → 不再提示头像修改
  // 昵称已自定义（非默认格式 ^跑友\d{5,}$）→ 不再提示昵称修改
  // 两者都已完成 → 完全隐藏副标语（让头像昵称回归"纯展示"）
  const isAvatarCustomized = !!profile?.avatar
  const isNickCustomized = !isDefaultNickname(profile?.nickname)
  const tapTipParts: string[] = []
  if (!isAvatarCustomized) tapTipParts.push('点击头像更换')
  if (!isNickCustomized) {
      tapTipParts.push(isWeapp ? '点击昵称可使用微信昵称' : isDouyin ? '点击昵称可使用抖音昵称' : '点击昵称修改')
    }
  const tapTipText = tapTipParts.join(' · ')

  const menus = [
    { key: '我的信息', icon: 'user' },
    { key: '赛事提醒', icon: 'bell', badge: 3 },
    { key: '跑步记录', icon: 'footprints' },
    { key: '帮助中心', icon: 'help-circle' },
    { key: '关于我们', icon: 'info' }
  ]

  return (
    <View className='page-mine'>
      {/* 资料头：单态 —— 头像/昵称就地编辑、自动保存 */}
      <View className='profile-header'>

        {loggedIn ? (
          <>
            {/* 头像：整块可点——
                MP-WEAPP 走 Button openType=chooseAvatar 直接弹微信原生面板
                （微信头像 / 相册 / 拍照），无需自定义 UI；
                抖音 + H5 端无该面板，改为 onClick 调 Taro.chooseImage。
                注意：必须彻底清掉 Taro Button 默认白底 / padding / min-height，
                否则头像外会出现一块明显白色方框。 */}
            {isWeapp ? (
              <Button
                className='profile-avatar-block'
                openType='chooseAvatar'
                onChooseAvatar={onChooseAvatar}
                disabled={avatarSaving}
              >
                <View className='profile-avatar'>
                  {finalAvatarUrl ? (
                    <Image className='profile-avatar__img' src={finalAvatarUrl} mode='aspectFill' />
                  ) : (
                    <Icon name='user' size={96} color='#FFFFFF' />
                  )}
                </View>
              </Button>
            ) : (
              <View className='profile-avatar-block' onClick={handlePickAvatarNonWeapp}>
                <View className='profile-avatar'>
                  {finalAvatarUrl ? (
                    <Image className='profile-avatar__img' src={finalAvatarUrl} mode='aspectFill' />
                  ) : (
                    <Icon name='user' size={96} color='#FFFFFF' />
                  )}
                </View>
              </View>
            )}

            {/* 昵称 + 性别徽章：wrap 整体居中（wrap 宽度 = 昵称文字宽），性别徽章
                绝对定位在昵称右上角一点点。常驻 Input，type='nickname' 在 MP-WEIXIN
                点输入框自动弹微信昵称选择面板。
                性别徽章：未设置 → 浅白半透"+ 性别"文字药丸（明确入口，一眼就懂）；
                已设置 → ♂ 蓝底 / ♀ 粉底 白字单字圆形，再点可切换。 */}
            <View className='profile-name-row'>
              <View className='profile-name-wrap'>
                <Input
                  className='profile-name profile-name--input'
                  /* 宽度贴合文字（+8px 余量防截断），容器右沿==文字右沿，
                     徽章才能紧贴昵称；pxTransform 保证跨端单位与 scss 一致 */
                  style={{ width: Taro.pxTransform(nickInputWidth) }}
                  type='nickname'
                  value={profile?.nickname || ''}
                  placeholder='点击设置昵称'
                  placeholderClass='profile-name-ph'
                  onBlur={(e) => saveNick(e.detail.value)}
                  onConfirm={(e) => saveNick(e.detail.value)}
                />
                <View
                  className={`profile-gender${
                    profile?.gender === 1
                      ? ' profile-gender--male'
                      : profile?.gender === 2
                        ? ' profile-gender--female'
                        : ' profile-gender--unset'
                  }`}
                  onClick={openGenderPicker}
                >
                  <Text>{profile?.gender === 1 ? '♂' : profile?.gender === 2 ? '♀' : '+ 性别'}</Text>
                </View>
              </View>
            </View>
            {/* 副标语：头像或昵称只要有一个没改就提示对应那一条；两者都改完就完全隐藏 */}
            {tapTipText ? (
              <Text className='profile-tap-tip'>{tapTipText}</Text>
            ) : null}

            {/* 抖音专属：一键使用抖音头像昵称
                微信端无此入口（微信用户点头像/昵称原生面板更顺滑）
                注意：tt.getUserProfile 必须由 tap 手势触发（否则报 111601），
                且需在抖音后台配置隐私协议 scope（否则报 111679/111680）。*/}
            {isDouyin && (isAvatarCustomized === false || isNickCustomized === false) && (
              <View className='profile-use-douyin-btn' onClick={handleUseDouyinProfile}>
                <Text>一键使用抖音头像昵称</Text>
              </View>
            )}

            {/* chips 行：等级（数据驱动，点击看等级说明） + 年龄段（用户自设）；性别已并入昵称右上角 */}
            <View className='profile-chips'>
              <View className='profile-chip profile-chip--brand' onClick={() => setLevelInfoOpen(true)}>
                <Icon name='award' size={28} color='#FF5C38' />
                <Text>{profile?.runner_level || '跑者'}</Text>
              </View>
              <View
                className={`profile-chip profile-chip--age${
                  profile?.age_group ? ' profile-chip--age-set' : ''
                }`}
                onClick={openAgePicker}
              >
                <Icon
                  name={profile?.age_group ? 'check' : 'plus'}
                  size={28}
                  color={profile?.age_group ? '#FFFFFF' : 'rgba(255,255,255,0.85)'}
                />
                <Text>{profile?.age_group ? AGE_LABEL[profile.age_group] : '添加年龄段'}</Text>
              </View>
            </View>

            {/* 数据条：报名中 / 完赛 / 里程 */}
            <View className='profile-data-strip'>
              <View className='profile-data-item'>
                <Text className='profile-data-item__num'>
                  {profile?.registered_count ?? 0}
                  <Text className='profile-data-item__unit'>场</Text>
                </Text>
                <Text className='profile-data-item__label'>报名中</Text>
              </View>
              <View className='profile-data-strip__divider' />
              <View className='profile-data-item'>
                <Text className='profile-data-item__num'>
                  {profile?.finished_count ?? 0}
                  <Text className='profile-data-item__unit'>场</Text>
                </Text>
                <Text className='profile-data-item__label'>完赛</Text>
              </View>
              <View className='profile-data-strip__divider' />
              <View className='profile-data-item'>
                <Text className='profile-data-item__num'>
                  {profile?.total_distance ?? 0}
                  <Text className='profile-data-item__unit'>km</Text>
                </Text>
                <Text className='profile-data-item__label'>跑步里程</Text>
              </View>
            </View>
          </>
        ) : (
          <>
            <View className='profile-avatar-block' onClick={handleLogin}>
              <View className='profile-avatar profile-avatar--login'>
                <Icon name='user' size={96} color='#FFFFFF' />
              </View>
            </View>
            <Text className='profile-name' onClick={handleLogin}>点击登录</Text>
            <Text className='profile-tap-tip'>登录后开启马拉松追踪之旅</Text>
          </>
        )}
      </View>

      {/* === 下一场比赛（有则展示，作为最重要的激励信息） === */}
      {loggedIn && profile?.next_race && (() => {
        const nr = profile.next_race
        const isSoon = nr.days_away >= 0 && nr.days_away <= 30
        const isOngoing = nr.days_away < 0 && nr.days_away >= -14
        const statusText = isOngoing
          ? '进行中'
          : nr.days_away === 0
            ? '就在今天'
            : `${nr.days_away} 天后开赛`
        return (
          <View className='race-card' onClick={() => {
            if (nr.event_id) Taro.navigateTo({ url: `/pages/race-detail/index?id=${nr.event_id}` })
            else Taro.showToast({ title: '自定义赛事暂无详情', icon: 'none' })
          }}>
            <View className='race-card__label'>
              <Icon name='calendar-days' size={28} color='#FF5C38' />
              <Text>下一场比赛</Text>
            </View>
            <View className='race-card__main'>
              <View className='race-card__name-row'>
                <Text className='race-card__name ellipsis'>{nr.event_name}</Text>
                <Text className={`race-card__tag ${nr.event_type === 1 ? 'race-card__tag--full' : ''}`}>
                  {nr.event_type_label}
                </Text>
              </View>
              <View className='race-card__sub'>
                <Text className='race-card__date'>{nr.start_date}</Text>
                <Text className={`race-card__days ${isSoon ? 'race-card__days--soon' : ''}`}>
                  {statusText}
                </Text>
              </View>
            </View>
          </View>
        )
      })()}

      {/* === PB 展示卡（有一场完赛就有价值） === */}
      {loggedIn && (profile?.finished_count ?? 0) > 0 && (profile?.half_pb || profile?.full_pb) && (
        <View className='pb-card'>
          <Text className='pb-card__title'>个人最好成绩</Text>
          <View className='pb-card__row'>
            <View className='pb-card__item'>
              <Text className='pb-card__item__label'>半马 PB</Text>
              <Text className='pb-card__item__value'>{profile?.half_pb || '—'}</Text>
            </View>
            <View className='pb-card__divider' />
            <View className='pb-card__item'>
              <Text className='pb-card__item__label'>全马 PB</Text>
              <Text className='pb-card__item__value'>{profile?.full_pb || '—'}</Text>
            </View>
          </View>
        </View>
      )}

      {/* === 我的排名（激励模块，仅当有完赛/花费且有排名） === */}
      {loggedIn && profile?.my_rank && (
        <View className='rank-card'>
          <View className='rank-card__left'>
            <Text className='rank-card__rank'>
              第<Text className='rank-card__rank-num'>{profile.my_rank.rank}</Text>名
            </Text>
            <Text className='rank-card__metric'>
              {profile.my_rank.metric === 'distance' ? '总跑量' :
               profile.my_rank.metric === 'full_marathon_pb' ? '全马 PB' :
               profile.my_rank.metric === 'half_marathon_pb' ? '半马 PB' : '总花费'}
            </Text>
          </View>
          <View className='rank-card__right'>
            <Text className='rank-card__value'>{profile.my_rank.value_label}</Text>
            {profile.my_rank.insight && (
              <Text className='rank-card__insight'>{profile.my_rank.insight}</Text>
            )}
          </View>
        </View>
      )}

      {/* === 最近完赛 === */}
      {loggedIn && profile?.recent_finished && profile.recent_finished.length > 0 && (
        <View className='section'>
          <Text className='section-title'>最近完赛</Text>
          <View className='finished-list'>
            {profile.recent_finished.map((item) => (
              <View key={item.event_id} className='finished-item'>
                <View className='finished-item__left'>
                  <Text className='finished-item__name ellipsis'>{item.event_name}</Text>
                  {item.start_time && (
                    <Text className='finished-item__date'>{item.start_time}</Text>
                  )}
                </View>
                <View className='finished-item__right'>
                  {item.finish_time ? (
                    <Text className='finished-item__time'>{item.finish_time}</Text>
                  ) : (
                    <Text className='finished-item__time finished-item__time--pb'>
                      {item.is_pb ? 'PB!' : '已完赛'}
                    </Text>
                  )}
                </View>
              </View>
            ))}
          </View>
        </View>
      )}

      {/* 菜单列表 */}
      <View className='section'>
        <Text className='section-title'>更多</Text>
        <View className='menu-list'>
          {menus.map((menu, idx) => (
            <View
              key={menu.key}
              className={`menu-item ${idx === menus.length - 1 ? 'menu-item--last' : ''}`}
              onClick={() => handleMenuClick(menu.key)}
            >
              <Icon name={menu.icon} size={32} color='#A3968D' />
              <Text className='menu-item__text'>{menu.key}</Text>
              {menu.badge ? (
                <Text className='menu-item__badge'>{menu.badge}</Text>
              ) : null}
              <Icon name='chevron-right' size={28} color='#B9AAA0' />
            </View>
          ))}
        </View>
      </View>

      <TabBar current='mine' />

      {/* === 底部 picker：性别 + 年龄段共用同一组件 ===
          - 半透黑 + 底部圆角白卡，比 ActionSheet 更整齐
          - 选中项绿色高亮
          - 点选项即存即关（无确认按钮，延续单态即时保存） */}
      {pickerType ? (
        <View className='picker-overlay' onClick={closePicker}>
          <View
            className='picker-sheet'
            onClick={(e) => {
              // 阻止冒泡避免点选时穿透关闭
              e?.stopPropagation?.()
            }}
          >
            <View className='picker-sheet__title'>
              {pickerType === 'gender' ? '选择性别' : '选择年龄段'}
            </View>
            <View className='picker-sheet__list'>
              {pickerType === 'gender'
                ? [
                    { v: 1, label: '♂  男性' },
                    { v: 2, label: '♀  女性' }
                  ].map((opt) => {
                    const active = profile?.gender === opt.v
                    return (
                      <View
                        key={opt.v}
                        className={`picker-sheet__item${active ? ' picker-sheet__item--active' : ''}`}
                        onClick={() => {
                          saveGender(opt.v)
                          closePicker()
                        }}
                      >
                        <Text>{opt.label}</Text>
                        {active ? <Text className='picker-sheet__check'>✓</Text> : null}
                      </View>
                    )
                  })
                : AGE_GROUPS.map((opt) => {
                    const active = profile?.age_group === opt.value
                    return (
                      <View
                        key={opt.value}
                        className={`picker-sheet__item${active ? ' picker-sheet__item--active' : ''}`}
                        onClick={() => {
                          saveAgeGroup(opt.value)
                          closePicker()
                        }}
                      >
                        <Text>{opt.label}</Text>
                        {active ? <Text className='picker-sheet__check'>✓</Text> : null}
                      </View>
                    )
                  })}
            </View>
            <View className='picker-sheet__cancel' onClick={closePicker}>
              <Text>取消</Text>
            </View>
          </View>
        </View>
      ) : null}

      {/* === 跑者等级说明弹层：点等级 chip 打开，纯展示（复用 picker 弹层骨架） === */}
      {levelInfoOpen ? (
        <View className='picker-overlay' onClick={() => setLevelInfoOpen(false)}>
          <View
            className='picker-sheet'
            onClick={(e) => {
              e?.stopPropagation?.()
            }}
          >
            <View className='picker-sheet__title'>跑者等级说明</View>
            <View className='level-sheet__list'>
              {RUNNER_LEVELS.map((lv) => {
                const current = (profile?.runner_level || '跑者') === lv.name
                return (
                  <View
                    key={lv.name}
                    className={`level-sheet__row${current ? ' level-sheet__row--current' : ''}`}
                  >
                    <View className='level-sheet__head'>
                      <Text className='level-sheet__name'>{lv.name}</Text>
                      {current ? <Text className='level-sheet__badge'>当前等级</Text> : null}
                    </View>
                    <Text className='level-sheet__need'>{lv.need}</Text>
                    <Text className='level-sheet__desc'>{lv.desc}</Text>
                  </View>
                )
              })}
            </View>
            <View className='level-sheet__note'>
              <Text>等级按累计完赛场次自动计算，无需手动申报</Text>
            </View>
            <View className='picker-sheet__cancel' onClick={() => setLevelInfoOpen(false)}>
              <Text>我知道了</Text>
            </View>
          </View>
        </View>
      ) : null}
    </View>
  )
}
