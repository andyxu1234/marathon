/**
 * 平台判断常量集中出口。
 *
 * 设计意图：
 * - `process.env.TARO_ENV` 在 Taro 中是**编译期常量替换**，未命中分支会被
 *   webpack5 当死代码 tree-shake 掉，不存在跨端 API 误调用风险。
 * - 业务代码统一从这里 import `{ isMiniProgram, isWeapp, isDouyin, isH5 }`，
 *   不在业务文件里直接写 `process.env.TARO_ENV === 'weapp'`，便于平台差异
 *   点 grep 收敛与回归。
 *
 * 字节系说明：
 * - 抖音小程序本质是"字节跳动小程序"，一个 appid 一份代码自动覆盖抖音 /
 *   抖音极速版 / 今日头条 / 今日头条极速版 4 个宿主端，Taro 编译目标统一为
 *   `--type tt`，无需再分 douyin / toutiao 两套适配器。
 */

export const TARO_ENV = process.env.TARO_ENV as 'weapp' | 'tt' | 'h5'

/** 微信小程序（编译目标 weapp） */
export const isWeapp = TARO_ENV === 'weapp'

/** 抖音 / 字节跳动小程序（编译目标 tt，覆盖抖音 + 头条 4 个宿主端） */
export const isDouyin = TARO_ENV === 'tt'

/** 通用小程序（微信 + 抖音两端共性逻辑） */
export const isMiniProgram = isWeapp || isDouyin

/** H5 端 */
export const isH5 = TARO_ENV === 'h5'

/**
 * 当前小程序平台代号，用于后端登录接口分流：
 * - weapp → /users/login/wechat
 * - tt    → /users/login/douyin
 * 小程序之外的端返回 null。
 */
export const miniProgramPlatform: 'weapp' | 'tt' | null = isWeapp
  ? 'weapp'
  : isDouyin
    ? 'tt'
    : null
