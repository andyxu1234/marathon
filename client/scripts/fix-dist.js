/**
 * Taro 构建产物配置文件修复脚本（微信 + 抖音通用）。
 *
 * 问题：
 *   Taro 构建时写入 dist 的 project.config.json 往往是空对象 {}（缺少 appid），
 *   开发者工具读它就会报「不合法的 AppID」或「解析 project.config.json 失败」。
 *
 * 修复：
 *   dist/ 里同时产出 project.config.json（开发者工具实际读取的文件）
 *   和 project.tt.json（保留一份便于对照 / 旧版工具），内容都来自项目根
 *   对应平台的配置（微信 project.config.json / 抖音 project.tt.json）。
 *
 *   注意：两个文件内容是一模一样的。抖音开发者工具读 project.config.json，
 *   若该文件缺失会直接报 ENOENT；若为空 {} 会报 AppID 不合法。所以必须保证
 *   它存在且带正确 appid。
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
  // 抖音：把 project.tt.json 的内容写入 dist/project.config.json
  // （开发者工具实际读这个文件名），同时保留一份 project.tt.json 便于对照。
  //
  // ⚠️ 两个坑：
  //   1. 若 dist/project.config.json 缺失 → 工具报 ENOENT 解析失败
  //   2. 若它是空对象 {} → 工具报「不合法的 AppID」
  const src = path.join(rootDir, 'project.tt.json')
  const dstConfig = path.join(distDir, 'project.config.json')
  const dstTt = path.join(distDir, 'project.tt.json')

  if (!fs.existsSync(src)) {
    console.error('[fix-dist] ✗ 根目录 project.tt.json 不存在')
    process.exit(1)
  }

  let cfg
  try {
    cfg = JSON.parse(fs.readFileSync(src, 'utf8'))
  } catch (e) {
    console.error('[fix-dist] ✗ 解析 client/project.tt.json 失败:', e.message)
    process.exit(1)
  }

  if (!cfg.appid) {
    console.error('[fix-dist] ✗ client/project.tt.json 里 appid 为空，请填入真实抖音 AppID')
    process.exit(1)
  }

  const content = JSON.stringify(cfg, null, 2) + '\n'
  fs.writeFileSync(dstConfig, content, 'utf8')
  fs.writeFileSync(dstTt, content, 'utf8')

  console.log('[fix-dist] ✓ dist/project.config.json 已生成（抖音，开发者工具实际读取）')
  console.log('[fix-dist] ✓ dist/project.tt.json 已生成（同内容，便于对照）')
  console.log(`[fix-dist] ✓ appid = ${cfg.appid}`)

} else {
  console.error('用法：node scripts/fix-dist.js [weapp|tt]')
  process.exit(1)
}
