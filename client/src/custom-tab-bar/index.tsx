import { View } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import { useState } from 'react'
import TabBar from '@/components/TabBar'
import { isMiniProgram } from '@/utils/platform'
import './index.scss'

// 微信小程序自定义 tabBar 组件（custom: true 时由原生加载）
export default function CustomTabBar() {
  const [selected, setSelected] = useState(0)

  useDidShow(() => {
    // 仅小程序端需要强制隐藏原生 tabBar（H5 端也无原生 tabBar 调用）
    if (isMiniProgram) {
      try {
        Taro.hideTabBar({ animation: false })
      } catch (_) { /* ignore */ }
    }

    const pages = Taro.getCurrentPages()
    const page = pages[pages.length - 1]
    const route = page ? page.route : ''
    const keyMap: Record<string, number> = {
      'pages/home/index': 0,
      'pages/follow/index': 1,
      'pages/mine/index': 2
    }
    setSelected(keyMap[route] ?? 0)
  })

  const currentArr: Array<'home' | 'follow' | 'mine'> = ['home', 'follow', 'mine']
  return (
    <View className='custom-tab-bar-wrapper'>
      <TabBar current={currentArr[selected]} />
    </View>
  )
}
