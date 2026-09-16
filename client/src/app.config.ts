export default defineAppConfig({
  // 去掉 lazyCodeLoading: 'requiredComponents'：Taro 4.x 把所有自定义组件合并到 comp 占位，
  // 与微信"按需注入组件"机制不完全兼容，运行时递归组件树会偶发 wx://not-found。
  // 去掉后所有组件随 app.js 启动加载，对启动耗时影响可忽略（comp.js ~500B 已合并）。
  pages: [
    'pages/home/index',
    'pages/ranking/index',
    'pages/follow/index',
    'pages/mine/index',
    'pages/race-detail/index',
    'pages/add-race/index'
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#FFF8F3',
    navigationBarTitleText: '马拉松赛事',
    navigationBarTextStyle: 'black',
    backgroundColor: '#FFF8F3'
  },
  // 注意：不使用 custom: true，改用原生 tabBar 管页面切换，
  // 然后通过 Taro.hideTabBar() 隐藏原生视觉，自绘 TabBar 组件负责展示。
  // 这样可以避免 custom-tab-bar + 页面 TabBar 双渲染导致的重复/错位问题。
  tabBar: {
    color: '#A3968D',
    selectedColor: '#FF5C38',
    backgroundColor: '#FFFFFF',
    borderStyle: 'white',
    list: [
      { pagePath: 'pages/home/index', text: '首页' },
      { pagePath: 'pages/ranking/index', text: '排行' },
      { pagePath: 'pages/follow/index', text: '关注' },
      { pagePath: 'pages/mine/index', text: '我的' }
    ]
  }
})
