import { View, Text, Input, Picker } from '@tarojs/components'
import { useState, useEffect, useMemo } from 'react'
import Taro from '@tarojs/taro'
import Icon from '@/components/Icon'
import api, { EventBrief } from '@/services/api'
import { getAllProvinces, getCitiesByProvince } from '@/utils/regions'
import './index.scss'

// 比赛类型（报名项目）：1全马 2半马 3欢乐跑
const RACE_TYPE_OPTIONS = [
  { value: 1, label: '全马' },
  { value: 2, label: '半马' },
  { value: 3, label: '欢乐跑' }
]

// 赛事等级：0未设置 1白金标 2金标 3精英标 4标牌 5田协
const LEVEL_OPTIONS = [
  { value: 0, label: '不填' },
  { value: 1, label: '白金标' },
  { value: 2, label: '金标' },
  { value: 3, label: '精英标' },
  { value: 4, label: '标牌' },
  { value: 5, label: '田协' }
]

// 报名/缴费/中签选项
const REG_OPTIONS = [
  { value: 0, label: '未报名' },
  { value: 1, label: '已报名' }
]
const PAY_OPTIONS = [
  { value: 0, label: '未缴费' },
  { value: 1, label: '已缴费' }
]
const LOTTERY_OPTIONS = [
  { value: 0, label: '未中签' },
  { value: 1, label: '已中签' },
  { value: 2, label: '抽签中' }
]

interface ChipGroupProps {
  options: { value: number; label: string }[]
  value: number
  onChange: (v: number) => void
  disabled?: boolean
}
function ChipGroup({ options, value, onChange, disabled }: ChipGroupProps) {
  return (
    <View className='chip-group'>
      {options.map((opt) => (
        <View
          key={opt.value}
          className={`chip ${value === opt.value ? 'active' : ''} ${disabled ? 'chip--disabled' : ''}`}
          onClick={() => !disabled && onChange(opt.value)}
        >
          <Text>{opt.label}</Text>
        </View>
      ))}
    </View>
  )
}

/** 取 ISO 日期字符串的 YYYY-MM-DD 部分 */
function toDateInput(v?: string | null): string {
  if (!v) return ''
  const m = v.match(/^(\d{4}-\d{2}-\d{2})/)
  return m ? m[1] : ''
}

const PROVINCE_LIST = getAllProvinces()

export default function AddRace() {
  const [eventName, setEventName] = useState('')
  const [selectedEvent, setSelectedEvent] = useState<EventBrief | null>(null)
  const [suggestions, setSuggestions] = useState<EventBrief[]>([])
  const [searching, setSearching] = useState(false)

  const [startTime, setStartTime] = useState('')
  const [province, setProvince] = useState('')
  const [city, setCity] = useState('')
  const [eventLevel, setEventLevel] = useState(0)

  const [regStatus, setRegStatus] = useState(0)
  const [payStatus, setPayStatus] = useState(0)
  const [lotteryStatus, setLotteryStatus] = useState(0)
  const [raceType, setRaceType] = useState(1)
  const [fee, setFee] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // 省市级联数据
  const provinceIdx = useMemo(() => {
    return Math.max(0, PROVINCE_LIST.findIndex((p) => p.name === province || p.matchName === province))
  }, [province])

  const cityOptions = useMemo(() => {
    const prov = PROVINCE_LIST[provinceIdx]
    if (!prov) return []
    return getCitiesByProvince(prov.provinceKey)
  }, [provinceIdx])

  const cityIdx = useMemo(() => {
    return Math.max(0, cityOptions.findIndex((c) => c.name === city || c.matchName === city))
  }, [cityOptions, city])

  // 搜索赛事名称（debounce 300ms）
  useEffect(() => {
    if (selectedEvent) {
      setSuggestions([])
      return
    }
    const kw = eventName.trim()
    if (!kw) {
      setSuggestions([])
      return
    }
    setSearching(true)
    const timer = setTimeout(() => {
      api.getEvents({ keyword: kw, page_size: 10 })
        .then((res) => {
          setSuggestions(res.items || [])
        })
        .catch((e) => {
          console.warn('[AddRace] search failed', e)
          setSuggestions([])
        })
        .finally(() => setSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [eventName, selectedEvent])

  const handleNameInput = (val: string) => {
    setEventName(val)
    if (selectedEvent) {
      // 用户修改名称时视为重新搜索，清除已选
      setSelectedEvent(null)
      setStartTime('')
      setProvince('')
      setCity('')
      setEventLevel(0)
    }
  }

  const selectEvent = (ev: EventBrief) => {
    setSelectedEvent(ev)
    setEventName(ev.event_name)
    setSuggestions([])
    setStartTime(toDateInput(ev.start_time))
    setProvince(ev.province || '')
    setCity(ev.city || ev.location || '')
    setEventLevel(ev.event_level || 0)
  }

  const clearSearch = () => {
    setEventName('')
    setSelectedEvent(null)
    setSuggestions([])
    setStartTime('')
    setProvince('')
    setCity('')
    setEventLevel(0)
  }

  const handleDateChange = (e: any) => {
    if (selectedEvent) return
    setStartTime(e?.detail?.value || '')
  }

  const handleLocationColumnChange = (e: any) => {
    const { column, value: idx } = e.detail
    if (column === 0) {
      const prov = PROVINCE_LIST[idx]
      if (prov) {
        setProvince(prov.name)
        const cities = getCitiesByProvince(prov.provinceKey)
        setCity(cities[0]?.name || '')
      }
    }
  }

  const handleLocationChange = (e: any) => {
    const [pIdx, cIdx] = e.detail.value || [0, 0]
    const prov = PROVINCE_LIST[pIdx]
    const cities = prov ? getCitiesByProvince(prov.provinceKey) : []
    const cit = cities[cIdx]
    if (prov && cit) {
      setProvince(prov.name)
      setCity(cit.name)
    }
  }

  const displayLocation = useMemo(() => {
    if (selectedEvent) {
      const parts = [selectedEvent.province, selectedEvent.city || selectedEvent.location].filter(Boolean)
      return parts.join(' ') || '暂无地点'
    }
    if (province && city) return `${province} ${city}`
    return '请选择比赛地点'
  }, [selectedEvent, province, city])

  const handleSubmit = async () => {
    const name = eventName.trim()
    if (!name && !selectedEvent) {
      Taro.showToast({ title: '请填写赛事名称', icon: 'none' })
      return
    }
    if (!Taro.getStorageSync('token')) {
      Taro.showToast({ title: '请先登录', icon: 'none' })
      return
    }

    setSubmitting(true)
    try {
      const payload: Record<string, any> = {
        registration_status: regStatus,
        payment_status: payStatus,
        lottery_status: lotteryStatus,
        race_type: raceType,
        fee: parseFloat(fee) || 0
      }

      if (selectedEvent) {
        payload.event_id = selectedEvent.event_id
      } else {
        payload.event_name = name
        payload.start_time = startTime || undefined
        payload.province = province || undefined
        payload.city = city || undefined
        payload.event_level = eventLevel
      }

      await api.addRace(payload)
      Taro.showToast({ title: '添加成功', icon: 'success' })
      setTimeout(() => {
        Taro.navigateBack({ delta: 1 }).catch(() => {
          Taro.switchTab({ url: '/pages/follow/index' })
        })
      }, 800)
    } catch (e: any) {
      console.warn('[AddRace] submit failed', e)
      const msg = e?.message || '添加失败'
      Taro.showToast({ title: msg, icon: 'none' })
    } finally {
      setSubmitting(false)
    }
  }

  // 省市下拉选项
  const provinceNames = useMemo(() => PROVINCE_LIST.map((p) => p.name), [])
  const cityNames = useMemo(() => cityOptions.map((c) => c.name), [cityOptions])

  return (
    <View className='page-add-race'>
      {/* 搜索提示 */}
      <View className='search-tip'>
        <Icon name='search' size={24} color='#FF5C38' />
        <Text className='search-tip__text'>先根据赛事名称搜索，搜不到再添加自定义赛事</Text>
      </View>

      {/* 表单 */}
      <View className='form-wrap'>
        {/* 基本信息 */}
        <Text className='section-title'>基本信息</Text>
        <View className='form-section'>
          <View className='form-row form-row--column'>
            <Text className='form-label form-label--required'>赛事名称</Text>
            <View className='name-search-wrap'>
              <Input
                className='form-input form-input--name'
                placeholder='例如：南京马拉松'
                value={eventName}
                onInput={(e) => handleNameInput(e.detail.value)}
                maxlength={50}
              />
              {eventName ? (
                <View className='name-search-clear' onClick={clearSearch}>
                  <Icon name='x' size={24} color='#B9AAA0' />
                </View>
              ) : null}
            </View>

            {/* 搜索结果下拉 */}
            {suggestions.length > 0 && !selectedEvent && (
              <View className='suggest-dropdown'>
                {suggestions.map((ev) => (
                  <View
                    key={ev.event_id}
                    className='suggest-item'
                    onClick={() => selectEvent(ev)}
                  >
                    <View className='suggest-item__left'>
                      <Text className='suggest-item__name'>{ev.event_name}</Text>
                      <Text className='suggest-item__meta'>
                        {ev.start_date_label || ev.start_time || '日期待定'} · {ev.location || '地点待定'}
                      </Text>
                    </View>
                    {ev.event_level_label ? (
                      <Text className='suggest-item__level'>{ev.event_level_label}</Text>
                    ) : null}
                  </View>
                ))}
              </View>
            )}
            {searching && eventName && !selectedEvent && (
              <Text className='suggest-empty'>搜索中…</Text>
            )}
            {!searching && eventName && !selectedEvent && suggestions.length === 0 && (
              <Text className='suggest-empty'>未找到匹配赛事，将保存为自定义赛事</Text>
            )}
          </View>

          <View className='form-row'>
            <Text className='form-label form-label--required'>比赛日期</Text>
            <Picker
              className='form-picker'
              mode='date'
              value={startTime || ''}
              disabled={!!selectedEvent}
              onChange={handleDateChange}
            >
              <View className={`form-picker__display ${!startTime ? 'form-picker__display--placeholder' : ''} ${selectedEvent ? 'form-picker__display--disabled' : ''}`}>
                <Text>{startTime || '请选择比赛日期'}</Text>
                <Icon name='calendar-days' size={24} color={selectedEvent ? '#D9CFC6' : '#B9AAA0'} />
              </View>
            </Picker>
          </View>

          <View className='form-row'>
            <Text className='form-label form-label--required'>比赛地点</Text>
            <Picker
              className='form-picker'
              mode='multiSelector'
              range={[provinceNames, cityNames]}
              value={[provinceIdx, cityIdx]}
              disabled={!!selectedEvent}
              onColumnChange={handleLocationColumnChange}
              onChange={handleLocationChange}
            >
              <View className={`form-picker__display ${!province ? 'form-picker__display--placeholder' : ''} ${selectedEvent ? 'form-picker__display--disabled' : ''}`}>
                <Text>{displayLocation}</Text>
                <Icon name='chevron-down' size={24} color={selectedEvent ? '#D9CFC6' : '#B9AAA0'} />
              </View>
            </Picker>
          </View>

          <View className='form-row'>
            <Text className='form-label'>赛事等级</Text>
            <ChipGroup
              options={LEVEL_OPTIONS}
              value={eventLevel}
              onChange={setEventLevel}
              disabled={!!selectedEvent}
            />
          </View>
        </View>

        {/* 报名状态 */}
        <Text className='section-title'>报名状态</Text>
        <View className='form-section'>
          <View className='form-row'>
            <Text className='form-label'>报名状态</Text>
            <ChipGroup options={REG_OPTIONS} value={regStatus} onChange={setRegStatus} />
          </View>

          <View className='form-row'>
            <Text className='form-label'>比赛类型</Text>
            <ChipGroup options={RACE_TYPE_OPTIONS} value={raceType} onChange={setRaceType} />
          </View>

          <View className='form-row'>
            <Text className='form-label'>缴费状态</Text>
            <ChipGroup options={PAY_OPTIONS} value={payStatus} onChange={setPayStatus} />
          </View>

          <View className='form-row'>
            <Text className='form-label'>中签状态</Text>
            <ChipGroup options={LOTTERY_OPTIONS} value={lotteryStatus} onChange={setLotteryStatus} />
          </View>

          <View className='form-row'>
            <Text className='form-label'>报名费用</Text>
            <View className='fee-wrap'>
              <Text className='fee-unit'>¥</Text>
              <Input
                className='form-input form-input--fee'
                type='digit'
                placeholder='0'
                value={fee}
                onInput={(e) => setFee(e.detail.value)}
                maxlength={8}
              />
            </View>
          </View>
        </View>
      </View>

      {/* 提交按钮 */}
      <View className='sticky-bottom-bar'>
        <View className={`submit-btn ${submitting ? 'submit-btn--disabled' : ''}`} onClick={submitting ? undefined : handleSubmit}>
          <Icon name='check' size={32} color='#FFFFFF' />
          <Text>保存并添加到关注</Text>
        </View>
      </View>
    </View>
  )
}
