import { merge } from 'webpack-merge'
import baseConfig from './index'

export default merge({}, baseConfig, {
  mini: {},
  h5: {
    devServer: {
      port: 10086
    }
  }
})
