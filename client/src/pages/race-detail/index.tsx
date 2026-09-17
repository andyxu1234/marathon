import { View, Text } from '@tarojs/components'
import { useState, useRef } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import Icon from '@/components/Icon'
import Empty from '@/components/Empty'
import api, { EventDetail } from '@/services/api'
import { useUserStore } from '@/stores'
import './index.scss'

// 状态 → 徽章
function statusMeta(status: number): { label: string; cls: string } {
  switch (status) {
    case 2: return { label: '报名中', cls: 'badge-success' }
    case 1: return { label: '即将开跑', cls: 'badge-warning' }
    case 3: return { label: '报名结束', cls: 'badge-muted' }
    case 4: return { label: '比赛中', cls: 'badge-warning' }
    case 5: return { label: '已结束', cls: 'badge-muted' }
    default: return { label: '即将开跑', cls: 'badge-warning' }
  }
}

// 等级 → 徽章
function levelMeta(level: number): { label: string; cls: string } {
  switch (level) {
    case 1: return { label: '白金标赛事', cls: 'badge-outline' }
    case 2: return { label: '金标赛事', cls: 'badge-outline' }
    case 3: return { label: '精英标赛事', cls: 'badge-outline' }
    case 4: return { label: '标牌赛事', cls: 'badge-outline' }
    case 5: return { label: '田协赛事', cls: 'badge-outline' }
    default: return { label: '标牌赛事', cls: 'badge-outline' }
  }
}

export default function RaceDetail() {
  const [detail, setDetail] = useState<EventDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [favoriting, setFavoriting] = useState(false)
  const { ensureLoggedIn } = useUserStore()

  // 同 id 复用已加载数据：从列表反复进出同一赛事时秒开，不重复请求/重渲染（避免卡顿感）
  const loadedIdRef = useRef<number | null>(null)

  // 获取页面参数
  const getPageId = (): number => {
    const inst = Taro.getCurrentInstance()
    const id = inst?.router?.params?.id
    return id ? parseInt(id, 10) : 0
  }

  const fetchDetail = async () => {
    const id = getPageId()
    if (!id) return
    // 已加载过同一赛事且数据仍在，直接跳过请求，避免重复渲染造成的卡顿
    if (loadedIdRef.current === id && detail) return
    setLoading(true)
    try {
      const res = await api.getEvent(id)
      loadedIdRef.current = id
      setDetail(res)
    } catch (e) {
      console.warn('[RaceDetail] fetch failed', e)
      Taro.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }

  useDidShow(() => {
    fetchDetail()
  })

  const handleFavorite = async () => {
    if (!detail) return
    setFavoriting(true)
    try {
      // 需求 2：关注时不做登录校验——静默补登录态后直接操作；失败重试一次（401 场景）
      const ensure = async () => {
        const ok = await ensureLoggedIn()
        if (!ok) throw new Error('登录失败，请稍后重试')
      }
      await ensure()

      const doToggle = async () => {
        if (detail.is_favorite) {
          await api.unfavoriteEvent(detail.event_id)
          setDetail({ ...detail, is_favorite: false })
          Taro.showToast({ title: '已取消关注', icon: 'none' })
        } else {
          await api.favoriteEvent(detail.event_id)
          setDetail({ ...detail, is_favorite: true })
          Taro.showToast({ title: '关注成功', icon: 'success' })
        }
      }

      try {
        await doToggle()
      } catch (err: any) {
        // 401 → 再 ensure 一次（可能 token 被清）后重试，仍然失败就把错误抛出去
        if (err?.statusCode === 401) {
          await ensure()
          await doToggle()
        } else {
          throw err
        }
      }
    } catch (e: any) {
      console.warn('[RaceDetail] favorite failed', e)
      const msg = e?.message || '操作失败'
      Taro.showToast({ title: msg.length > 14 ? '操作失败' : msg, icon: 'none' })
    } finally {
      setFavoriting(false)
    }
  }

  if (!detail && loading) {
    return (
      <View className='page-race-detail'>
        {/* 骨架屏：结构占位 + 珊瑚呼吸光，替代"白屏+加载中文字"，消除突然全量渲染的跳跃感 */}
        <View className='sk'>
          <View className='sk-hero' />
          <View className='sk-quick'>
            <View className='sk-pill' />
            <View className='sk-pill' />
            <View className='sk-pill' />
          </View>
          <View className='sk-section'>
            <View className='sk-line sk-w70' />
            <View className='sk-line' />
            <View className='sk-line sk-w40' />
            <View className='sk-line' />
            <View className='sk-line sk-w85' />
          </View>
          <View className='sk-section'>
            <View className='sk-line sk-w50' />
            <View className='sk-line' />
            <View className='sk-line sk-w60' />
          </View>
        </View>
      </View>
    )
  }

  if (!detail) {
    return (
      <View className='page-race-detail'>
        <Empty text='赛事不存在' icon='search' />
      </View>
    )
  }

  const st = statusMeta(detail.event_status)
  const lvl = levelMeta(detail.event_level)

  // 信息行
  const infoRows: { label: string; value: string }[] = []
  if (detail.event_year) {
    infoRows.push({ label: '赛事年份', value: `${detail.event_year}` })
  }
  if (detail.start_date_label) {
    infoRows.push({ label: '比赛日期', value: detail.start_date_label })
  }
  if (detail.address || detail.location) {
    infoRows.push({ label: '比赛地点', value: detail.address || detail.location || '' })
  }
  if (detail.start_point) {
    infoRows.push({ label: '起点', value: detail.start_point })
  }
  if (detail.end_point) {
    infoRows.push({ label: '终点', value: detail.end_point })
  }
  if (detail.event_level_label) {
    infoRows.push({ label: '赛事等级', value: detail.event_level_label })
  }
  if (detail.certification) {
    infoRows.push({ label: '田协认证', value: detail.certification })
  }
  if (detail.registration_start_time && detail.registration_end_time) {
    infoRows.push({ label: '报名时间', value: `${detail.registration_start_time} - ${detail.registration_end_time}` })
  } else if (detail.registration_start_time) {
    infoRows.push({ label: '报名时间', value: `${detail.registration_start_time} 起` })
  }
  if (detail.registration_fee != null) {
    infoRows.push({ label: '默认报名费', value: `¥${detail.registration_fee}` })
  }
  if (detail.registration_channels) {
    infoRows.push({ label: '报名渠道', value: detail.registration_channels })
  }
  if (detail.organizer) {
    infoRows.push({ label: '主办单位', value: detail.organizer })
  }
  if (detail.contact_phone) {
    infoRows.push({ label: '联系电话', value: detail.contact_phone })
  }

  // 多项目设置（items_json 优先；无则回退 event_type_label 单项）
  const items = detail.items_json && detail.items_json.length > 0 ? detail.items_json : null

  // 报名须知（按 introduction / registration_guide 拆分）
  const introText = detail.introduction || detail.description || ''
  const guideText = detail.registration_guide || ''

  return (
    <View className='page-race-detail'>
      {/* Hero 区 */}
      <View className='hero-section'>
        <Text className='hero-title'>{detail.event_name}</Text>
        <View className='hero-badges'>
          <Text className={`hero-badge hero-badge--solid ${st.cls}`}>{st.label}</Text>
          <Text className={`hero-badge hero-badge--outline ${lvl.cls}`}>{lvl.label}</Text>
          {detail.certification ? (
            <Text className='hero-badge hero-badge--outline badge-outline'>{detail.certification}</Text>
          ) : null}
        </View>
      </View>

      {/* 快速信息卡片 */}
      <View className='quick-info-row'>
        <View className='quick-info-card'>
          <Icon name='calendar' size={36} color='#FF5C38' />
          <Text className='quick-info-label'>比赛日期</Text>
          <Text className='quick-info-value'>{detail.start_date_label || '待定'}</Text>
        </View>
        <View className='quick-info-card'>
          <Icon name='map-pin' size={36} color='#FF5C38' />
          <Text className='quick-info-label'>比赛地点</Text>
          <Text className='quick-info-value'>{detail.city || detail.location || '待定'}</Text>
        </View>
        <View className='quick-info-card'>
          <Icon name='award' size={36} color='#FF5C38' />
          <Text className='quick-info-label'>赛事等级</Text>
          <Text className='quick-info-value'>{detail.event_level_label || '待定'}</Text>
        </View>
      </View>

      {/* 赛事信息 */}
      <View className='info-section'>
        <Text className='section-title'>赛事信息</Text>
        <View className='info-card'>
          {infoRows.map((row, idx) => (
            <View key={idx} className={`info-row ${idx === infoRows.length - 1 ? 'info-row--last' : ''}`}>
              <Text className='info-label'>{row.label}</Text>
              <Text className='info-value'>{row.value}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* 项目设置（多项目表格） */}
      {items ? (
        <View className='info-section'>
          <Text className='section-title'>项目设置</Text>
          <View className='info-card'>
            {items.map((it, idx) => (
              <View key={idx} className={`info-row ${idx === items.length - 1 ? 'info-row--last' : ''}`}>
                <Text className='info-label'>{it.type}</Text>
                <View className='info-value items-value'>
                  {it.fee != null ? <Text className='item-fee'>¥{it.fee}</Text> : null}
                  {it.scale != null ? <Text className='item-scale'>规模 {it.scale.toLocaleString()}</Text> : null}
                </View>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {/* 赛事介绍 */}
      {introText || guideText ? (
        <View className='info-section'>
          <Text className='section-title'>赛事介绍</Text>
          <View className='info-card'>
            {introText ? (
              <Text className='intro-text'>{introText}</Text>
            ) : null}
            {guideText ? (
              <>
                <Text className='guide-title'>报名须知</Text>
                <View className='notice-list'>
                  {guideText.split('\n').filter(Boolean).map((line, i) => (
                    <View key={i} className='notice-item'>
                      <Text className='notice-text'>{line}</Text>
                    </View>
                  ))}
                </View>
              </>
            ) : null}
          </View>
        </View>
      ) : null}

      {/* 中签分析 */}
      {detail.lottery_history ? (
        <View className='info-section'>
          <Text className='section-title'>中签分析</Text>
          <View className='info-card'>
            <Text className='intro-text'>{detail.lottery_history}</Text>
          </View>
        </View>
      ) : null}

      {/* 底部关注按钮 */}
      <View className='sticky-bottom-bar'>
        <View
          className={`follow-btn ${detail.is_favorite ? 'follow-btn--active' : ''} ${favoriting ? 'follow-btn--loading' : ''}`}
          onClick={!favoriting ? handleFavorite : undefined}
        >
          <Icon name='heart' size={32} color={detail.is_favorite ? '#FF5C38' : '#FFFFFF'} />
          <Text>{favoriting ? '处理中…' : detail.is_favorite ? '已关注' : '关注赛事'}</Text>
        </View>
      </View>
    </View>
  )
}
