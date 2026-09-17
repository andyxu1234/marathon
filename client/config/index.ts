import path from 'path'
import { defineConfig } from '@tarojs/cli'
import { Compiler } from 'webpack'

/**
 * 在 webpack 的 environment 钩子中（此时 compiler.options 已合并完毕），遍历
 * compiler.options.module.rules 上所有挂了 sass-loader 的 use 对象，
 * 把 'import' 追加到 options.sassOptions.silenceDeprecations 里。
 *
 * 为什么不直接在 Taro config 里设？
 *   - Taro 的 sass.* 字段只接受白名单键（resource/data/等），sassOptions / silenceDeprecations
 *     不被识别，传了也会被丢；
 *   - webpack-chain 里 Taro 生成的 rule/use 命名不稳定，rule.uses.store 读取为空。
 * 直接在运行时遍历 compiler.options.module.rules 是最稳的方式，H5/小程序两边都生效。
 */
class SassSilenceImportDeprecationPlugin {
  apply(compiler: Compiler) {
    compiler.hooks.environment.tap('SassSilenceImportDeprecationPlugin', () => {
      const rules: any[] = (compiler.options as any).module?.rules || []
      const walk = (list: any[]) => {
        list.forEach((r) => {
          if (!r) return
          if (Array.isArray(r.oneOf)) walk(r.oneOf)
          if (Array.isArray(r.rules)) walk(r.rules)
          const uses: any[] = Array.isArray(r.use) ? r.use : (r.use ? [r.use] : [])
          uses.forEach((u) => {
            if (!u || typeof u !== 'object') return
            const loader = typeof u.loader === 'string' ? u.loader : ''
            if (!loader.includes('sass-loader')) return
            const cur: string[] = Array.isArray(u.options?.sassOptions?.silenceDeprecations)
              ? [...u.options.sassOptions.silenceDeprecations]
              : []
            if (!cur.includes('import')) cur.push('import')
            u.options = {
              ...(u.options || {}),
              sassOptions: {
                ...((u.options && u.options.sassOptions) || {}),
                silenceDeprecations: cur
              }
            }
          })
          // 兜底：r.loader / r.options 扁平形式
          const directLoader = typeof r.loader === 'string' ? r.loader : ''
          if (directLoader.includes('sass-loader')) {
            const cur: string[] = Array.isArray(r.options?.sassOptions?.silenceDeprecations)
              ? [...r.options.sassOptions.silenceDeprecations]
              : []
            if (!cur.includes('import')) cur.push('import')
            r.options = {
              ...(r.options || {}),
              sassOptions: {
                ...((r.options && r.options.sassOptions) || {}),
                silenceDeprecations: cur
              }
            }
          }
        })
      }
      walk(rules)
    })
  }
}

// 在 sass-loader 被 require() 之前就把 Dart-Sass 自带的环境变量设好，
// 彻底消除 @import deprecation warning 的源头（Dart-Sass 官方支持此 env var）。
process.env.SASS_SILENCE_DEPRECATIONS = 'import'

export default defineConfig(async (merge) => {
  const baseConfig = {
    projectName: 'marathon-mini-program',
    date: '2026-8-27',
    designWidth: 750,
    deviceRatio: { 640: 2.34 / 2, 750: 1, 828: 1.81 / 2, 375: 2 / 1 },
    sourceRoot: 'src',
    outputRoot: 'dist',
    alias: {
      '@': path.resolve(process.cwd(), 'src')
    },
    plugins: ['@tarojs/plugin-framework-react'],
    // TARO_APP_* 环境变量编译期注入：
    //   - 小程序没有 process 全局对象，必须通过 defineConstants 在编译时替换为字面量，
    //     避免运行时 "process is not defined"。
    //   - TARO_APP_API_BASE：显式覆盖 API 地址，用于真机调试（手机无法访问 localhost）。
    defineConstants: {
      'process.env.TARO_APP_API_BASE': JSON.stringify(process.env.TARO_APP_API_BASE || ''),
      // Taro CLI 在 build 时会带 --mode production，但不会写进 process.env，
      // 因此这里以命令行是否含 --watch 来判定：watch = 开发，否则 = 生产。
      'process.env.NODE_ENV': JSON.stringify(
        process.argv.includes('--watch')
          ? 'development'
          : process.env.NODE_ENV || 'production'
      )
    },
    copy: { patterns: [], options: {} },
    framework: 'react',
    compiler: { type: 'webpack5', prebundle: { enable: false } },
    cache: { enable: false },
    // 全局 SCSS 变量自动注入每个文件（Taro 会合并到 sass-loader 的 additionalData）
    sass: { resource: ['src/styles/variables.scss'] },
    mini: {
      webpackChain(chain: any) {
        chain.plugin('sass-silence-import-deprecation')
          .use(SassSilenceImportDeprecationPlugin, [])
      },
      postcss: {
        pxtransform: { enable: true, config: {} }
      }
    },
    h5: {
      publicPath: '/',
      staticDirectory: 'static',
      output: {
        filename: 'js/[name].[hash:8].js',
        chunkFilename: 'js/[name].[chunkhash:8].js'
      },
      miniCssExtractPluginOption: {
        ignoreOrder: true,
        filename: 'css/[name].[hash].css'
      },
      postcss: { autoprefixer: { enable: true } },
      webpackChain(chain: any) {
        chain.plugin('sass-silence-import-deprecation')
          .use(SassSilenceImportDeprecationPlugin, [])
      },
      devServer: {
        // 端口支持 PORT 环境变量覆盖，方便一台机同时起多个 dev server：
        //   $env:PORT=10088; npm run dev:h5
        port: Number(process.env.PORT || 10086),
        host: '0.0.0.0',
        open: false,
        https: false,
        client: {
          // webpack-dev-server 默认 overlay 连 warnings 也全屏遮罩，
          // 手机上会被红色半透明层挡住所有内容（其实下面渲染正常）。
          // 只在真实编译错误时弹遮罩，warnings（例如 Sass 弃用提示）静默。
          overlay: {
            errors: true,
            warnings: false,
            runtimeErrors: true
          },
          logging: 'warn'
        }
      }
    }
  }
  return baseConfig
})
