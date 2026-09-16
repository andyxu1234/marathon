/// <reference types="@tarojs/taro" />

declare module '*.png';
declare module '*.jpg';
declare module '*.jpeg';
declare module '*.svg';
declare module '*.scss';
declare module '*.css';

declare namespace NodeJS {
  interface ProcessEnv {
    /**
     * 当前编译类型：
     * - weapp  微信小程序
     * - tt     抖音 / 字节跳动小程序（一个 appid 自动覆盖抖音 + 抖音极速版
     *          + 今日头条 + 今日头条极速版 4 个宿主端，无需再分 toutiao 分支）
     * - h5     Web 端
     * - swan   百度小程序
     * - alipay 支付宝小程序
     */
    TARO_ENV: 'weapp' | 'tt' | 'h5' | 'swan' | 'alipay'
    NODE_ENV: 'development' | 'production'
  }
}
