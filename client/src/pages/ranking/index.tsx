import { View, Text, Image, ScrollView } from '@tarojs/components'
import { useState, useEffect, useCallback } from 'react'
import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import Icon from '@/components/Icon'
import Empty from '@/components/Empty'
import TabBar from '@/components/TabBar'
import api, { RankingItem, RankingListOut, resolveUrl } from '@/services/api'
import './index.scss'

type Metric = 'distance' | 'half_marathon_pb' | 'full_marathon_pb' | 'spent'

const METRICS: { key: Metric; label: string }[] = [
  { key: 'distance', label: '总跑量' },
  { key: 'half_marathon_pb', label: '半马PB' },
  { key: 'full_marathon_pb', label: '全马PB' },
  { key: 'spent', label: '总花费' },
]

const GENDERS: { value: number; label: string }[] = [
  { value: 0, label: '全部' },
  { value: 1, label: '男' },
  { value: 2, label: '女' },
]

// 与 server/app/services/config_service.py SEED 逐字对齐
const AGE_GROUPS: { value: number; label: string }[] = [
  { value: 0, label: '全部' },
  { value: 1, label: '34岁以下' },
  { value: 2, label: '35-39岁' },
  { value: 3, label: '40-44岁' },
  { value: 4, label: '45-49岁' },
  { value: 5, label: '50-54岁' },
  { value: 6, label: '55-59岁' },
  { value: 7, label: '60-64岁' },
  { value: 8, label: '65岁以上' },
]

function genderGlyph(g?: number): string {
  if (g === 1) return '♂'
  if (g === 2) return '♀'
  return ''
}

export default function Ranking() {
  const [metric, setMetric] = useState<Metric>('distance')
  const [gender, setGender] = useState(0)
  const [ageGroup, setAgeGroup] = useState(0)
  const [data, setData] = useState<RankingListOut | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.listRankings({ metric, gender, age_group: ageGroup, limit: 50 })
      setData(res)
    } catch (e) {
      console.warn('[Ranking] fetch failed', e)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [metric, gender, ageGroup])

  useDidShow(() => {
    try { Taro.hideTabBar({ animation: false }) } catch (_) {}
    fetchData()
  })

  // metric/gender/ageGroup 切换时立即刷新（首次 useDidShow 已触发一次）
  useEffect(() => {
    fetchData()
  }, [fetchData])

  usePullDownRefresh(async () => {
    await fetchData()
    Taro.stopPullDownRefresh()
  })

  const items = data?.items ?? []
  const myRank = data?.my_rank ?? null
  const currentMetric = METRICS.find((m) => m.key === metric)?.label || ''

  return (
    <View className='page-ranking'>
      {/* ===== Hero ===== */}
      <View className='ranking-hero'>
        <View className='ranking-hero__bg'>
          <Icon name='trending-up' size={120} color='rgba(255,255,255,0.18)' className='ranking-hero__icon' />
        </View>
        <Text className='ranking-hero__title'>跑者排行</Text>
        <Text className='ranking-hero__sub'>看看你在跑友中的位置</Text>
      </View>

      {/* ===== Metric Tabs ===== */}
      <ScrollView scrollX className='metric-tabs no-scrollbar' enhanced show-scrollbar={false}>
        {METRICS.map((m) => (
          <View
            key={m.key}
            className={`metric-tab ${metric === m.key ? 'metric-tab--active' : ''}`}
            onClick={() => setMetric(m.key)}
          >
            <Text>{m.label}</Text>
          </View>
        ))}
      </ScrollView>

      {/* ===== 筛选（性别 + 年龄段） ===== */}
      <View className='ranking-filters'>
        <ScrollView scrollX className='filter-row no-scrollbar' enhanced show-scrollbar={false}>
          {GENDERS.map((g) => (
            <View
              key={g.value}
              className={`filter-chip ${gender === g.value ? 'filter-chip--active' : ''}`}
              onClick={() => setGender(g.value)}
            >
              <Text>{g.label}</Text>
            </View>
          ))}
        </ScrollView>
        <ScrollView scrollX className='filter-row no-scrollbar' enhanced show-scrollbar={false}>
          {AGE_GROUPS.map((a) => (
            <View
              key={a.value}
              className={`filter-chip ${ageGroup === a.value ? 'filter-chip--active' : ''}`}
              onClick={() => setAgeGroup(a.value)}
            >
              <Text>{a.label}</Text>
            </View>
          ))}
        </ScrollView>
      </View>

      {/* ===== 我的排名 sticky 卡 ===== */}
      {data && (
        <View className={`my-rank-card ${myRank ? '' : 'my-rank-card--muted'}`}>
          <View className='my-rank-card__left'>
            <Text className='my-rank-card__label'>我的排名</Text>
            <Text className='my-rank-card__rank'>{myRank ? `#${myRank.rank}` : '未上榜'}</Text>
            <Text className='my-rank-card__metric'>{currentMetric}</Text>
          </View>
          <View className='my-rank-card__right'>
            <Text className='my-rank-card__value'>{data.my_value_label ?? '—'}</Text>
            {data.my_insight && (
              <Text className='my-rank-card__insight'>{data.my_insight}</Text>
            )}
          </View>
        </View>
      )}

      {/* ===== 列表 ===== */}
      <View className='ranking-list'>
        <View className='ranking-list__header'>
          <Text className='ranking-list__title'>本榜共 {data?.total_users ?? 0} 位跑者</Text>
          {loading && <Text className='ranking-list__loading'>加载中…</Text>}
        </View>

        {!loading && items.length === 0 ? (
          <Empty text='这个分组还没有人上榜' icon='trending-up' hint='换个筛选条件，或先去跑一场' />
        ) : (
          items.map((it, idx) => <RankingCard key={it.user_id} item={it} index={idx} />)
        )}
      </View>

      <TabBar current='ranking' />
    </View>
  )
}

function RankingCard({ item, index = 0 }: { item: RankingItem; index?: number }) {
  const avatarUrl = resolveUrl(item.avatar || '')
  const gGlyph = genderGlyph(item.gender)
  const ageLabel = AGE_GROUPS.find((a) => a.value === item.age_group)?.label || ''
  const isTop3 = item.rank <= 3
  const delay = Math.min(index, 10) * 50
  return (
    <View
      className={`ranking-card ${isTop3 ? 'ranking-card--top' : ''}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <View className={`ranking-card__rank ranking-card__rank--${item.rank}`}>
        <Text>{item.rank}</Text>
      </View>

      <View className='ranking-card__main'>
        <View className='ranking-card__top'>
          <View className='ranking-card__avatar'>
            {avatarUrl ? (
              <Image className='ranking-card__avatar-img' src={avatarUrl} mode='aspectFill' />
            ) : (
              <Text className='ranking-card__avatar-placeholder'>
                {(item.nickname || '跑')[0]}
              </Text>
            )}
          </View>
          <Text className='ranking-card__nick ellipsis'>{item.nickname}</Text>
          {item.gender === 1 || item.gender === 2 ? (
            <View className={`gender-chip gender-chip--${item.gender}`}>
              <Text>{gGlyph}</Text>
            </View>
          ) : null}
          {item.age_group && item.age_group >= 1 ? (
            <View className='age-chip'>
              <Text>{ageLabel}</Text>
            </View>
          ) : null}
        </View>
        <View className='ranking-card__bot'>
          <Text className='ranking-card__value'>{item.value_label}</Text>
          <Text className='ranking-card__sub'>
            {item.finished_count} 场完赛 · 累计报名 {item.registered_count} 场
          </Text>
        </View>
      </View>
    </View>
  )
}