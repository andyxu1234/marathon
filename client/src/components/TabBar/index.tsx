import { View, Text } from '@tarojs/components'
import Taro, { useDidShow } from '@tarojs/taro'
import Icon from '@/components/Icon'
import './index.scss'

interface TabItem {
  key: string
  text: string
  path: string
  icon: string
}

const TABS: TabItem[] = [
  { key: 'home', text: '首页', path: '/pages/home/index', icon: 'home' },
  { key: 'ranking', text: '排行', path: '/pages/ranking/index', icon: 'trending-up' },
  { key: 'follow', text: '关注', path: '/pages/follow/index', icon: 'heart' },
  { key: 'mine', text: '我的', path: '/pages/mine/index', icon: 'user' }
]

interface TabBarProps {
  current: 'home' | 'ranking' | 'follow' | 'mine'
}

export default function TabBar({ current }: TabBarProps) {
  // 每次页面显示时都强制隐藏原生 tabBar（某些基础库版本会自动恢复原生 tabBar）
  useDidShow(() => {
    try {
      Taro.hideTabBar({ animation: false })
    } catch (_) { /* ignore */ }
  })

  const handleSwitch = (path: string, isActive: boolean) => {
    if (isActive) return
    Taro.switchTab({ url: path })
  }

  return (
    <View className='tb'>
      {TABS.map((tab) => {
        const isActive = tab.key === current
        return (
          <View
            key={tab.key}
            className={`tb__item ${isActive ? 'tb__item--active' : ''}`}
            hoverClass='tb__item--pressed'
            hoverStayTime={80}
            onClick={() => handleSwitch(tab.path, isActive)}
          >
            <View className='tb__badge'>
              <Icon name={tab.icon} size={42} color={isActive ? '#FFFFFF' : '#B9AAA0'} />
              <Text className='tb__text'>{tab.text}</Text>
            </View>
          </View>
        )
      })}
    </View>
  )
}
