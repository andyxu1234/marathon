# Marathon · 马拉松赛事追踪小程序

一款面向马拉松爱好者的赛事查询与个人追踪工具。支持浏览全国马拉松赛事、筛选报名状态、关注收藏、记录报名 / 缴费 / 中签信息、统计个人战绩。

技术架构参考 `world-cup-prediction` 项目，采用 **Taro 4 + React 18 + TypeScript** 前端 + **FastAPI + SQLAlchemy 2 async** 后端，一套代码同时覆盖微信小程序与 H5 多端。

> 🖥️ **在线介绍页**：<https://andyxu1234.github.io/marathon/>
> 源码在 [`docs/`](docs/)，由 GitHub Pages 直接托管，改完 push 即生效。

---

## 目录结构

```
marathon/
├── client/                     # 前端（Taro 4 · React 18 · TypeScript · Sass）
│   ├── src/
│   │   ├── pages/              # 5 个页面（home / follow / mine / race-detail / add-race）
│   │   ├── components/         # 共享组件（Icon / TabBar / EventCard / Empty）
│   │   ├── custom-tab-bar/     # 微信自定义 TabBar
│   │   ├── services/api.ts     # 统一 API 请求层
│   │   ├── stores/             # Zustand 状态管理（用户登录态）
│   │   └── styles/             # SCSS 变量 + 全局样式
│   ├── config/index.ts         # Taro 编译配置
│   └── package.json
│
├── server/                     # 后端（FastAPI · SQLAlchemy 2 async · Alembic）
│   ├── app/
│   │   ├── api/v1/             # 4 组路由：events / favorites / registrations / users
│   │   ├── models/             # 4 张表 ORM：event / user / favorite / registration
│   │   ├── schemas/            # Pydantic 2 请求 / 响应模型
│   │   ├── services/           # 业务逻辑层
│   │   ├── core/               # JWT 认证 · 微信登录 · 缓存
│   │   ├── utils/              # 枚举 label 映射 · 时间格式化
│   │   ├── config.py           # Pydantic Settings（.env 加载）
│   │   ├── database.py         # SQLAlchemy async engine + session
│   │   ├── deps.py             # FastAPI 依赖注入（DB / 当前用户）
│   │   └── main.py             # FastAPI 入口 + CORS + 生命周期
│   ├── alembic/                # 数据库迁移（含 0001 新增 registration_fee + mi_registration）
│   ├── .env.example            # 环境变量模板
│   └── requirements.txt
│
├── pages/                      # 设计稿 HTML（5 页）
│
└── docs/                       # GitHub Pages 介绍页（源站）
    ├── index.html              # 项目落地页（滚动动画 + 截图灯箱）
    ├── screenshot/             # 小程序界面截图
    ├── asset/                  # 架构图
    └── tech/                   # 技术方案文档
```

---

## 技术栈

### 前端
| 类别 | 选型 | 说明 |
|------|------|------|
| 跨端框架 | **Taro 4.1.11** | 一套代码编译到微信小程序 + H5 |
| UI 框架 | **React 18** | Hooks 风格组件 |
| 语言 | **TypeScript 5.4** | 类型安全 |
| 样式 | **Sass / SCSS** | 设计稿 token 注入为全局变量 |
| 状态管理 | **Zustand 4.5** | 轻量 store（用户登录态） |
| 请求 | Taro.request 封装 | 带重试 · 超时 · 自动鉴权头 |
| 路由 | Taro tabBar + navigator | 3 个 Tab 页 + 2 个独立页 |

### 后端
| 类别 | 选型 | 说明 |
|------|------|------|
| Web 框架 | **FastAPI 0.115** | 异步 · Pydantic 2 · 自动生成 OpenAPI |
| ASGI | **Uvicorn 0.30** | 支持标准模式（HMR / WatchFiles） |
| ORM | **SQLAlchemy 2.0.35 async** | declarative style + Mapped 类型标注 |
| 数据库驱动 | **aiomysql**（Windows）/ **asyncmy**（Linux）| config 根据平台自动切换 |
| 同步迁移 | **Alembic 1.13** | pymysql 同步连接 |
| 认证 | **JWT（python-jose）** | 微信静默登录 + 开发期密码登录 |
| 微信 SDK | **wechatpy 1.8** | code → openid 交换 |
| 配置 | **pydantic-settings 2.5** | 自动读取 `.env` |
| 日志 | **loguru** | 结构化日志 |
| 缓存 | **cachetools TTLCache** | 筛选项内存缓存 |

---

## 快速开始

### 前置条件
- Python 3.10+
- Node.js 18+
- MySQL 8.x（数据库名：`marathon`）

### 1. 后端启动

```bash
cd server

# (a) 创建虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# (b) 安装依赖
pip install -r requirements.txt

# (c) 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DB 连接信息 + 微信 AppID/Secret（小程序用）

# (d) 执行数据库迁移
alembic upgrade head

# (e) 启动服务（默认 8000 端口）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问：
- 健康检查：http://127.0.0.1:8000/health
- 在线文档：http://127.0.0.1:8000/docs

### 2. 前端启动（H5 开发模式）

```bash
cd client

# (a) 安装依赖
npm install

# (b) 启动 H5 开发服务器（默认 10086 端口，被占自动顺延）
npm run dev:h5
```

浏览器访问控制台输出的地址（如 `http://localhost:10086/`）。

### 3. 前端编译（微信小程序）

```bash
cd client

# 生产构建，输出到 client/dist/
npm run build:weapp
```

用「微信开发者工具」导入 `client/dist` 目录即可预览 / 上传。

---

## 数据库设计

4 张核心表，Alembic 版本化管理：

### `mi_event` · 赛事表
| 字段 | 类型 | 说明 |
|------|------|------|
| event_id | INT PK | 自增主键 |
| event_name | VARCHAR(100) | 赛事名称 |
| cover_image | VARCHAR(255) | 封面图 |
| **event_type** | INT | **1全马 2半马 3健康跑 4越野 5其他** |
| **event_status** | INT | **1未开始 2报名中 3报名结束 4比赛中 5已结束** |
| **event_level** | INT | **1白金 2金标 3精英标 4标牌 5田协** |
| start_time / end_time | DATETIME | 比赛起止时间 |
| registration_{start,end}_time | DATETIME | 报名时间窗 |
| province / city / location / address | VARCHAR | 地理位置（多维用于筛选） |
| introduction / description / route_map | TEXT | 赛事介绍 |
| registration_fee | DECIMAL(10,2) | ⭐ 新增：默认报名费 |
| is_hot / is_recommended | INT | 首页排序依据 |
| favorite_count / registration_count | INT | 统计（反写 / 展示用）|
| create_time / update_time / deleted | - | 通用审计字段 |

### `mi_user` · 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | INT PK | 自增主键 |
| username | VARCHAR(50) UNIQUE | 登录账号（开发期） |
| password | VARCHAR(100) | 密码（哈希） |
| nickname / avatar / phone / email | VARCHAR | 个人资料 |
| openid | VARCHAR(100) | 微信小程序唯一 ID |
| gender / user_type / status | INT | 性别 / 类型 / 状态 |
| login_ip / login_date | - | 最后登录信息 |

### `mi_favorite` · 收藏表
| 字段 | 类型 | 说明 |
|------|------|------|
| favorite_id | INT PK | 主键 |
| user_id + event_id | INT + UNIQUE | 联合唯一，一人一赛事只收藏一次 |
| create_time / update_time | DATETIME | 审计 |

### `mi_registration` · 用户报名记录（⭐ 新增表）
承载「关注页」报名 / 缴费 / 中签状态 &「我的页」完赛统计：

| 字段 | 类型 | 说明 |
|------|------|------|
| registration_id | INT PK | 主键 |
| user_id + event_id | INT + UNIQUE | 一人一赛事一条记录 |
| **registration_status** | INT | **0未报名 1已报名** |
| **payment_status** | INT | **0未缴费 1已缴费** |
| **lottery_status** | INT | **0未中签 1已中签 2抽签中** |
| fee | DECIMAL(10,2) | 实际报名费（可覆盖 event 默认值）|
| bib_number | VARCHAR(20) | 参赛号码 |
| finish_time | VARCHAR(20) | 完赛时间（如 "03:45:00"）|
| **result_status** | INT | **0未完赛 1已完赛 2PB（个人最好）** |
| create_time / update_time | DATETIME | 审计 |

迁移脚本：[alembic/versions/0001_add_registration_fee_and_table.py](server/alembic/versions/0001_add_registration_fee_and_table.py)

---

## API 接口一览

统一前缀 `/api/v1`，所有分页接口返回 `Page<T>{ items, total, page, page_size }`。

### `GET /events` · 赛事列表
> 首页卡片数据。推荐优先 → 热门其次 → 开赛时间升序。

| 参数 | 类型 | 说明 |
|------|------|------|
| page / page_size | int | 分页（默认 1 / 10） |
| keyword | str | 赛事名称模糊搜索 |
| event_type / event_status / event_level | int | 三大枚举筛选 |
| province | str | 省份精确匹配 |
| month | str | 按开赛月过滤，格式 `YYYY-MM` |
| is_hot / is_recommended | bool | 热门 / 推荐过滤 |

### `GET /events/filters` · 筛选项
返回当前数据库中真实存在的枚举值 + 月份 + 省份列表，用于首页 5 个下拉。

### `GET /events/{id}` · 赛事详情
返回 `EventDetail`（比 Brief 多报名信息、须知、主办、联系方式），登录态下额外带 `is_favorite` 布尔值。

### `POST /events/{id}/favorite` · 收藏赛事
### `DELETE /events/{id}/favorite` · 取消收藏
> 均需要 JWT Bearer Token。

---

### `GET /favorites` · 关注列表
> 关注页卡片。需登录，每条带：赛事基本信息 + **报名 / 缴费 / 中签三维状态** + 报名费 + 开赛倒计时天数。

### `GET /favorites/stats` · 关注统计条
> 返回 `{ favorite_count, registered_count, pending_lottery_count }`。

---

### `PUT /events/{id}/registration` · 更新报名状态
> 关注页 chips 切换时调用。可同时更新 `registration_status / payment_status / lottery_status / fee` 中的任意字段。

### `POST /races` · 添加自定义赛事
> 一键新建 event → favorite → registration 三条关联记录，从「关注页」添加按钮进入。

---

### `POST /users/login/wechat` · 微信静默登录
```json
{ "code": "wx.login.code", "nickname": "...", "avatar": "..." }
```
返回 `{ access_token, user_id, ...}`。小程序环境首次打开时在 `app.ts` 中自动调用。

### `POST /users/login/password` · 密码登录（开发期）
```json
{ "username": "admin", "password": "admin" }
```
H5 「我的页」点击登录弹窗的开发登录路径，便于本地调试。

### `GET /users/me` · 当前用户资料
### `PUT /users/me` · 更新昵称 / 头像
### `GET /users/me/stats` · 我的页统计
> 返回 `{ registered_count, total_spent, total_distance, recent_finished[] }`，完赛记录带完赛时间、PB 徽章。

### `POST /users/logout` · 退出登录

---

## 页面清单

| 页面 | 路径 | 类型 | 核心功能 |
|------|------|------|----------|
| 🏠 首页 | `pages/home/index` | Tab 页 | Banner 轮播 · 搜索 · 5 维筛选 · 赛事卡片列表 · 下拉刷新 · 分页加载 |
| ❤️ 关注 | `pages/follow/index` | Tab 页 | 三维统计 · 状态筛选 Tab · 赛事追踪卡片（报名 / 缴费 / 中签切换 + 费用编辑 + 倒计时）· 添加自定义赛事 |
| 👤 我的 | `pages/mine/index` | Tab 页 | 头像 / 昵称 / 等级 · 报名 / 花费 / 里程 三卡片 · 近期完赛列表 · 5 个菜单入口 |
| 📄 赛事详情 | `pages/race-detail/index` | 独立页 | Hero 区 + 三张快速信息卡 + 赛事信息列表 + 赛事介绍 + 底部「关注赛事」按钮 |
| ➕ 添加赛事 | `pages/add-race/index` | 独立页 | 基本信息（名称 / 类型 / 日期 / 地点 / 等级）+ 报名状态三 chip + 费用输入 + 保存并关注 |

页面配置见 [app.config.ts](client/src/app.config.ts)。

---

## 多端适配说明

| 差异点 | H5 处理 | 微信小程序处理 |
|--------|---------|----------------|
| 登录方式 | 密码登录（admin/admin）弹窗占位 | `Taro.login` 获取 code → 后端换 openid → JWT |
| TabBar | 自定义 React 组件 + `Taro.switchTab` | `custom-tab-bar` 目录配合 `app.json` 的 `custom: true` |
| 网络请求 | 走浏览器 fetch（Taro.request 封装） | 走微信 wx.request，自动添加 `Referer: mini-app` |
| 图片图标 | SVG data URI（兼容） | 同左，支持 base64 背景图 |
| 页面路由 | `/#/pages/xxx/index` Hash 模式 | 原生小程序路由栈 |
| 数据库驱动 | Windows 开发：aiomysql | 生产部署 / Docker：asyncmy（更快）|

---

## 设计稿还原

设计 token 完整映射到 [client/src/styles/variables.scss](client/src/styles/variables.scss)：

| 设计稿 CSS 变量 | SCSS 变量 | 值 |
|-----------------|-----------|-----|
| `--brand` | `$brand` / `$primary` | `#10B981`（薄荷绿主色）|
| `--brand-background` | `$bg-primary` | `#F0FDFA` |
| `--ink` / `--ink-2` / `--ink-3` | `$text1` / `$text2` / `$text3` | `#0F172A` / `#64748B` / `#94A3B8` |
| `--state-success/warning/error/info` | `$success/warning/error/info` | 状态色 |
| `--brand-radius-sm~xl` | `$radius-sm~xl` | 4 / 8 / 12 / 16px |
| `--brand-shadow-sm/md/lg` | `$shadow-sm/md/lg` | 三级阴影 |

组件样式对齐设计稿的 5 页 HTML 原型，见 [pages/](pages/) 目录。

---

## 常见问题

**Q: 启动后端报 `ImportError: cannot import name _log`？**
A: 原虚拟环境 pip 损坏。按本文「快速开始」步骤，在 `server/` 下新建独立 `.venv` 重新安装依赖即可。

**Q: Windows 下连远程 MySQL 报 `WinError 87` 或 SSL 错误？**
A: 已在 config 中处理：Windows 自动切到 `mysql+aiomysql` 驱动并默认关闭 SSL；如需 SSL 在 `.env` 加 `DB_SSL=1`。

**Q: 启动前端 H5 报 `useState is not a function`？**
A: React Hooks 必须从 `react` 包导入，不要从 `@tarojs/taro` 导入（Taro 只暴露 `useDidShow` / `usePullDownRefresh` 等生命周期 hook）。

**Q: 小程序 TabBar 不显示？**
A: 检查：1. `app.config.ts` 中 `tabBar.custom = true`；2. `src/custom-tab-bar/` 文件齐全；3. 每个 Tab 页面内 `useDidShow` 里同步 `selected` 状态。

---

## License

MIT
