/**
 * Taro 构建产物配置文件修复脚本（微信 + 抖音通用）。
 *
 * 问题：
 *   1. Taro build:weapp 不会把项目根的 project.config.json 复制到 dist，
 *      直接用微信开发者工具打开 dist/ 目录时找不到配置文件。
 *   2. Taro build:tt 会把 project.tt.json 重命名为 project.config.json
 *      放进 dist，但抖音开发者工具认 project.tt.json，否则按微信项目
 *      解析去找 .wxml（实际是 .ttml），导致"模拟器启动失败"。
 *
 * 修复：
 *   根据构建类型（WEAPP / TT），把项目根目录对应的配置文件
 *   复制到 dist，并清理另一端的配置文件，避免开发者工具误判。
 *
 * 用法：
 *   node scripts/fix-dist.js weapp   # 微信构建后
 *   node scripts/fix-dist.js tt      # 抖音构建后
 */
const fs = require('fs')
const path = require('path')

const target = (process.argv[2] || '').toLowerCase()
const distDir = path.resolve(__dirname, '..', 'dist')
const rootDir = path.resolve(__dirname, '..')

if (target === 'weapp') {
  // 微信：复制 project.config.json 到 dist，清理可能残留的 project.tt.json
  const src = path.join(rootDir, 'project.config.json')
  const dst = path.join(distDir, 'project.config.json')
  const cleanup = path.join(distDir, 'project.tt.json')

  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dst)
    console.log('[fix-dist] ✓ dist/project.config.json 已生成（微信）')
  } else {
    console.warn('[fix-dist] ⚠ 根目录 project.config.json 不存在')
  }
  if (fs.existsSync(cleanup)) fs.unlinkSync(cleanup)

} else if (target === 'tt') {
  // 抖音：复制 project.tt.json 到 dist，清理 project.config.json（Taro 可能自动生成的）
  const src = path.join(rootDir, 'project.tt.json')
  const dst = path.join(distDir, 'project.tt.json')
  const cleanup = path.join(distDir, 'project.config.json')

  if (fs.existsSync(src)) {
    fs.copyFileSync(src, dst)
    console.log('[fix-dist] ✓ dist/project.tt.json 已生成（抖音）')
  } else {
    console.warn('[fix-dist] ⚠ 根目录 project.tt.json 不存在')
  }
  if (fs.existsSync(cleanup)) fs.unlinkSync(cleanup)

} else {
  console.error('用法：node scripts/fix-dist.js [weapp|tt]')
  process.exit(1)
}
