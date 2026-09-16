import { View, Text } from '@tarojs/components'
import Icon from '@/components/Icon'
import './index.scss'

interface EmptyProps {
  text?: string
  icon?: string
  /** 副文案：给一句有用的引导，比干巴巴的"暂无数据"强 */
  hint?: string
}

export default function Empty({
  text = '暂无数据',
  icon = 'search',
  hint = ''
}: EmptyProps) {
  return (
    <View className='ep'>
      <View className='ep__art'>
        <View className='ep__ring' />
        <View className='ep__core'>
          <Icon name={icon} size={60} color='#FF8156' />
        </View>
      </View>
      <Text className='ep__text'>{text}</Text>
      {hint ? <Text className='ep__hint'>{hint}</Text> : null}
    </View>
  )
}
