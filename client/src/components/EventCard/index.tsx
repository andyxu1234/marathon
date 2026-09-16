import { View, Text } from '@tarojs/components'
import Icon from '@/components/Icon'

import type { EventBrief } from '@/services/api'
import './index.scss'

interface EventCardProps {
  event: EventBrief
  onClick?: (id: number) => void
  /** 入场动画的序号，用于列表 stagger（从 0 开始） */
  index?: number
}

// 赛事级别 → 文案 + 色系（金 / 银 / 铜，全部走暖调）
function levelMeta(level: number): { label: string; cls: string } {
  switch (level) {
    case 1:
      return { label: '白金标', cls: 'lvl--platinum' }
    case 2:
      return { label: '金标', cls: 'lvl--gold' }
    case 3:
      return { label: '精英标', cls: 'lvl--silver' }
    case 4:
      return { label: '标牌', cls: 'lvl--bronze' }
    case 5:
      return { label: '田协', cls: 'lvl--bronze' }
    default:
      return { label: '标牌', cls: 'lvl--bronze' }
  }
}

// 赛事状态 → 文案 + 语义色 key
function statusMeta(status: number): { label: string; key: string } {
  switch (status) {
    case 2:
      return { label: '报名中', key: 'open' }
    case 1:
      return { label: '即将开跑', key: 'soon' }
    case 3:
      return { label: '报名结束', key: 'done' }
    case 4:
      return { label: '比赛中', key: 'live' }
    case 5:
      return { label: '已结束', key: 'done' }
    default:
      return { label: '即将开跑', key: 'soon' }
  }
}

// 省份全称 → 简称（车牌/省份缩写），用于头像左上角"印章"角标
const PROVINCE_ABBR: Record<string, string> = {
  '北京市': '京', '上海': '沪', '上海市': '沪', '天津市': '津', '天津': '津',
  '重庆市': '渝', '重庆': '渝', '广东': '粤', '广东省': '粤', '湖南': '湘',
  '湖南省': '湘', '湖北': '鄂', '湖北省': '鄂', '广西': '桂', '广西壮族自治区': '桂',
  '海南': '琼', '海南省': '琼', '四川': '川', '四川省': '川', '贵州': '黔',
  '贵州省': '黔', '云南': '滇', '云南省': '滇', '西藏': '藏', '西藏自治区': '藏',
  '陕西': '陕', '陕西省': '陕', '甘肃': '甘', '甘肃省': '甘', '青海': '青',
  '青海省': '青', '宁夏': '宁', '宁夏回族自治区': '宁', '新疆': '新',
  '新疆维吾尔自治区': '新', '内蒙古': '蒙', '内蒙古自治区': '蒙', '台湾': '台',
  '台湾省': '台', '香港': '港', '香港特别行政区': '港', '澳门': '澳',
  '澳门特别行政区': '澳', '河北': '冀', '河北省': '冀', '山西': '晋', '山西省': '晋',
  '吉林': '吉', '吉林省': '吉', '辽宁': '辽', '辽宁省': '辽', '江苏': '苏',
  '江苏省': '苏', '浙江': '浙', '浙江省': '浙', '安徽': '皖', '安徽省': '皖',
  '福建': '闽', '福建省': '闽', '江西': '赣', '江西省': '赣', '山东': '鲁',
  '山东省': '鲁', '河南': '豫', '河南省': '豫',
}

// 去掉"市/省/自治区"等后缀，得到城市核心名（"郴州市"→"郴州"）
const stripSuffix = (s: string) =>
  s.replace(/(特别行政区|壮族自治区|回族自治区|维吾尔自治区|自治区|省|市)$/, '')

// 省份全称 → 简称查找
const provinceAbbr = (raw?: string): string => {
  if (!raw) return ''
  if (PROVINCE_ABBR[raw]) return PROVINCE_ABBR[raw]
  const trimmed = raw.replace(/(省|市|自治区|特别行政区)$/, '')
  return PROVINCE_ABBR[trimmed] || ''
}

// 城市名 → 稳定的 0-3 索引，对应 4 个暖调渐变
const PH_GRADIENTS = [
  'linear-gradient(135deg, #FF8156 0%, #FF5C38 52%, #EE4520 100%)', // 珊瑚红（主）
  'linear-gradient(135deg, #FFB872 0%, #FF8A3D 52%, #F36B1E 100%)', // 日落橙
  'linear-gradient(135deg, #FF6F61 0%, #E84855 52%, #C72B3E 100%)', // 深玫红
  'linear-gradient(135deg, #FFAA73 0%, #FF7E47 52%, #E95724 100%)', // 琥珀橙
]

// 字符串哈希，保证同一城市每次得到同一渐变
const cityHash = (s: string): number => {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

// 赛事类型角标已移除（与"全程/半程"等筛选器信息重复）

export default function EventCard({ event, onClick, index = 0 }: EventCardProps) {
  const lvl = levelMeta(event.event_level)
  const st = statusMeta(event.event_status)

  const handleClick = () => onClick?.(event.event_id)

  // 首屏前 10 张播入场动画（stagger），第 11 张起（即触底加载的下一页新卡）直接静态显示，
  // 避免 append 时整批新卡同时跑动画造成滚动卡顿。
  const enableAnim = index < 10

  const cityCore = stripSuffix((event.city || '').trim())
  const phText = cityCore || (event.event_name || '马').trim().charAt(0) || '马'
  const phSize =
    phText.length <= 1 ? 'rc__ph--1' : phText.length === 2 ? 'rc__ph--2' : phText.length === 3 ? 'rc__ph--3' : 'rc__ph--4'
  const phAbbr = provinceAbbr(event.province)
  const phGradient = PH_GRADIENTS[cityHash(phText) % PH_GRADIENTS.length]

  return (
    <View
      className={`rc ${enableAnim ? 'rc--enter' : ''}`}
      hoverClass='rc--pressed'
      hoverStayTime={90}
      onClick={handleClick}
      style={enableAnim ? { animationDelay: `${Math.min(index, 10) * 55}ms` } : undefined}
    >
      <View className='rc__media'>
        {/* 统一使用省市文字头像（哈希分色渐变 + 斜向速度条纹 + 城市核心名 + 定位图标 + 左上角省份简称印章），
            不再使用 cover_image，保证全站视觉一致 */}
        <View
          className={`rc__ph ${phSize}`}
          style={{ background: phGradient }}
        >
          {phAbbr ? (
            <View className='rc__ph-abbr'>
              <Text className='rc__ph-abbr-txt'>{phAbbr}</Text>
            </View>
          ) : null}
          <Icon name='map-pin' size={phSize === 'rc__ph--1' ? 30 : 26} color='rgba(255,255,255,0.88)' />
          <Text className='rc__ph-text'>{phText}</Text>
        </View>
      </View>

      <View className='rc__body'>
        <Text className='rc__name clamp-2'>{event.event_name}</Text>

        <View className='rc__meta'>
          <View className='rc__meta-row'>
            <Icon name='calendar' size={24} color='#A3968D' />
            <Text className='rc__meta-txt ellipsis'>{event.start_date_label || '待定'}</Text>
          </View>
          <View className='rc__meta-row'>
            <Icon name='map-pin' size={24} color='#A3968D' />
            <Text className='rc__meta-txt ellipsis'>{event.location || event.city || '待定'}</Text>
          </View>
        </View>

        <View className='rc__foot'>
          <View className={`rc__status rc__status--${st.key}`}>
            {st.key === 'live' ? <View className='rc__dot' /> : null}
            <Text className='rc__status-txt'>{st.label}</Text>
          </View>
          <Text className={`rc__lvl ${lvl.cls}`}>{lvl.label}</Text>
          <View className='rc__spacer' />
          {event.registration_fee != null ? (
            <Text className='rc__price num'>¥{event.registration_fee}</Text>
          ) : (
            <View className='rc__fav'>
              <Icon name='heart' size={22} color='#C9B9AC' />
              <Text className='rc__fav-txt num'>{event.favorite_count || 0}</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  )
}
