"""微信小程序 AppSecret 配置 + 验证 + 沙盒账号清理工具

用法：
    # 1. 写入 secret 并立即验证（推荐）
    python tools/setup_wechat.py --set-secret <你的AppSecret>

    # 2. 只验证当前配置是否有效
    python tools/setup_wechat.py --verify

    # 3. 查看数据库 openid 现状
    python tools/setup_wechat.py --status

    # 4. 清理 dev_ 孤儿账号（没有任何收藏/报名的空壳账号）
    python tools/setup_wechat.py --clean-orphans         # 预演，只显示不删
    python tools/setup_wechat.py --clean-orphans --apply  # 真正执行（软删除）

    # 5. 把某个 dev_ 账号的数据迁移到真实账号（用户换设备/清缓存后补救）
    python tools/setup_wechat.py --merge 110 100

安全说明：脚本不会打印 AppSecret 明文，只显示长度与前 4 位。
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# 让脚本能 import app.*
SERVER_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_DIR))

ENV_PATH = SERVER_DIR / ".env"
SANDBOX_PREFIX = "dev_"


# --------------------------------------------------------------------------
# .env 读写（保留原有注释与顺序，只替换目标行）
# --------------------------------------------------------------------------
def read_env_text() -> str:
    return ENV_PATH.read_text(encoding="utf-8")


def upsert_env(text: str, key: str, value: str) -> str:
    """更新或追加 key=value，保留文件其余内容"""
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text)
    # 没找到就追加
    if not text.endswith("\n"):
        text += "\n"
    return text + f"{line}\n"


def get_env_value(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}\s*=(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else ""


def mask(s: str) -> str:
    if not s:
        return "(empty)"
    return f"{s[:4]}...(len={len(s)})"


# --------------------------------------------------------------------------
# 微信接口
# --------------------------------------------------------------------------
async def verify_credentials(app_id: str, secret: str) -> tuple[bool, str]:
    """用 /cgi-bin/token 验证 appid+secret（不需要 code，最干净的凭证测试）"""
    import httpx

    if not app_id:
        return False, "WECHAT_APP_ID 为空"
    if not secret:
        return False, "WECHAT_APP_SECRET 为空"

    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {"grant_type": "client_credential", "appid": app_id, "secret": secret}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(url, params=params)
            data = resp.json()
        except Exception as exc:
            return False, f"网络异常: {exc}"

    if "access_token" in data:
        return True, f"凭证有效（expires_in={data.get('expires_in')}s）"

    errcode = data.get("errcode")
    errmsg = data.get("errmsg")
    hint = {
        40013: "invalid appid —— AppID 不正确",
        40125: "invalid appsecret —— AppSecret 与 AppID 不匹配，请重新获取",
        45009: "接口调用超过限额",
        -1: "微信系统繁忙，稍后重试",
    }.get(errcode, "")
    return False, f"errcode={errcode} errmsg={errmsg}" + (f"（{hint}）" if hint else "")


# --------------------------------------------------------------------------
# 数据库操作
# --------------------------------------------------------------------------
async def db_status(settings) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT COUNT(*) FROM mi_user"))).scalar()
        dev_cnt = (
            await conn.execute(
                text("SELECT COUNT(*) FROM mi_user WHERE openid LIKE 'dev_%'")
            )
        ).scalar()
        real_cnt = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) FROM mi_user "
                    "WHERE openid IS NOT NULL AND openid NOT LIKE 'dev_%' "
                    "AND openid NOT LIKE 'openid%'"
                )
            )
        ).scalar()
        print(f"  总用户数        = {total}")
        print(f"  沙盒 dev_ openid = {dev_cnt}")
        print(f"  真实 openid      = {real_cnt}（统计口径：排除 dev_ 沙盒与 openid 开头的种子格式）")

        rows = (
            await conn.execute(
                text(
                    "SELECT u.user_id, u.nickname, u.openid, "
                    "  (SELECT COUNT(*) FROM mi_favorite f "
                    "   WHERE f.user_id=u.user_id AND f.deleted=0) AS fav_cnt, "
                    "  (SELECT COUNT(*) FROM mi_registration r "
                    "   WHERE r.user_id=u.user_id AND r.deleted=0) AS reg_cnt, "
                    "  u.login_date "
                    "FROM mi_user u "
                    "WHERE u.deleted=0 "
                    "ORDER BY u.user_id DESC LIMIT 20"
                )
            )
        ).fetchall()
        print()
        print(f"  {'user_id':<8}{'昵称':<16}{'openid':<30}{'收藏':<6}{'报名':<6}最后登录")
        print("  " + "-" * 92)
        for r in rows:
            oid = r[2] or "(null)"
            flag = "  ←沙盒" if (oid or "").startswith(SANDBOX_PREFIX) else ""
            print(
                f"  {r[0]:<8}{str(r[1] or '')[:15]:<16}{oid:<30}"
                f"{r[3]:<6}{r[4]:<6}{r[5]}{flag}"
            )
    await engine.dispose()


async def clean_orphans(settings, apply: bool) -> None:
    """软删除没有任何收藏/报名的 dev_ 空壳账号"""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT user_id, nickname, openid FROM mi_user "
                        "WHERE openid LIKE 'dev_%' AND deleted=0 "
                        "AND (SELECT COUNT(*) FROM mi_favorite f "
                        "     WHERE f.user_id=mi_user.user_id AND f.deleted=0)=0 "
                        "AND (SELECT COUNT(*) FROM mi_registration r "
                        "     WHERE r.user_id=mi_user.user_id AND r.deleted=0)=0"
                    )
                )
            ).fetchall()

            if not rows:
                print("  没有可清理的 dev_ 空壳账号。")
                return

            print(f"  发现 {len(rows)} 个无数据的 dev_ 空壳账号：")
            for r in rows:
                print(f"    user_id={r[0]}  nickname={r[1]}  openid={r[2]}")

            if not apply:
                print()
                print("  [预演模式] 未做任何修改。加 --apply 才会真正软删除。")
                return

            ids = [r[0] for r in rows]
            await conn.execute(
                text(
                    "UPDATE mi_user SET deleted=1 WHERE user_id IN :ids"
                ).bindparams(bindparam_expanded(ids))
            )
            print(f"\n  已软删除 {len(ids)} 个账号（deleted=1）：{ids}")
    finally:
        await engine.dispose()


def bindparam_expanded(ids):
    from sqlalchemy import bindparam

    return bindparam("ids", value=ids, expanding=True)


async def merge_users(settings, from_id: int, to_id: int) -> None:
    """把 from_id 的收藏/报名迁移到 to_id，然后软删除 from_id"""
    from sqlalchemy import text, select
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with engine.begin() as conn:
            f = (
                await conn.execute(
                    text("SELECT user_id, nickname, openid FROM mi_user WHERE user_id=:i"),
                    {"i": from_id},
                )
            ).fetchone()
            t = (
                await conn.execute(
                    text("SELECT user_id, nickname, openid FROM mi_user WHERE user_id=:i"),
                    {"i": to_id},
                )
            ).fetchone()
            if not f or not t:
                print(f"  用户不存在：from={from_id} to={to_id}")
                return

            print(f"  源账号 {from_id} ({f[1]}) openid={f[2]}")
            print(f"  目标账号 {to_id} ({t[1]}) openid={t[2]}")

            fav = await conn.execute(
                text("UPDATE mi_favorite SET user_id=:to WHERE user_id=:fr AND deleted=0"),
                {"to": to_id, "fr": from_id},
            )
            reg = await conn.execute(
                text(
                    "UPDATE mi_registration SET user_id=:to "
                    "WHERE user_id=:fr AND deleted=0"
                ),
                {"to": to_id, "fr": from_id},
            )
            # 目标账号昵称是默认「跑友xxxxx」时，用源账号的昵称覆盖
            await conn.execute(
                text(
                    "UPDATE mi_user SET nickname=:fn WHERE user_id=:to "
                    "AND (nickname IS NULL OR nickname LIKE '跑友%')"
                ),
                {"to": to_id, "fn": f[1]},
            )
            await conn.execute(
                text("UPDATE mi_user SET deleted=1 WHERE user_id=:fr"), {"fr": from_id}
            )
            print(f"  迁移完成：收藏 {fav.rowcount} 条，报名 {reg.rowcount} 条")
            print(f"  源账号 {from_id} 已软删除")
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
async def main_async(args) -> int:
    from app.config import get_settings

    # 写 secret
    if args.set_secret:
        secret = args.set_secret.strip()
        if len(secret) != 32:
            print(f"[警告] AppSecret 通常是 32 位，你输入的是 {len(secret)} 位，确认没复制错？")
            if not args.yes:
                ans = input("  仍然写入？[y/N] ").strip().lower()
                if ans != "y":
                    print("  已取消。")
                    return 1
        text = read_env_text()
        text = upsert_env(text, "WECHAT_APP_SECRET", secret)
        ENV_PATH.write_text(text, encoding="utf-8")
        print(f"[OK] 已写入 {ENV_PATH.name}: WECHAT_APP_SECRET={mask(secret)}")
        # 清缓存让新配置生效
        get_settings.cache_clear()

    settings = get_settings()
    app_id = settings.WECHAT_APP_ID
    secret = settings.WECHAT_APP_SECRET

    print()
    print("=" * 70)
    print("微信登录配置检查")
    print("=" * 70)
    print(f"  WECHAT_APP_ID     = {app_id or '(empty)'}")
    print(f"  WECHAT_APP_SECRET = {mask(secret)}")
    print(f"  配置文件          = {ENV_PATH}")
    print()

    exit_code = 0
    if args.verify or args.set_secret:
        ok, msg = await verify_credentials(app_id, secret)
        print(f"  凭证验证：{'PASS' if ok else 'FAIL'} —— {msg}")
        print()
        if not ok:
            exit_code = 1
            print("  获取 AppSecret 步骤：")
            print("    1. 登录 https://mp.weixin.qq.com")
            print("    2. 开发 → 开发管理 → 开发设置")
            print("    3. 找到「小程序密钥(AppSecret)」，点「重置」或「复制」")
            print("    4. 执行：python tools/setup_wechat.py --set-secret <secret>")
            print()

    if args.status or args.set_secret or args.verify:
        print("=" * 70)
        print("数据库 openid 现状")
        print("=" * 70)
        await db_status(settings)

    if args.clean_orphans:
        print()
        print("=" * 70)
        print("清理 dev_ 空壳账号")
        print("=" * 70)
        await clean_orphans(settings, apply=args.apply)

    if args.merge:
        print()
        print("=" * 70)
        print("合并账号")
        print("=" * 70)
        await merge_users(settings, args.merge[0], args.merge[1])

    return exit_code


def main() -> int:
    p = argparse.ArgumentParser(description="微信小程序 AppSecret 配置与 openid 修复工具")
    p.add_argument("--set-secret", metavar="SECRET", help="写入 AppSecret 到 server/.env")
    p.add_argument("--verify", action="store_true", help="验证 appid+secret 是否有效")
    p.add_argument("--status", action="store_true", help="查看数据库 openid 现状")
    p.add_argument("--clean-orphans", action="store_true", help="软删除无数据的 dev_ 空壳账号")
    p.add_argument("--apply", action="store_true", help="配合 --clean-orphans 真正执行")
    p.add_argument(
        "--merge", nargs=2, type=int, metavar=("FROM", "TO"), help="把 FROM 账号数据迁移到 TO"
    )
    p.add_argument("-y", "--yes", action="store_true", help="跳过交互确认")
    args = p.parse_args()

    if not any([args.set_secret, args.verify, args.status, args.clean_orphans, args.merge]):
        # 默认：状态 + 验证
        args.status = True
        args.verify = True

    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
