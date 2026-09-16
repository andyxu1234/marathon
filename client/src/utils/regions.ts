/**
 * 省→市级联数据工具
 * 数据源：province-city-china (民政部 GB/T 2260)
 *
 * 34 省 / 直辖市 / 特别行政区
 *   - 普通省：下辖 ~10-20 个市
 *   - 直辖市（北京/上海/天津/重庆）、特别行政区：没有下辖市
 *     → 我们把"自己"作为唯一选项，保证 UI 一致
 */
import rawProvinces from 'province-city-china/dist/province.json'
import rawCities from 'province-city-china/dist/city.json'

// province-city-china 原始类型
interface RawProvince { code: string; name: string; province: string }
interface RawCity { code: string; name: string; province: string; city: string }

const PROVINCES = rawProvinces as RawProvince[]
const CITIES = rawCities as RawCity[]

// 规范化 name：去掉冗余后缀"市/省/自治区/壮族/回族/维吾尔/特别行政区"用于匹配
function normalizeName(s: string): string {
  return s
    .replace(/特别行政区$/, '')
    .replace(/壮族自治区$/, '')
    .replace(/回族自治区$/, '')
    .replace(/维吾尔自治区$/, '')
    .replace(/自治区$/, '')
    .replace(/省$/, '')
    .replace(/市$/, '')
}

export interface ProvinceOption {
  code: string          // 6 位区划代码，如 '320000'
  provinceKey: string   // 省匹配键（city.province 2 位代码），如 '32'
  name: string          // 展示名，如 '江苏省'
  matchName: string     // 匹配名（去后缀），用于和数据库 province 字段对齐
}

export interface CityOption {
  code: string          // 6 位区划代码，如 '320100'
  provinceKey: string   // 所属省的匹配键
  name: string          // 展示名，如 '南京市'
  matchName: string     // 匹配名（去后缀），用于和数据库 city 字段对齐
}

// 内存构建一次
const PROVINCE_LIST: ProvinceOption[] = PROVINCES.map((p) => ({
  code: p.code,
  provinceKey: p.province,
  name: p.name,
  matchName: normalizeName(p.name),
}))

const CITY_LIST: CityOption[] = CITIES.map((c) => ({
  code: c.code,
  provinceKey: c.province,
  name: c.name,
  matchName: normalizeName(c.name),
}))

/**
 * 取所有省列表（前端下拉直接用）
 */
export function getAllProvinces(): ProvinceOption[] {
  return PROVINCE_LIST
}

/**
 * 根据 provinceKey 取该省的城市列表。
 *   - 普通省：返回正常 cities
 *   - 直辖市 / 特别行政区（没有下辖市）：自动构造一个"自己"的虚拟 city
 *     保证级联 UI 行为一致：用户选完省 → 进入下一步选市，必有结果
 */
export function getCitiesByProvince(provinceKey: string): CityOption[] {
  const list = CITY_LIST.filter((c) => c.provinceKey === provinceKey)
  if (list.length > 0) return list

  const prov = PROVINCE_LIST.find((p) => p.provinceKey === provinceKey)
  if (!prov) return []

  // 直辖市/特别行政区：虚拟一个 city，code = 省 code + 0000 占位？直接用省的 6 位 code
  return [
    {
      code: prov.code,
      provinceKey: prov.provinceKey,
      name: prov.name,
      matchName: prov.matchName,
    },
  ]
}

/**
 * 把用户选择的 {provinceName, cityName} 转换成"能匹配数据库 Event.province/city 字段"的纯文本。
 *
 * 背景：
 *   - 前端存的是全称（"江苏省" / "南京市"）
 *   - 数据库里 pipeline 归一化的通常是短名（"江苏" / "南京"），也可能是全称
 * 策略：
 *   - 两个版本都试：优先 matchName（去后缀，概率匹配高），失败时再给 full name（让后端用 OR 条件兜底）
 *
 * 实际上现在 list_events 接口接收 plain string，后端就按字段直接等值匹配。
 * 所以我们这里返回 { province, city }，其中 province 用 matchName、city 也用 matchName，
 * 如果将来数据库里存的是全称，由后端改成 LIKE/兼容匹配即可。
 */
export function toQueryParams(
  selectedProvince: ProvinceOption | null,
  selectedCity: CityOption | null,
): { province: string | null; city: string | null } {
  return {
    province: selectedProvince ? selectedProvince.matchName : null,
    city: selectedCity ? selectedCity.matchName : null,
  }
}
