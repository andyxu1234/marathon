"""最酷 ZUICOOL 数据源适配器（enrich 流水线专用）

新 enrich 流水线：
- discover_events(min_date=today) → 全量抓列表页 → LLM 补全 → mi_event
- 列表页过滤参数：?type=run&where=asia（最酷网站自带分类：路跑 + 亚洲）
- 本地 _is_road_race 兜底过滤爬坡赛/徒步等边缘 case
- min_date=today 提前 break 历史页（最酷列表按比赛日期倒序）

旧 pipeline 的 fetch_raw / parse_rule_based / parse_detail 已随删旧 pipeline 清除。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.pipeline.base import EventCandidate

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class ZuicoolAdapter:
    """最酷马拉松报名 ZUICOOL 列表页采集器

    enrich 流水线专用：只抓列表卡片，不进详情页（LLM 联网补全缺失字段）。
    """
    source_name = "最酷"
    source_weight = 80

    BASE_URL = "https://zuicool.com"
    EVENTS_URL = "https://zuicool.com/events"
    # 列表页过滤参数：?type=run 只抓"路跑"分类（最酷网站自带分类，
    # 已过滤越野/铁三/海外等；本适配器再用 _is_road_race 做兜底过滤爬坡赛/徒步等边缘 case）
    EVENTS_TYPE_FILTER = "run"
    # 列表页地点过滤：?where=asia 只抓亚洲赛事（过滤欧洲/美洲等海外赛事）
    EVENTS_WHERE_FILTER = "asia"
    # 列表页分页参数：?page=N&per-page=100（注意不是 ?p=N）
    EVENTS_PAGE_SIZE = 100
    EVENTS_MAX_PAGES = 20   # 安全上限，min_date=today 通常 11 页就提前 break

    # ------------------- 采集 -------------------
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_one(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        """GET 一个 URL，返回 HTML 字符串（失败返回 None）"""
        try:
            resp = await client.get(url, follow_redirects=True,
                                    timeout=httpx.Timeout(timeout=None, connect=15))
            if resp.status_code == 200 and resp.text:
                return resp.text
            logger.warning(f"[Zuicool] 抓取失败 {url} status={resp.status_code}")
        except Exception as e:
            logger.warning(f"[Zuicool] 抓取异常 {url}: {e!r}")
        return None

    def _events_page_url(self, page: int) -> str:
        return (
            f"{self.EVENTS_URL}?type={self.EVENTS_TYPE_FILTER}"
            f"&where={self.EVENTS_WHERE_FILTER}"
            f"&page={page}&per-page={self.EVENTS_PAGE_SIZE}"
        )

    # 路跑类赛事关键词（保留），其它类型（越野/户外/徒步/登山）丢弃
    _RE_KEEP_TYPE = re.compile(r"(马拉松|半程|半马|全马|健康跑|欢乐跑|路跑|10公里|5公里|10K|5K|迷你)")
    _RE_DROP_TYPE = re.compile(r"(越野|户外|徒步|登山|越野跑|trail|Trail|登山赛|山地)")

    def _is_road_race(self, name: str, type_raw: Optional[str]) -> bool:
        """只保留马拉松/路跑类赛事，过滤越野/户外/徒步/登山等"""
        text = f"{name or ''} {type_raw or ''}"
        # 显式 DROP 关键词优先（避免"山地马拉松"被误判为保留）
        if self._RE_DROP_TYPE.search(text):
            return False
        # 显式 KEEP 关键词
        if self._RE_KEEP_TYPE.search(text):
            return True
        return False

    # 卡片日期格式 "2026.11.08" → date（解析失败返回 None）
    _RE_CARD_DATE_FULL = re.compile(r"(20\d{2})[\.\-年/](\d{1,2})[\.\-月/](\d{1,2})")

    def _parse_card_date(self, date_str: Optional[str]) -> Optional[date]:
        """把卡片 '2026.11.08' 解析成 date；解析失败返回 None"""
        if not date_str:
            return None
        m = self._RE_CARD_DATE_FULL.search(date_str)
        if not m:
            return None
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    async def discover_events(
        self, timeout: int = 20, max_pages: int | None = None,
        min_date: Optional[date] = None,
    ) -> list[dict]:
        """全量抓取列表页，返回轻量赛事清单（用于每日新增 diff）。

        只保留马拉松/路跑类赛事，过滤越野/户外/徒步/登山等。
        min_date: 只保留 start_date >= min_date 的赛事（默认不过滤）。
                  最酷列表页按比赛日期倒序排列（未来在前、历史在后），
                  当某页所有 items 都 < min_date 时提前 break，省请求量。
        返回每项：{event_id, url, name, start_date, location, reg_end, status, candidate}
        """
        max_pages = max_pages or self.EVENTS_MAX_PAGES
        out: list[dict] = []
        seen_ids: set[str] = set()
        async with httpx.AsyncClient(
            headers={"User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=timeout,
        ) as client:
            for page in range(1, max_pages + 1):
                url = self._events_page_url(page)
                try:
                    raw_html = await self._fetch_one(client, url)
                except Exception as e:
                    logger.warning(f"[Zuicool] 列表页 {url} 异常: {e!r}")
                    break
                if not raw_html:
                    break
                # 包装成 parse_event_list 接受的 RawPage 替代对象（只取 .html 和 .source_url）
                class _PageView:
                    def __init__(self, html: str, source_url: str):
                        self.html = html
                        self.source_url = source_url
                items = self.parse_event_list(_PageView(raw_html, url))
                if not items:
                    break   # 空页 = 已到末尾
                new_on_page = 0
                dropped_type = 0
                dropped_date = 0
                # 该页所有可解析日期是否都 < min_date（用于提前终止翻页）
                page_all_past = True if min_date else False
                for c in items:
                    eid = c.raw_extra.get("event_id") if c.raw_extra else None
                    if not eid or eid in seen_ids:
                        continue
                    seen_ids.add(eid)
                    # 类型过滤：只保留马拉松/路跑类
                    if not self._is_road_race(c.event_name, c.type_raw):
                        dropped_type += 1
                        continue
                    # 日期过滤：min_date 之后的才保留（解析失败保留，避免误杀）
                    if min_date:
                        sd = self._parse_card_date(c.start_date_raw)
                        if sd is None:
                            page_all_past = False   # 有无法解析的，不提前 break
                        elif sd >= min_date:
                            page_all_past = False
                        else:
                            dropped_date += 1
                            continue
                    out.append({
                        "event_id": eid,
                        "url": c.source_url,
                        "name": c.event_name,
                        "start_date": c.start_date_raw,
                        "location": c.location_raw,
                        "reg_end": c.reg_end_raw,
                        "status": c.status_raw,
                        "candidate": c,   # 完整 EventCandidate，供 enricher.build_raw_json
                    })
                    new_on_page += 1
                logger.info(
                    f"[Zuicool] 列表 page={page} 新增 {new_on_page} 条"
                    f"（过滤越野/户外 {dropped_type}，过滤过期 {dropped_date}），累计 {len(out)}"
                )
                # 该页所有可解析日期都早于 min_date → 后续页全是历史，提前 break
                if page_all_past:
                    logger.info(f"[Zuicool] page={page} 全部赛事已过期（< {min_date}），停止翻页")
                    break
                # 不足一页通常意味着最后一页
                if len(items) < self.EVENTS_PAGE_SIZE:
                    break
        return out

    # ------------------- 列表页解析（/events?page=N）-------------------
    # 列表页 DOM 实测（参见 /events?page=1&per-page=100）：
    #   div.event > div.event-body
    #     a.event-a[href=/event/{id}]   赛事名 + 链接
    #     div.info p                    "2026.11.08 · 福建 厦门市 翔安区 ..."
    #     div.meta                      "报名截止：09-24 23:59" + 报名按钮(状态/链接)
    _RE_CARD_ID = re.compile(r"/event/(\d+)")
    _RE_CARD_DATE = re.compile(r"(20\d{2}[\.\-年/]\d{1,2}[\.\-月/]\d{1,2})")
    _RE_CARD_REG_END = re.compile(r"报名截止[：:]\s*(\d{1,2}-\d{1,2}\s*\d{1,2}[:：]\d{1,2})")

    # 详情页解析需要的正则（保留以防 enrich 后续接入详情页富化时复用）
    _RE_FULL = re.compile(r"(全程|全马|马拉松)")
    _RE_HALF = re.compile(r"(半程|半马)")
    _RE_HEALTH = re.compile(r"(健康|欢乐|迷你|5K|5公里|10K|10公里)")
    _RE_CROSS = re.compile(r"(越野|山)")

    def parse_event_list(self, raw) -> list[EventCandidate]:
        """解析 /events 列表页卡片 -> 轻量 EventCandidate 列表

        卡片已含 日期/城市/报名截止/状态/链接，无需进详情页即可做增量识别。
        富字段（费用/规模/项目）由 enrich_with_llm 联网补全。
        """
        try:
            soup = BeautifulSoup(raw.html, "lxml")
        except Exception:
            soup = BeautifulSoup(raw.html, "html.parser")

        out: list[EventCandidate] = []
        seen: set[str] = set()
        for ev in soup.select("div.event"):
            body = ev.select_one("div.event-body")
            if not body:
                continue
            a = body.select_one("a.event-a") or body.select_one('a[href*="/event/"]')
            if not a:
                continue
            href = a.get("href", "") or ""
            m = self._RE_CARD_ID.search(href)
            if not m:
                continue
            eid = m.group(1)
            if eid in seen:
                continue
            seen.add(eid)
            full_url = href if href.startswith("http") else (self.BASE_URL + href)
            name = a.get_text(strip=True)

            info = body.select_one("div.info p")
            info_txt = info.get_text(" ", strip=True) if info else ""
            start_date = self._extract_first(self._RE_CARD_DATE, info_txt)
            location = re.sub(r"^.*?·\s*", "", info_txt).strip() if "·" in info_txt else None

            meta_el = body.select_one("div.meta")
            meta_txt = meta_el.get_text(" ", strip=True) if meta_el else ""
            rm = self._RE_CARD_REG_END.search(meta_txt)
            reg_end_raw = rm.group(1).strip() if rm else None

            btn = body.select_one('div.meta a[href*="/event/"], div.meta a.btn')
            status_raw = None
            reg_link = None
            if btn:
                status_raw = btn.get_text(strip=True) or None
                reg_link = btn.get("href")

            # 提取赛事专属 logo（img.logo，src 形如
            # https://s.pro.zuicool.com/events/{eid}/logo-xxx.{jpg|png}?imageMogr2/...
            # 去掉七牛缩略图 query 拿原图；只认 /events/ 路径，排除 /tags/ 分类共用 logo
            cover_image = None
            logo_img = ev.select_one("img.logo")
            if logo_img:
                src = (logo_img.get("src") or "").split("?")[0]
                if "/events/" in src:
                    cover_image = src

            out.append(EventCandidate(
                event_name=self._clean_name(name) or name,
                source_name=self.source_name,
                source_url=full_url,
                source_weight=self.source_weight,
                start_date_raw=start_date,
                location_raw=location,
                status_raw=status_raw,
                reg_end_raw=reg_end_raw,
                reg_link=reg_link,
                type_raw=self._guess_type(name + " " + info_txt),
                parser_tag="rule",
                parse_confidence=70,
                cover_image=cover_image,
                raw_extra={"event_id": eid, "list_page": True},
            ))
        return out

    # ------------------- 工具函数 -------------------
    @staticmethod
    def _extract_first(pattern: re.Pattern, text: str) -> Optional[str]:
        m = pattern.search(text)
        return m.group(0) if m else None

    @staticmethod
    def _clean_name(name: str) -> str:
        name = re.sub(r"[\[\]【】《》()（）].*?[\]\)）】》]", "", name)
        name = re.sub(r"\s+", "", name)
        name = name.strip("-—_·|· \t")
        # 去掉"开启报名""抽签结果""报名指南"等后缀
        for tail in ("开启报名", "报名开启", "即将截止", "报名指南", "抽签结果",
                     "公布", "报名中", "赛事详情", "报名"):
            if name.endswith(tail):
                name = name[: -len(tail)]
        # 如果结果太短，保留原文
        return name if len(name) >= 3 else (re.sub(r"\s+", "", name) or "未知赛事")

    def _guess_type(self, text: str) -> str:
        if self._RE_CROSS.search(text):
            return "越野跑"
        if self._RE_HALF.search(text):
            return "半程马拉松"
        if self._RE_HEALTH.search(text):
            return "健康跑"
        if self._RE_FULL.search(text):
            return "马拉松"
        return "未知"   # 不命中任何路跑关键词时返回未知，避免边缘赛事被误判为马拉松
