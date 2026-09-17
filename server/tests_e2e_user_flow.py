"""E2E: 微信登录(H5 sandbox) → 头像上传 → 更新资料 → 关注/取消 → 401 重试"""
from __future__ import annotations

import io
import json
import struct
import zlib
import urllib.request
import urllib.error
import http.client
import mimetypes
import uuid

BASE = "http://127.0.0.1:8000/api/v1"

# ---------- 生成 1x1 PNG ----------
def make_png_1x1() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB
    raw = b"\x00" + bytes([0xEF, 0x44, 0x44])  # filter=0, R=239 G=68 B=68 (#EF4444)
    idat = zlib.compress(raw, 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")

PNG = make_png_1x1()


def http(method: str, url: str, *, json_body=None, headers=None, form_file=None):
    """form_file: (field, filename, bytes, content_type)"""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    data = None
    if form_file is not None:
        field, filename, fbytes, ctype = form_file
        boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
        hdrs["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        body = bytearray()
        body += f"--{boundary}\r\n".encode()
        body += f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'.encode()
        body += f"Content-Type: {ctype}\r\n\r\n".encode()
        body += fbytes
        body += b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        data = bytes(body)
    elif json_body is not None:
        hdrs["Content-Type"] = "application/json"
        data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            txt = raw.decode("utf-8") if raw else ""
            body_json = json.loads(txt) if txt else None
            return resp.status, body_json, resp.headers
    except urllib.error.HTTPError as e:
        raw = e.read()
        txt = raw.decode("utf-8") if raw else ""
        try:
            body_json = json.loads(txt) if txt else None
        except Exception:
            body_json = {"raw": txt}
        return e.code, body_json, e.headers


def ok(code):
    return 200 <= code < 300


def main():
    print("=== 1. 微信登录(H5 sandbox) ===")
    code, body, _ = http(
        "POST", f"{BASE}/users/login/wechat",
        json_body={"code": "h5-sandbox-local", "appid": "h5-dev"},
    )
    assert ok(code), (code, body)
    print("new_user:", body["is_new_user"], "user_id:", body["user"]["user_id"],
          "nickname:", body["user"]["nickname"])
    token = body["token"]
    bearer = {"Authorization": f"Bearer {token}"}

    print("\n=== 2. GET /users/me 初始资料 ===")
    code, me, _ = http("GET", f"{BASE}/users/me", headers=bearer)
    assert ok(code)
    print("me:", me)

    print("\n=== 3. 头像上传 ===")
    code, up, _ = http(
        "POST", f"{BASE}/users/avatar", headers=bearer,
        form_file=("file", "avatar_test.png", PNG, "image/png"),
    )
    assert ok(code), (code, up)
    print("upload:", up)
    avatar_url = up["url"]
    assert avatar_url.startswith("/m-uploads/avatars/"), avatar_url

    print("\n=== 4. PUT /users/me 更新昵称 + 头像 ===")
    new_nick = f"AndyTest_{uuid.uuid4().hex[:6]}"
    code, upd, _ = http(
        "PUT", f"{BASE}/users/me", headers=bearer,
        json_body={"nickname": new_nick, "avatar": avatar_url},
    )
    assert ok(code)
    print("updated:", upd)
    assert upd["nickname"] == new_nick
    assert upd["avatar"] == avatar_url

    print("\n=== 5. GET /users/me 验证已保存 ===")
    code, me2, _ = http("GET", f"{BASE}/users/me", headers=bearer)
    assert ok(code)
    assert me2["nickname"] == new_nick, (me2["nickname"], new_nick)
    assert me2["avatar"] == avatar_url, (me2["avatar"], avatar_url)
    print("OK")

    print("\n=== 6. 获取一个赛事 ===")
    code, page, _ = http("GET", f"{BASE}/events?page=1&page_size=1")
    assert ok(code)
    assert page["items"], "需要数据库里至少有一条赛事数据"
    ev = page["items"][0]
    print("event_id:", ev["event_id"], "name:", ev["event_name"])

    print("\n=== 7. 关注赛事（已登录） ===")
    code, fav, _ = http("POST", f"{BASE}/events/{ev['event_id']}/favorite", headers=bearer)
    assert ok(code), (code, fav)
    print("favorite:", fav)

    print("\n=== 8. 取消关注 ===")
    code, unfav, _ = http("DELETE", f"{BASE}/events/{ev['event_id']}/favorite", headers=bearer)
    assert ok(code)
    print("unfavorite:", unfav)

    print("\n=== 9. 未登录关注 → 401 → 静默登录 → 重试（模拟前端 ensureLoggedIn 行为） ===")
    code, err, _ = http("POST", f"{BASE}/events/{ev['event_id']}/favorite")
    assert code == 401, f"期望 401，实际 {code} {err}"
    print("未登录关注 => 401 OK")
    # 模拟前端 ensureLoggedIn
    code, lb, _ = http(
        "POST", f"{BASE}/users/login/wechat",
        json_body={"code": "h5-sandbox-local", "appid": "h5-dev"},
    )
    assert ok(code)
    bearer2 = {"Authorization": f"Bearer {lb['token']}"}
    code, fav2, _ = http("POST", f"{BASE}/events/{ev['event_id']}/favorite", headers=bearer2)
    assert ok(code), (code, fav2)
    print("401→ensureLoggedIn→retry OK:", fav2)
    # 清理
    http("DELETE", f"{BASE}/events/{ev['event_id']}/favorite", headers=bearer2)

    print("\n=== 10. /me/stats 有返回 ===")
    code, stats, _ = http("GET", f"{BASE}/users/me/stats", headers=bearer)
    assert ok(code)
    print("stats keys:", sorted(stats.keys()))
    assert stats["user_id"] == me2["user_id"]

    print("\n✅ E2E 全链路 PASS")


if __name__ == "__main__":
    main()
