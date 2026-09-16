import { View } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

// Lucide 风格的 line icon，24x24 viewBox，stroke=currentColor
// 用 base64 SVG 作为 background-image，H5 + 小程序均可渲染
const ICONS: Record<string, string> = {
  home: '<path d="M3 9.5L12 3l9 6.5"/><path d="M5 10v11h14V10"/><path d="M9 21v-7h6v7"/>',
  heart: '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  'map-pin': '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
  'chevron-right': '<path d="M9 18l6-6-6-6"/>',
  'chevron-left': '<path d="M15 18l-6-6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>',
  star: '<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  trophy: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2z"/>',
  wallet: '<path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M18 12a2 2 0 0 0 0 4h4v-4z"/>',
  settings: '<path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  'log-out': '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>',
  filter: '<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>',
  'trending-up': '<path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
  award: '<circle cx="12" cy="8" r="7"/><path d="M8.21 13.89L7 23l5-3 5 3-1.21-9.12"/>',
  phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
  mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="M22 6l-10 7L2 6"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.59 13.51l6.83 3.98M15.41 6.51L8.59 10.49"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  'x': '<path d="M18 6L6 18M6 6l12 12"/>',
  edit: '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>',
  'plus-circle': '<circle cx="12" cy="12" r="10"/><path d="M12 8v8M8 12h8"/>',
  'check-circle': '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/>',
  'alert-circle': '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  'calendar-days': '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"/>',
  medal: '<path d="M7.21 15a2.5 2.5 0 0 1 0-3l4.79-9 4.79 9a2.5 2.5 0 0 1 0 3"/><path d="M20.79 15a2.5 2.5 0 0 1 0 3l-4.79 9-4.79-9a2.5 2.5 0 0 1 0-3"/><circle cx="12" cy="17" r="4"/>',
  bell: '<path d="M10.268 11a2 2 0 0 0-3.736 0M6 9V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v5a6 6 0 0 1-6 6 6 6 0 0 1-6-6z"/><path d="M4 8a8 8 0 0 0 16 0M10.268 19a2 2 0 0 0 4 0"/>',
  footprints: '<path d="M4 16v-2.38C4 11.5 2.97 10.5 3 8c.03-2.5 1-3 1-3"/><path d="M14 18v-2.38c0-2.12 1.03-3.12 1-5.62-.03-2.5-1-3-1-3"/>',
  'help-circle': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
  'share-2': '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.59 13.51l6.83 3.98M15.41 6.51L8.59 10.49"/>',
  'circle-dot': '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="1"/>',
  minus: '<path d="M5 12h14"/>',
  circle: '<circle cx="12" cy="12" r="10"/>',
  'chevron-down': '<path d="M6 9l6 6 6-6"/>',
  'chevron-up': '<path d="M18 15l-6-6-6 6"/>',
  camera: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/>',
  'trash-2': '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>'
}

// 跨端 base64：H5 用 btoa（浏览器原生），weapp 用 Taro.arrayBufferToBase64（Taro 提供，H5/weapp 均实现）。
// 避免用 Node 的 Buffer（小程序端没有 Buffer 全局对象）。
function utf8ToBase64(str: string): string {
  if (typeof btoa !== 'undefined') {
    // H5: unescape(encodeURIComponent(...)) 是把 UTF-16 DOMString 编码成 UTF-8 binary string 的经典写法
    return btoa(unescape(encodeURIComponent(str)))
  }
  // 小程序（H5 也支持 Taro.arrayBufferToBase64，留作兜底）
  // encodeURIComponent -> 把 %XX 拼成 Uint8Array -> Taro.arrayBufferToBase64
  const percent = encodeURIComponent(str)
  const bytes: number[] = []
  for (let i = 0; i < percent.length; i++) {
    if (percent[i] === '%') {
      bytes.push(parseInt(percent.substr(i + 1, 2), 16))
      i += 2
    } else {
      bytes.push(percent.charCodeAt(i))
    }
  }
  const uint8 = new Uint8Array(bytes)
  const buffer = uint8.buffer.slice(uint8.byteOffset, uint8.byteOffset + uint8.byteLength) as ArrayBuffer
  return Taro.arrayBufferToBase64(buffer)
}

function toSvgDataUri(pathStr: string, color: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${pathStr}</svg>`
  return `data:image/svg+xml;base64,${utf8ToBase64(svg)}`
}

interface IconProps {
  name: keyof typeof ICONS | string
  size?: number
  color?: string
  className?: string
}

// 缺失图标只告警一次，避免列表渲染时刷屏
const warnedMissing = new Set<string>()

export default function Icon({ name, size = 40, color = '#A3968D', className = '' }: IconProps) {
  let path = ICONS[name]
  if (!path) {
    if (process.env.NODE_ENV !== 'production' && !warnedMissing.has(name)) {
      warnedMissing.add(name)
      console.warn(
        `[Icon] 图标 "${name}" 未在 ICONS 表中定义，已降级渲染为 chevron-right（一个箭头）。` +
          `请在 client/src/components/Icon/index.tsx 的 ICONS 中补充该图标的 SVG path。`
      )
    }
    path = ICONS['chevron-right']
  }
  const uri = toSvgDataUri(path, color)
  return (
    <View
      className={`icon ${className}`}
      style={{
        width: `${size}rpx`,
        height: `${size}rpx`,
        backgroundImage: `url("${uri}")`,
        backgroundSize: 'contain',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center',
        flexShrink: 0
      }}
    />
  )
}
