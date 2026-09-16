import { View, Text, Input, ScrollView } from '@tarojs/components'
import { useState, useMemo } from 'react'
import Taro, { useDidShow, usePullDownRefresh, useReachBottom } from '@tarojs/taro'
import EventCard from '@/components/EventCard'
import Empty from '@/components/Empty'
import TabBar from '@/components/TabBar'
import Icon from '@/components/Icon'
import api, { EventBrief, EventFilters, EventStats } from '@/services/api'
import { useFilterStore } from '@/stores'
import { getAllProvinces, getCitiesByProvince } from '@/utils/regions'
import './index.scss'

interface FilterTab {
  key: string
  label: string
}

export default function Home() {
  const filterStore = useFilterStore()

  const [events, setEvents] = useState<EventBrief[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<EventFilters | null>(null)
  const [stats, setStats] = useState<EventStats | null>(null)

  // 搜索输入
  const [keywordInput, setKeywordInput] = useState(filterStore.keyword)

  // 过滤面板状态
  const [openFilterKey, setOpenFilterKey] = useState<string | null>(null)
  // 临时过滤状态（仅在面板打开时修改，点击确认才提交到 store）
  const [tempType, setTempType] = useState<number | null>(filterStore.type)
  const [tempLevel, setTempLevel] = useState<number | null>(filterStore.level)
  const [tempStatus, setTempStatus] = useState<number | null>(filterStore.status)
  const [tempYear, setTempYear] = useState<number | null>(filterStore.year)
  const [tempMonth, setTempMonth] = useState<number | null>(filterStore.month)
  const [tempProvince, setTempProvince] = useState<string | null>(filterStore.province)
  const [tempCity, setTempCity] = useState<string | null>(filterStore.city)

  // 过滤标签配置
  const filterTabs: FilterTab[] = [
    { key: 'type', label: '类型' },
    { key: 'level', label: '等级' },
    { key: 'date', label: '日期' },
    { key: 'region', label: '区域' },
    { key: 'status', label: '状态' },
  ]

  const curYear = new Date().getFullYear()

  // 年份选项（当年 ~ 当年+3）
  const yearOptions = useMemo(() => {
    const cur = new Date().getFullYear()
    const years: { value: number; label: string }[] = []
    for (let y = cur; y <= cur + 3; y++) {
      years.push({ value: y, label: `${y}年` })
    }
    return years
  }, [])

  // 月份选项（1~12）
  const monthOptions = useMemo(() => {
    const months: { value: number; label: string }[] = []
    for (let m = 1; m <= 12; m++) {
      months.push({ value: m, label: `${m}月` })
    }
    return months
  }, [])

  const fetchEvents = async (p = 1, append = false) => {
    setLoading(true)
    try {
      const params = { page: p, page_size: 10, ...filterStore.toParams() }
      const res = await api.getEvents(params)
      setEvents(append ? [...events, ...res.items] : res.items)
      setTotal(res.total)
      setPage(p)
    } catch (e) {
      console.warn('[Home] fetchEvents failed', e)
    } finally {
      setLoading(false)
    }
  }

  const fetchFilters = async () => {
    try {
      setFilters(await api.getEventFilters())
    } catch (e) {
      console.warn('[Home] fetchFilters failed', e)
    }
  }

  const fetchStats = async () => {
    try {
      setStats(await api.getEventStats())
    } catch (e) {
      console.warn('[Home] fetchStats failed', e)
    }
  }

  useDidShow(() => {
    try { Taro.hideTabBar({ animation: false }) } catch (_) {}
    fetchFilters()
    fetchStats()
    fetchEvents(1)
  })

  usePullDownRefresh(async () => {
    await fetchEvents(1)
    Taro.stopPullDownRefresh()
  })

  // 触底自动加载下一页（loading 中或已加载全部则短路）
  useReachBottom(() => {
    if (loading || events.length >= total) return
    fetchEvents(page + 1, true)
  })

  const handleSearch = () => {
    filterStore.setFilter('keyword', keywordInput)
    fetchEvents(1)
  }

  const handleCardClick = (id: number) => {
    Taro.navigateTo({ url: `/pages/race-detail/index?id=${id}` })
  }

  const toggleFilterTab = (key: string) => {
    if (openFilterKey === key) {
      setOpenFilterKey(null)
    } else {
      // 打开新标签时，同步临时状态到当前值
      setTempType(filterStore.type)
      setTempLevel(filterStore.level)
      setTempStatus(filterStore.status)
      setTempYear(filterStore.year)
      setTempMonth(filterStore.month)
      setTempProvince(filterStore.province)
      setTempCity(filterStore.city)
      setOpenFilterKey(key)
    }
  }

  // 省/市级联数据
  const provinceOptions = useMemo(
    () => getAllProvinces().map((p) => ({ value: p.matchName, label: p.name, rawProvinceKey: p.provinceKey })),
    []
  )

  const currentProvinceRawKey = useMemo(() => {
    if (!tempProvince) return ''
    return provinceOptions.find((o) => o.value === tempProvince)?.rawProvinceKey ?? ''
  }, [tempProvince, provinceOptions])

  const cityOptions = useMemo(() => {
    if (!currentProvinceRawKey) return [] as { value: string; label: string }[]
    return getCitiesByProvince(currentProvinceRawKey).map((c) => ({ value: c.matchName, label: c.name }))
  }, [currentProvinceRawKey])

  // 获取当前标签对应的 values
  const currentValues = useMemo(() => {
    switch (openFilterKey) {
      case 'type':
        return {
          key: 'type',
          values: (filters?.types || []).map((v) => ({ value: v.value, label: v.label })),
          current: tempType,
          setCurrent: setTempType
        }
      case 'level':
        return {
          key: 'level',
          values: (filters?.levels || []).map((v) => ({ value: v.value, label: v.label })),
          current: tempLevel,
          setCurrent: setTempLevel
        }
      case 'status':
        return {
          key: 'status',
          values: (filters?.statuses || []).map((v) => ({ value: v.value, label: v.label })),
          current: tempStatus,
          setCurrent: setTempStatus
        }
      case 'region':
        return null
      case 'date':
        return null
      default:
        return null
    }
  }, [openFilterKey, filters, tempType, tempLevel, tempStatus])

  // 重置所有临时过滤条件
  const handleReset = () => {
    setTempType(null)
    setTempLevel(null)
    setTempStatus(null)
    setTempYear(null)
    setTempMonth(null)
    setTempProvince(null)
    setTempCity(null)
  }

  // 确认过滤：把临时状态提交到 store，关闭面板，重新请求
  const handleConfirm = () => {
    filterStore.setFilter('type', tempType)
    filterStore.setFilter('level', tempLevel)
    filterStore.setFilter('status', tempStatus)
    filterStore.setFilter('year', tempYear)
    filterStore.setFilter('month', tempMonth)
    filterStore.setFilter('province', tempProvince)
    filterStore.setFilter('city', tempCity)
    setOpenFilterKey(null)
    fetchEvents(1)
  }

  // 统计卡片点击 → 快速按状态筛选
  const onStatClick = (status?: number) => {
    filterStore.setFilter('status', status ?? null)
    fetchEvents(1)
  }

  // 统计已激活的过滤维度数（不算 keyword；日期/区域各算 1 维，与 chip 数一致）
  const activeFilterCount = useMemo(() => {
    let n = 0
    if (filterStore.type != null) n++
    if (filterStore.level != null) n++
    if (filterStore.status != null) n++
    if (filterStore.year != null || filterStore.month != null) n++
    if (filterStore.province || filterStore.city) n++
    return n
  }, [filterStore.type, filterStore.level, filterStore.status, filterStore.year, filterStore.month, filterStore.province, filterStore.city])

  // 已选过滤标签行（用于展开面板外展示）
  const activeChips = useMemo(() => {
    const chips: { key: string; label: string }[] = []
    if (filterStore.type != null) {
      const t = filters?.types.find((v) => v.value === filterStore.type)
      if (t) chips.push({ key: 'type', label: t.label })
    }
    if (filterStore.level != null) {
      const l = filters?.levels.find((v) => v.value === filterStore.level)
      if (l) chips.push({ key: 'level', label: l.label })
    }
    if (filterStore.status != null) {
      const s = filters?.statuses.find((v) => v.value === filterStore.status)
      if (s) chips.push({ key: 'status', label: s.label })
    }
    // 日期：年/月任一存在即一个 chip（删除时成对清空）
    if (filterStore.year != null || filterStore.month != null) {
      const y = filterStore.year
      const m = filterStore.month
      let label = ''
      if (y != null && m != null) label = `${y}年${m}月`
      else if (y != null) label = `${y}年`
      else label = `${m}月`
      chips.push({ key: 'date', label })
    }
    // 区域：省/市任一存在即一个 chip（删除时成对清空）
    if (filterStore.province || filterStore.city) {
      const label = filterStore.city
        ? [filterStore.province, filterStore.city].filter(Boolean).join('·')
        : (filterStore.province as string)
      chips.push({ key: 'region', label })
    }
    return chips
  }, [filterStore, filters])

  // chip 删除 → 成对清空对应维度的全部字段
  const CHIP_CLEAR_KEYS: Record<string, string[]> = {
    type: ['type'],
    level: ['level'],
    status: ['status'],
    date: ['year', 'month'],
    region: ['province', 'city'],
  }

  const removeChip = (key: string) => {
    ;(CHIP_CLEAR_KEYS[key] || [key]).forEach((k) => filterStore.setFilter(k, null))
    fetchEvents(1)
  }

  // 点击"不限"城市 → 清除 city 选择，但保留 province
  const selectUnlimitedCity = () => {
    setTempCity(null)
  }

  // 一键清除所有筛选条件（保留关键词）
  const handleClearAll = () => {
    const keys = ['type', 'level', 'status', 'year', 'month', 'province', 'city'] as const
    keys.forEach((k) => filterStore.setFilter(k, null))
    fetchEvents(1)
  }

  return (
    <View className='page-home'>
      {/* Hero —— 珊瑚渐变 + 斜向速度条纹 + 超大数字 */}
      <View className='hero'>
        <View className='hero__stripes' />
        <View className='hero__inner'>
          <Text className='hero__eyebrow'>{curYear} 赛季 · 全国赛事</Text>
          <View className='hero__total'>
            <Text className='hero__total-num num'>{stats?.total ?? '--'}</Text>
            <Text className='hero__total-unit'>场在册</Text>
          </View>
          <View className='hero__grid'>
            <View className='hero__cell' onClick={() => onStatClick(2)}>
              <Text className='hero__cell-num num'>{stats?.registering ?? '--'}</Text>
              <Text className='hero__cell-label'>报名中</Text>
            </View>
            <View className='hero__cell' onClick={() => onStatClick(1)}>
              <Text className='hero__cell-num num'>{stats?.upcoming ?? '--'}</Text>
              <Text className='hero__cell-label'>未开始</Text>
            </View>
            <View className='hero__cell' onClick={() => onStatClick(5)}>
              <Text className='hero__cell-num num'>{stats?.finished ?? '--'}</Text>
              <Text className='hero__cell-label'>已结束</Text>
            </View>
          </View>
        </View>
      </View>

      {/* 搜索框 —— 上移压在 Hero 底部，制造层次 */}
      <View className='search'>
        <Icon name='search' size={30} color='#C9B9AC' />
        <Input
          className='search__input'
          placeholder='搜索赛事名称 / 城市'
          placeholderClass='search__placeholder'
          placeholderStyle={`color:#A3968D;font-size:25px;font-weight:400;line-height:1.4;`}
          value={keywordInput}
          onInput={(e) => setKeywordInput(e.detail.value)}
          onConfirm={handleSearch}
          confirmType='search'
        />
        {keywordInput ? (
          <View
            className='search__clear'
            onClick={() => { setKeywordInput(''); filterStore.setFilter('keyword', ''); fetchEvents(1) }}
          >
            <Icon name='x' size={26} color='#C9B9AC' />
          </View>
        ) : null}
      </View>

      {/* 过滤标签栏 + 下拉面板 */}
      <View className='filter-wrapper'>
        <View className='filter-tabs'>
          {filterTabs.map((tab) => {
            const isActive = openFilterKey === tab.key
            const hasValue =
              (tab.key === 'type' && filterStore.type != null) ||
              (tab.key === 'level' && filterStore.level != null) ||
              (tab.key === 'status' && filterStore.status != null) ||
              (tab.key === 'date' && (filterStore.year != null || filterStore.month != null)) ||
              (tab.key === 'region' && (filterStore.province != null || filterStore.city != null))
            return (
              <View
                key={tab.key}
                className={`filter-tab ${isActive ? 'filter-tab--active' : ''} ${hasValue ? 'filter-tab--filled' : ''}`}
                onClick={() => toggleFilterTab(tab.key)}
              >
                <Text
                  className={`filter-tab__label ${isActive ? 'filter-tab__label--active' : ''} ${hasValue ? 'filter-tab__label--filled' : ''}`}
                >
                  {tab.label}
                </Text>
                <Icon
                  name={isActive ? 'chevron-up' : 'chevron-down'}
                  size={22}
                  color={isActive || hasValue ? '#FF5C38' : '#B9AAA0'}
                />
              </View>
            )
          })}
          {activeFilterCount > 0 && (
            <View className='filter-clear' onClick={handleClearAll}>
              <Icon name='x' size={20} color='#FF5C38' />
              <Text className='filter-clear__text'>清除</Text>
              <Text className='filter-clear__count'>{activeFilterCount}</Text>
            </View>
          )}
        </View>

        {/* 下拉面板 */}
        {openFilterKey && (
          <View className='filter-dropdown'>
            {/* 日期双列级联（年+月） */}
            {openFilterKey === 'date' && (
              <View className='region-cascade'>
                <ScrollView scrollY className='region-cascade__left'>
                  <View
                    className={`region-item region-item--prov ${tempYear == null ? 'region-item--selected' : ''}`}
                    onClick={() => { setTempYear(null); setTempMonth(null) }}
                  >
                    <Text className={`region-item__text ${tempYear == null ? 'region-item__text--selected' : ''}`}>
                      不限
                    </Text>
                    {tempYear == null && <View className='region-item__border' />}
                  </View>
                  {yearOptions.map((opt) => {
                    const selected = tempYear === opt.value
                    return (
                      <View
                        key={opt.value}
                        className={`region-item region-item--prov ${selected ? 'region-item--selected' : ''}`}
                        onClick={() => { setTempYear(opt.value); setTempMonth(null) }}
                      >
                        <Text className={`region-item__text ${selected ? 'region-item__text--selected' : ''}`}>
                          {opt.label}
                        </Text>
                        {selected && <View className='region-item__border' />}
                      </View>
                    )
                  })}
                </ScrollView>
                <ScrollView scrollY className='region-cascade__right'>
                  <View
                    className={`region-item region-item--city ${tempMonth == null ? 'region-item--selected' : ''}`}
                    onClick={() => setTempMonth(null)}
                  >
                    <Text className={`region-item__text ${tempMonth == null ? 'region-item__text--selected' : ''}`}>
                      不限
                    </Text>
                    {tempMonth == null && <View className='region-item__border' />}
                  </View>
                  {monthOptions.map((opt) => {
                    const selected = tempMonth === opt.value
                    return (
                      <View
                        key={opt.value}
                        className={`region-item region-item--city ${selected ? 'region-item--selected' : ''}`}
                        onClick={() => setTempMonth(opt.value)}
                      >
                        <Text className={`region-item__text ${selected ? 'region-item__text--selected' : ''}`}>
                          {opt.label}
                        </Text>
                        {selected && <View className='region-item__border' />}
                      </View>
                    )
                  })}
                </ScrollView>
              </View>
            )}

            {/* 区域双列级联（省+市） */}
            {openFilterKey === 'region' && (
              <View className='region-cascade'>
                <ScrollView scrollY className='region-cascade__left'>
                  {provinceOptions.map((prov) => {
                    const selected = tempProvince === prov.value
                    return (
                      <View
                        key={prov.value}
                        className={`region-item region-item--prov ${selected ? 'region-item--selected' : ''}`}
                        onClick={() => { setTempProvince(prov.value); setTempCity(null) }}
                      >
                        <Text className={`region-item__text ${selected ? 'region-item__text--selected' : ''}`}>
                          {prov.label}
                        </Text>
                        {selected && <View className='region-item__border' />}
                      </View>
                    )
                  })}
                </ScrollView>
                <ScrollView scrollY className='region-cascade__right'>
                  <View
                    className={`region-item region-item--city ${tempCity == null ? 'region-item--selected' : ''}`}
                    onClick={selectUnlimitedCity}
                  >
                    <Text className={`region-item__text ${tempCity == null ? 'region-item__text--selected' : ''}`}>
                      不限
                    </Text>
                    {tempCity == null && <View className='region-item__border' />}
                  </View>
                  {cityOptions.map((city) => {
                    const selected = tempCity === city.value
                    return (
                      <View
                        key={city.value}
                        className={`region-item region-item--city ${selected ? 'region-item--selected' : ''}`}
                        onClick={() => setTempCity(city.value)}
                      >
                        <Text className={`region-item__text ${selected ? 'region-item__text--selected' : ''}`}>
                          {city.label}
                        </Text>
                        {selected && <View className='region-item__border' />}
                      </View>
                    )
                  })}
                </ScrollView>
              </View>
            )}

            {/* 普通单选列表（类型/等级/状态） */}
            {openFilterKey !== 'date' && openFilterKey !== 'region' && currentValues && (
              <ScrollView scrollY className='filter-single-list'>
                <View
                  className={`filter-item ${currentValues.current == null ? 'filter-item--selected' : ''}`}
                  onClick={() => currentValues.setCurrent(null)}
                >
                  <Text className={`filter-item__text ${currentValues.current == null ? 'filter-item__text--selected' : ''}`}>
                    不限
                  </Text>
                  {currentValues.current == null && (
                    <View className='filter-item__check'>
                      <Icon name='check' size={24} color='#FF5C38' />
                    </View>
                  )}
                </View>
                {currentValues.values.map((opt) => {
                  const selected = currentValues.current === opt.value
                  return (
                    <View
                      key={String(opt.value)}
                      className={`filter-item ${selected ? 'filter-item--selected' : ''}`}
                      onClick={() => currentValues.setCurrent(opt.value)}
                    >
                      <Text className={`filter-item__text ${selected ? 'filter-item__text--selected' : ''}`}>
                        {opt.label}
                      </Text>
                      {selected && (
                        <View className='filter-item__check'>
                          <Icon name='check' size={24} color='#FF5C38' />
                        </View>
                      )}
                    </View>
                  )
                })}
              </ScrollView>
            )}

            {/* 底部操作栏 */}
            <View className='filter-dropdown-footer'>
              <View className='filter-dropdown-btn filter-dropdown-btn--reset' onClick={handleReset}>
                <Text>重置</Text>
              </View>
              <View className='filter-dropdown-btn filter-dropdown-btn--confirm' onClick={handleConfirm}>
                <Text>确认</Text>
              </View>
            </View>
          </View>
        )}
      </View>

      {/* 下拉面板遮罩 */}
      {openFilterKey && (
        <View className='filter-dropdown-mask' onClick={() => setOpenFilterKey(null)} />
      )}

      {/* 已选过滤标签 */}
      {activeChips.length > 0 ? (
        <ScrollView scrollX className='active-chips-scroll no-scrollbar'>
          <View className='active-chips'>
            {activeChips.map((chip) => (
              <View key={chip.key} className='active-chip' onClick={() => removeChip(chip.key)}>
                <Text className='active-chip__text'>{chip.label}</Text>
                <View className='active-chip__close'>
                  <Icon name='x' size={20} color='#FF5C38' />
                </View>
              </View>
            ))}
          </View>
        </ScrollView>
      ) : null}

      {/* 赛事列表 */}
      <View className='content-area'>
        <View className='content-area__head'>
          <Text className='content-area__title'>近期赛事</Text>
          <Text className='content-area__count'>共 {total} 场</Text>
        </View>

        {events.length === 0 && !loading ? (
          <Empty text='没有找到匹配的赛事' icon='search' hint='试试放宽日期或区域条件' />
        ) : (
          <View className='race-list'>
            {events.map((e, idx) => (
              <EventCard key={e.event_id} event={e} index={idx} onClick={handleCardClick} />
            ))}
          </View>
        )}

        {/* 底部加载状态（已改为触底自动加载，按钮降级为提示文字） */}
        <View className='load-more'>
          {loading && events.length > 0 ? (
            <Text className='load-more__text load-more__text--loading'>加载中...</Text>
          ) : events.length >= total && events.length > 0 ? (
            <Text className='load-more__text'>— 已加载全部 —</Text>
          ) : null}
        </View>
      </View>

      <TabBar current='home' />
    </View>
  )
}