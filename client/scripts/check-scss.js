/* SCSS 语法自检：模拟 Taro 的 sass.resource 注入，把 variables.scss 拼在每个 scss 前面编译。
   用途：改完样式后先跑一遍，避免把错误攒到 npm run 阶段才发现。
   用法：node scripts/check-scss.js  （在 client 目录下） */
const fs = require('fs')
const path = require('path')
const sass = require('sass')

const SRC = path.resolve(__dirname, '../src')
const STYLES = path.join(SRC, 'styles')
const vars = fs.readFileSync(path.join(STYLES, 'variables.scss'), 'utf8')

function walk(dir, out = []) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f)
    const st = fs.statSync(p)
    if (st.isDirectory()) walk(p, out)
    else if (f.endsWith('.scss')) out.push(p)
  }
  return out
}

const files = walk(SRC)
let fail = 0
for (const f of files) {
  // variables.scss 自身单独编译
  const src = f.endsWith('variables.scss') ? '' : vars
  try {
    sass.compileString(src + '\n' + fs.readFileSync(f, 'utf8'), {
      // styles/ 必须加进来：global.scss 里 @import './variables.scss' 依赖此路径
      loadPaths: [SRC, STYLES],
      silenceDeprecations: ['import'],
      style: 'expanded'
    })
    console.log('  ok   ' + path.relative(SRC, f))
  } catch (e) {
    fail++
    console.log('  FAIL ' + path.relative(SRC, f))
    console.log('       ' + String(e.message).split('\n').slice(0, 4).join('\n       '))
  }
}
console.log(fail === 0 ? `\nAll ${files.length} scss files compiled.` : `\n${fail} file(s) failed.`)
process.exit(fail === 0 ? 0 : 1)
