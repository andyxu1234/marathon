import { View, Text, Input, ScrollView } from '@tarojs/components'
import { useState, useMemo } from 'react'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import Icon from '@/components/Icon'
import Empty from '@/components/Empty'
import TabBar from '@/components/TabBar'
import api, { Page } from '@/services/api'
import './index.scss'

// 关注项 = 后端 FavoriteItem
interface RegistrationBrief {
  registration_status: number   // 0未报名 1已报名
  payment_status: number        // 0未缴费 1已缴费
  lottery_status: number        // 0未中签 1已中签 2抽签中
  race_type: number             // 0未设置 1全马 2半马 3健康跑
  fee: number | null
  bib_number: string | null
  finish_time: string | null
  result_status: number
}
interface FavoriteItem {
  event_id: number | null
  custom_event_id: number | null
  is_custom: boolean
  event_name: string
  event_type: number
  event_type_label: string
  event_level: number
  event_level_label: string
  event_status: number
  event_status_label: string
  start_time: string | null
  start_date_label: string | null
  location: string | null
  cover_image: string | null
  registration_fee: number | null
  registration: RegistrationBrief
  days_to_race: number | null
  create_time?: string | null
}

// 状态 chip 元信息
interface ChipMeta {
  label: string
  cls: string       // success | warning | info | muted
  icon: string
}
function regMeta(s: number): ChipMeta {
  return s === 1
    ? { label: '已报名', cls: 'success', icon: 'check-circle' }
    : { label: '未报名', cls: 'info', icon: 'circle' }
}
function payMeta(s: number): ChipMeta {
  return s === 1
    ? { label: '已缴费', cls: 'success', icon: 'check-circle' }
    : { label: '未缴费', cls: 'muted', icon: 'minus' }
}
function lotteryMeta(s: number): ChipMeta {
  if (s === 1) return { label: '已中签', cls: 'success', icon: 'check-circle' }
  if (s === 2) return { label: '抽签中', cls: 'warning', icon: 'clock' }
  return { label: '未中签', cls: 'muted', icon: 'minus' }
}

// 赛事类型简称
function typeShort(t: number): string {
  const map: Record<number, string> = { 1: '全马', 2: '半马', 3: '健康跑', 4: '越野', 5: '其他' }
  return map[t] || '其他'
}

// 报名项目选项（记事本：用户报的项目，1全马 2半马 3健康跑）
const RACE_TYPE_OPTIONS = [
  { v: 1, label: '全马' },
  { v: 2, label: '半马' },
  { v: 3, label: '健康跑' },
] as const

/** 4 类过滤维度 —— chip 选项与 server mi_config seed 文案逐字对齐 */
const FILTER_OPTIONS = {
  reg: [
    { v: null, label: '全部' },
    { v: 1, label: '已报名' },
    { v: 0, label: '未报名' }
  ],
  pay: [
    { v: null, label: '全部' },
    { v: 1, label: '已缴费' },
    { v: 0, label: '未缴费' }
  ],
  lottery: [
    { v: null, label: '全部' },
    { v: 1, label: '已中签' },
    { v: 2, label: '抽签中' },
    { v: 0, label: '未中签' }
  ],
  event: [
    { v: null, label: '全部' },
    { v: 1, label: '未开始' },
    { v: 2, label: '报名中' },
    { v: 3, label: '报名结束' },
    { v: 4, label: '比赛中' },
    { v: 5, label: '已结束' }
  ]
} as const

type StatusKey = keyof typeof FILTER_OPTIONS
type FilterKey = StatusKey

interface FilterState {
  reg: number | null
  pay: number | null
  lottery: number | null
  event: number | null
}
const EMPTY_FILTER: FilterState = {
  reg: null, pay: null, lottery: null, event: null
}

const STATUS_LABELS: Record<StatusKey, string> = {
  reg: '报名状态',
  pay: '缴费状态',
  lottery: '中签状态',
  event: '比赛状态'
}

// Dropdown 浮层面板定位
interface DropdownState {
  key: FilterKey
  top: number
  left: number
  width: number
}

/** 取卡片唯一键 */
function itemKey(item: FavoriteItem): number {
  return item.is_custom && item.custom_event_id
    ? item.custom_event_id
    : item.event_id || 0
}

export default function Follow() {
  const [items, setItems] = useState<FavoriteItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<FilterState>(EMPTY_FILTER)
  const [dropdown, setDropdown] = useState<DropdownState | null>(null)
  // 卡片折叠：Record<key, boolean>
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({})

  const fetchAll = async () => {
    setLoading(true)
    try {
      const listRes = await api.getFavorites({ page: 1, page_size: 50 })
      setItems((listRes as Page<FavoriteItem>).items)
    } catch (e) {
      console.warn('[Follow] fetch failed', e)
      if ((e as any)?.statusCode === 401) {
        Taro.showToast({ title: '请先登录', icon: 'none' })
      }
    } finally {
      setLoading(false)
    }
  }

  useDidShow(() => {
    try { Taro.hideTabBar({ animation: false }) } catch (_) {}
    if (!Taro.getStorageSync('token')) {
      // 未登录展示空态
      return
    }
    fetchAll()
  })

  usePullDownRefresh(async () => {
    await fetchAll()
    Taro.stopPullDownRefresh()
  })

  const handleAddRace = () => {
    if (!Taro.getStorageSync('token')) {
      Taro.showToast({ title: '请先登录', icon: 'none' })
      return
    }
    Taro.navigateTo({ url: '/pages/add-race/index' })
  }

  const handleCardClick = (item: FavoriteItem) => {
    if (item.is_custom) {
      Taro.showToast({ title: '自定义赛事暂无详情页', icon: 'none' })
      return
    }
    if (!item.event_id) return
    Taro.navigateTo({ url: `/pages/race-detail/index?id=${item.event_id}` })
  }

  // 切换卡片折叠：默认折叠，点卡片展开/收起
  const toggleExpand = (key: number) => {
    setExpandedIds((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const isExpanded = (key: number) => !!expandedIds[key]

  // 切换状态 chip（含报名项目 race_type、完赛状态 result_status）
  const handleStatusChange = async (
    item: FavoriteItem,
    field: 'registration_status' | 'payment_status' | 'lottery_status' | 'race_type' | 'result_status',
    value: number
  ) => {
    const key = itemKey(item)
    // 本地乐观更新
    const updated = items.map((it) => {
      if (itemKey(it) === key) {
        return { ...it, registration: { ...it.registration, [field]: value } }
      }
      return it
    })
    setItems(updated)
    try {
      if (item.is_custom && item.custom_event_id) {
        await api.updateCustomRegistration(item.custom_event_id, { [field]: value })
      } else if (item.event_id) {
        await api.updateRegistration(item.event_id, { [field]: value })
      }
    } catch (e) {
      console.warn('[Follow] update status failed', e)
      Taro.showToast({ title: '更新失败', icon: 'none' })
      fetchAll() // 回滚
    }
  }

  // 费用输入
  const handleFeeChange = async (item: FavoriteItem, feeStr: string) => {
    const key = itemKey(item)
    const fee = parseFloat(feeStr) || 0
    const updated = items.map((it) => {
      if (itemKey(it) === key) {
        return { ...it, registration: { ...it.registration, fee } }
      }
      return it
    })
    setItems(updated)
  }

  const handleFeeBlur = async (item: FavoriteItem) => {
    try {
      const payload = { fee: item.registration.fee }
      if (item.is_custom && item.custom_event_id) {
        await api.updateCustomRegistration(item.custom_event_id, payload)
      } else if (item.event_id) {
        await api.updateRegistration(item.event_id, payload)
      }
    } catch (e) {
      console.warn('[Follow] update fee failed', e)
    }
  }

  // 通用文本字段 blur 保存（完赛成绩 / 参赛号码）
  const handleTextFieldBlur = async (
    item: FavoriteItem,
    field: 'finish_time' | 'bib_number',
    value: string
  ) => {
    try {
      const payload = { [field]: value.trim() || null }
      if (item.is_custom && item.custom_event_id) {
        await api.updateCustomRegistration(item.custom_event_id, payload)
      } else if (item.event_id) {
        await api.updateRegistration(item.event_id, payload)
      }
    } catch (e) {
      console.warn(`[Follow] update ${field} failed`, e)
    }
  }

  // 验证完赛成绩格式 h:mm:ss，无效时提示
  const handleFinishTimeBlur = async (item: FavoriteItem) => {
    const v = (item.registration.finish_time || '').trim()
    if (!v) {
      await handleTextFieldBlur(item, 'finish_time', '')
      return
    }
    const ok = /^(\d{1,2}):(\d{2}):(\d{2})$/.test(v)
    if (!ok) {
      Taro.showToast({ title: '请输入 h:mm:ss 格式', icon: 'none' })
      // 回滚本地状态
      fetchAll()
      return
    }
    await handleTextFieldBlur(item, 'finish_time', v)
  }

  // 取消关注 / 删除自定义赛事
  const handleUnfavorite = (item: FavoriteItem) => {
    const label = item.is_custom ? '删除自定义赛事' : '取消关注'
    Taro.showModal({
      title: '确认操作',
      content: `确定要${label}「${item.event_name}」吗？`,
      confirmText: item.is_custom ? '删除' : '取消关注',
      confirmColor: '#E23A2E',
      success: async (res) => {
        if (!res.confirm) return
        const key = itemKey(item)
        // 乐观更新：立即从列表移除
        setItems((prev) => prev.filter((it) => itemKey(it) !== key))
        try {
          if (item.is_custom && item.custom_event_id) {
            await api.deleteCustomRace(item.custom_event_id)
          } else if (item.event_id) {
            await api.unfavoriteEvent(item.event_id)
          }
          Taro.showToast({ title: '操作成功', icon: 'success' })
        } catch (e) {
          console.warn('[Follow] unfavorite failed', e)
          Taro.showToast({ title: '操作失败', icon: 'none' })
          fetchAll() // 回滚
        }
      },
    })
  }

  // 打开 dropdown（点同一维度切换关闭）
  const openDropdown = (key: FilterKey) => {
    if (dropdown?.key === key) {
      setDropdown(null)
      return
    }
    const query = Taro.createSelectorQuery()
    query.select(`.filter-chip-${key}`).boundingClientRect()
    query.exec((res) => {
      const rect = res[0]
      if (rect) {
        setDropdown({ key, top: rect.top + rect.height + 8, left: rect.left, width: rect.width })
      }
    })
  }

  // 根据 dropdown.key 取该 key 对应的可选项
  const optionsForDropdown = (key: FilterKey) => {
    return FILTER_OPTIONS[key] as any
  }

  // chip 默认 label
  const chipLabel = (key: FilterKey): string => {
    return STATUS_LABELS[key]
  }

  const currentChipValueLabel = (key: FilterKey): string | null => {
    const v = (filter as any)[key]
    if (v === null || v === undefined || v === '') return null
    const opt = optionsForDropdown(key).find((o: any) => o.v === v)
    return opt?.label ?? String(v)
  }

  // dropdown 选项点击
  const onFilterSelect = (key: FilterKey, value: any) => {
    setFilter((prev) => ({
      ...prev,
      [key]: (prev as any)[key] === value ? null : value,
    }))
    setDropdown(null)
  }

  // 清除全部过滤
  const clearAllFilter = () => {
    setFilter(EMPTY_FILTER)
    setDropdown(null)
  }

  // 过滤后的列表（任何非 null 都必须命中）+ 按比赛时间升序
  // 排序规则：未来赛事离比赛越近越靠上（days_to_race 升序），
  //         过去赛事按 |天数| 升序（最近结束的靠上），未知日期沉底
  const filteredItems = useMemo(() => {
    const filtered = items.filter((it) => {
      if (filter.reg !== null && it.registration.registration_status !== filter.reg) return false
      if (filter.pay !== null && it.registration.payment_status !== filter.pay) return false
      if (filter.lottery !== null && it.registration.lottery_status !== filter.lottery) return false
      if (filter.event !== null && it.event_status !== filter.event) return false
      return true
    })
    // 返回 [section, days]：section 0=未来, 1=过去, 2=未知；days 越低越靠前
    const sortKey = (d: number | null): [number, number] => {
      if (d == null) return [2, 0]
      if (d < 0) return [1, Math.abs(d)]
      return [0, d]
    }
    return [...filtered].sort((a, b) => {
      const ka = sortKey(a.days_to_race)
      const kb = sortKey(b.days_to_race)
      return ka[0] !== kb[0] ? ka[0] - kb[0] : ka[1] - kb[1]
    })
  }, [items, filter])

  // 是否存在任何过滤（用于顶部"清除"按钮）
  const hasActiveFilter = Object.values(filter).some((v) => v !== null)

  const loggedIn = !!Taro.getStorageSync('token')

  return (
    <View className='page-follow'>
      {/* Header —— 薄荷绿渐变 Hero（参考首页 .hero） */}
      <View className='follow-header'>
        <View className='follow-header__left'>
          <Text className='follow-header__title'>我的赛事</Text>
          <Text className='follow-header__sub'>追踪你的每场比赛</Text>
        </View>
        <View className='follow-header__add' onClick={handleAddRace}>
          <Icon name='plus' size={28} color='#FFFFFF' />
          <Text>添加赛事</Text>
        </View>
      </View>

      {/* 多维过滤：dropdown chip 风格（参考首页） */}
      <View className='filter-bar'>
        <ScrollView scrollX className='filter-scroll no-scrollbar'>
          <View className='filter-chips'>
            {(['reg', 'pay', 'lottery', 'event'] as FilterKey[]).map((key) => {
              const active = (filter as any)[key] !== null
              const valueLabel = currentChipValueLabel(key)
              const label = valueLabel ?? chipLabel(key)
              return (
                <View
                  key={key}
                  className={[
                    'filter-chip',
                    `filter-chip-${key}`,
                    active ? 'active' : '',
                    dropdown?.key === key ? 'open' : '',
                  ].join(' ')}
                  onClick={() => openDropdown(key)}
                >
                  <Text className='filter-chip-label'>{label}</Text>
                  <Icon
                    name='chevron-down'
                    size={20}
                    color={active ? '#FF5C38' : '#B9AAA0'}
                  />
                </View>
              )
            })}
            {hasActiveFilter && (
              <View className='filter-chip filter-chip-clear' onClick={clearAllFilter}>
                <Icon name='x' size={20} color='#B9AAA0' />
                <Text className='filter-chip-label'>清除全部</Text>
              </View>
            )}
          </View>
        </ScrollView>
      </View>

      {/* dropdown 浮层面板 */}
      {dropdown ? (
        <View className='dropdown-mask' onClick={() => setDropdown(null)}>
          <View
            className='dropdown-panel'
            style={{ top: `${dropdown.top}px`, left: `${dropdown.left}px` }}
            onClick={(e) => e.stopPropagation()}
          >
            <ScrollView scrollY className='dropdown-list'>
              {optionsForDropdown(dropdown.key).map((opt: any) => {
                const selected = (filter as any)[dropdown.key] === opt.v
                return (
                  <View
                    key={`${dropdown.key}-${opt.v ?? 'null'}`}
                    className={`dropdown-item ${selected ? 'selected' : ''}`}
                    onClick={() => onFilterSelect(dropdown.key, opt.v)}
                  >
                    <Text className='dropdown-item-label'>{opt.label}</Text>
                    {selected ? <Icon name='check' size={28} color='#FF5C38' /> : null}
                  </View>
                )
              })}
              {optionsForDropdown(dropdown.key).length === 0 && (
                <View className='dropdown-item disabled-row'>
                  <Text className='dropdown-item-label'>请先选择省份</Text>
                </View>
              )}
            </ScrollView>
          </View>
        </View>
      ) : null}

      {/* 关注列表 */}
      <View className='follow-list-wrap'>
        <View className='follow-list-head'>
          <Text className='follow-list-title'>赛事追踪</Text>
          <Text className='follow-list-count'>
            共 {filteredItems.length} / {items.length} 场
          </Text>
        </View>

        {!loggedIn ? (
          <Empty text='登录后查看你的赛事' icon='heart' hint='登录后即可追踪报名、中签与完赛' />
        ) : items.length === 0 && !loading ? (
          <Empty text='还没有关注的赛事' icon='heart' hint='在首页点进任意赛事收藏，或手动添加一场' />
        ) : filteredItems.length === 0 ? (
          <Empty text='没有匹配的赛事' icon='filter' hint='调整上面的筛选条件试试' />
        ) : (
          <View className='follow-card-list'>
            {filteredItems.map((item, idx) => {
              const reg = regMeta(item.registration.registration_status)
              const pay = payMeta(item.registration.payment_status)
              const lot = lotteryMeta(item.registration.lottery_status)
              // 入场 stagger 延迟（上限 10 条，避免长列表越滚越慢）
              const enterDelay = Math.min(idx, 10) * 55
              // 报名项目：用户选择的 race_type 优先，未设置则继承赛事类型
              const raceLabel = typeShort(item.registration.race_type || item.event_type)
              const countdownText =
                item.days_to_race != null && item.days_to_race >= 0
                  ? `倒计时${item.days_to_race}天`
                  : '比赛已结束'
              // 费用自动带出：用户填过(非0) > 赛事报名费 > 0
              const fee = item.registration.fee || item.registration_fee || 0
              const key = itemKey(item)
              const expanded = isExpanded(key)
              return (
                <View
                  key={key}
                  className={`follow-card ${expanded ? 'is-expanded' : ''}`}
                  style={{ animationDelay: `${enterDelay}ms` }}
                  onClick={() => toggleExpand(key)}
                >
                  {/* 折叠态可见：head 一行 —— 左名称+类型，右两行摘要+箭头 */}
                  <View className='follow-card__head'>
                    <View className='follow-card__head-left'>
                      <Text
                        className='follow-card__name ellipsis'
                        onClick={(e) => { e.stopPropagation(); handleCardClick(item) }}
                      >
                        {item.event_name}
                      </Text>
                      <View className='follow-card__tags'>
                        <Text className={`race-type-tag ${item.event_type === 1 ? 'race-type-tag--full' : ''}`}>{raceLabel}</Text>
                        {item.is_custom && (
                          <Text className='custom-tag'>自定义</Text>
                        )}
                      </View>
                    </View>
                    <View className='follow-card__head-right'>
                      <View className='follow-card__summary'>
                        {item.registration.registration_status === 1 ? (
                          <>
                            <Text className='follow-card__summary-line'>
                              <Text className={`follow-card__summary-em follow-card__summary-em--${lot.cls}`}>{lot.label}</Text>
                              ，<Text className={`follow-card__summary-em follow-card__summary-em--${pay.cls}`}>{pay.label}</Text>
                            </Text>
                            <Text className='follow-card__summary-line'>{countdownText}</Text>
                          </>
                        ) : (
                          <>
                            <Text className='follow-card__summary-line follow-card__summary-line--muted'>未报名</Text>
                            <Text className='follow-card__summary-line'>{countdownText}</Text>
                          </>
                        )}
                      </View>
                      <Icon
                        name={expanded ? 'chevron-up' : 'chevron-down'}
                        size={26}
                        color={expanded ? '#FF5C38' : '#B9AAA0'}
                      />
                    </View>
                  </View>

                  {/* 展开后才显示：详情区，点击需 stopPropagation 防止冒泡触发折叠 */}
                  {expanded && (
                    <View className='follow-card__detail' onClick={(e) => e.stopPropagation()}>
                      <View className='follow-card__status'>
                        {/* 报名项目（记事本核心：全马/半马/健康跑） */}
                        <View className='status-row'>
                          <Text className='status-label'>项目</Text>
                          <View className='status-options'>
                            {RACE_TYPE_OPTIONS.map((opt) => (
                              <View
                                key={opt.v}
                                className={`status-opt ${item.registration.race_type === opt.v ? 'active success' : ''}`}
                                onClick={() => handleStatusChange(item, 'race_type', opt.v)}
                              >
                                {item.registration.race_type === opt.v && <Icon name='check-circle' size={24} color='#FF5C38' />}
                                <Text>{opt.label}</Text>
                              </View>
                            ))}
                          </View>
                        </View>

                        {/* 报名 */}
                        <View className='status-row'>
                          <Text className='status-label'>报名</Text>
                          <View className='status-options'>
                            <View
                              className={`status-opt ${item.registration.registration_status === 1 ? `active ${reg.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'registration_status', 1)}
                            >
                              {item.registration.registration_status === 1 && <Icon name={reg.icon} size={24} color='#FF5C38' />}
                              <Text>已报名</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.registration_status === 0 ? `active ${reg.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'registration_status', 0)}
                            >
                              {item.registration.registration_status === 0 && <Icon name={reg.icon} size={24} color='#2E9BD6' />}
                              <Text>未报名</Text>
                            </View>
                          </View>
                        </View>

                        {/* 缴费 */}
                        <View className='status-row'>
                          <Text className='status-label'>缴费</Text>
                          <View className='status-options'>
                            <View
                              className={`status-opt ${item.registration.payment_status === 1 ? `active ${pay.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'payment_status', 1)}
                            >
                              {item.registration.payment_status === 1 && <Icon name='check-circle' size={24} color='#FF5C38' />}
                              <Text>已缴费</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.payment_status === 0 ? `active ${pay.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'payment_status', 0)}
                            >
                              {item.registration.payment_status === 0 && <Icon name='minus' size={24} color='#B9AAA0' />}
                              <Text>未缴费</Text>
                            </View>
                          </View>
                        </View>

                        {/* 中签 */}
                        <View className='status-row'>
                          <Text className='status-label'>中签</Text>
                          <View className='status-options'>
                            <View
                              className={`status-opt ${item.registration.lottery_status === 1 ? `active ${lot.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'lottery_status', 1)}
                            >
                              {item.registration.lottery_status === 1 && <Icon name='check-circle' size={24} color='#FF5C38' />}
                              <Text>已中签</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.lottery_status === 2 ? `active ${lot.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'lottery_status', 2)}
                            >
                              {item.registration.lottery_status === 2 && <Icon name='clock' size={24} color='#E8940C' />}
                              <Text>抽签中</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.lottery_status === 0 ? `active ${lot.cls}` : ''}`}
                              onClick={() => handleStatusChange(item, 'lottery_status', 0)}
                            >
                              {item.registration.lottery_status === 0 && <Icon name='minus' size={24} color='#B9AAA0' />}
                              <Text>未中签</Text>
                            </View>
                          </View>
                        </View>

                        {/* 完赛状态 */}
                        <View className='status-row'>
                          <Text className='status-label'>完赛</Text>
                          <View className='status-options'>
                            <View
                              className={`status-opt ${item.registration.result_status === 2 ? 'active success' : ''}`}
                              onClick={() => handleStatusChange(item, 'result_status', 2)}
                            >
                              {item.registration.result_status === 2 && <Icon name='trophy' size={24} color='#FF5C38' />}
                              <Text>PB</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.result_status === 1 ? 'active success' : ''}`}
                              onClick={() => handleStatusChange(item, 'result_status', 1)}
                            >
                              {item.registration.result_status === 1 && <Icon name='check-circle' size={24} color='#FF5C38' />}
                              <Text>已完赛</Text>
                            </View>
                            <View
                              className={`status-opt ${item.registration.result_status === 0 ? 'active muted' : ''}`}
                              onClick={() => handleStatusChange(item, 'result_status', 0)}
                            >
                              {item.registration.result_status === 0 && <Icon name='minus' size={24} color='#B9AAA0' />}
                              <Text>未完赛</Text>
                            </View>
                          </View>
                        </View>

                        {/* 完赛成绩 */}
                        <View className='status-row'>
                          <Text className='status-label'>成绩</Text>
                          <View className='time-input-wrap'>
                            <Input
                              className='time-input'
                              value={item.registration.finish_time || ''}
                              placeholder='如 3:25:18'
                              onInput={(e) => {
                                const key = itemKey(item)
                                setItems((prev) =>
                                  prev.map((it) =>
                                    itemKey(it) === key
                                      ? { ...it, registration: { ...it.registration, finish_time: e.detail.value } }
                                      : it
                                  )
                                )
                              }}
                              onBlur={() => handleFinishTimeBlur(item)}
                            />
                          </View>
                        </View>

                        {/* 参赛号码 */}
                        <View className='status-row'>
                          <Text className='status-label'>号码</Text>
                          <View className='bib-input-wrap'>
                            <Input
                              className='bib-input'
                              value={item.registration.bib_number || ''}
                              placeholder='可选'
                              onInput={(e) => {
                                const key = itemKey(item)
                                setItems((prev) =>
                                  prev.map((it) =>
                                    itemKey(it) === key
                                      ? { ...it, registration: { ...it.registration, bib_number: e.detail.value } }
                                      : it
                                  )
                                )
                              }}
                              onBlur={() => handleTextFieldBlur(item, 'bib_number', item.registration.bib_number || '')}
                            />
                          </View>
                        </View>

                        {/* 费用 */}
                        <View className='status-row'>
                          <Text className='status-label'>费用</Text>
                          <View className='fee-wrap'>
                            <Text className='fee-unit'>¥</Text>
                            <Input
                              className='fee-input'
                              type='digit'
                              value={String(fee ?? '')}
                              placeholder='0'
                              onInput={(e) => handleFeeChange(item, e.detail.value)}
                              onBlur={() => handleFeeBlur(item)}
                            />
                          </View>
                        </View>
                      </View>

                      {/* 倒计时 */}
                      <View className='follow-card__footer'>
                        <View className='follow-card__countdown'>
                          <Icon name='calendar-days' size={26} color='#A3968D' />
                          <Text>
                            {item.days_to_race != null && item.days_to_race >= 0
                              ? `距比赛还有 ${item.days_to_race} 天`
                              : '比赛已结束'}
                          </Text>
                        </View>
                        <View className='follow-card__actions'>
                          {item.registration.registration_status === 0 && !item.is_custom && (
                            <View className='follow-card__go-reg' onClick={() => handleCardClick(item)}>
                              <Text>去报名</Text>
                              <Icon name='chevron-right' size={24} color='#FF5C38' />
                            </View>
                          )}
                          <View
                            className='follow-card__unfavorite'
                            onClick={(e) => { e.stopPropagation(); handleUnfavorite(item) }}
                          >
                            <Icon name='trash-2' size={22} color='#E23A2E' />
                            <Text>{item.is_custom ? '删除' : '取消关注'}</Text>
                          </View>
                        </View>
                      </View>
                    </View>
                  )}
                </View>
              )
            })}
          </View>
        )}

        {/* 添加自定义赛事按钮 */}
        {loggedIn && items.length > 0 && (
          <View className='add-race-btn' onClick={handleAddRace}>
            <Icon name='plus-circle' size={36} color='#FF5C38' />
            <Text>添加自定义赛事</Text>
          </View>
        )}
      </View>

      <TabBar current='follow' />
    </View>
  )
}
