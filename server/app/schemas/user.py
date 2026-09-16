from typing import Optional
from pydantic import BaseModel


class UserProfile(BaseModel):
    user_id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    username: Optional[str] = None
    runner_level: str = "跑者"
    runner_no: Optional[str] = None
    gender: int = 0  # 0未设置 1男 2女
    age_group: int = 0  # 0未设置 1<=34 2:35-39 3:40-44 4:45-49 5:50-54 6:55-59 7:60-64 8>=65
    # 是否 dev_ 沙盒账号（WECHAT_APP_SECRET 缺失期产生的假 openid）。
    # 小程序端据此触发"自愈升级"：静默重登换真实 openid，数据就地迁移不丢失。
    is_sandbox: bool = False


class LoginOut(BaseModel):
    token: str
    user: UserProfile
    is_new_user: bool = False


class AvatarUploadOut(BaseModel):
    """上传头像后返回可直接存到 user.avatar 的相对 URL"""
    url: str


class RecentFinishedItem(BaseModel):
    event_id: int
    event_name: str
    start_time: Optional[str] = None
    finish_time: Optional[str] = None
    result_status: int = 0  # 0未完赛 1已完赛 2PB
    is_pb: bool = False


class NextRaceItem(BaseModel):
    """下一场比赛"""
    event_id: Optional[int] = None
    custom_event_id: Optional[int] = None
    event_name: str
    event_type: int = 0
    event_type_label: str = ""
    start_date: str  # YYYY-MM-DD
    days_away: int  # 负数=已开赛, 正数=倒计时
    is_custom: bool = False


class MyRankItem(BaseModel):
    """排行榜中的我的位置（跨 metric 取最好排名）"""
    metric: str  # distance / half_marathon_pb / full_marathon_pb
    rank: int
    total_users: int
    value_label: str
    # 激励语："你比全国 75% 的跑者跑得多"
    insight: Optional[str] = None


class UserStats(BaseModel):
    """我的页统计"""
    user_id: int
    nickname: Optional[str] = None
    avatar: Optional[str] = None
    runner_level: str = "跑者"
    runner_no: Optional[str] = None
    gender: int = 0  # 0未设置 1男 2女
    age_group: int = 0  # 0未设置 1<=34 2:35-39 3:40-44 4:45-49 5:50-54 6:55-59 7:60-64 8>=65

    # —— 核心数据条 ——
    registered_count: int = 0       # 报名中（registration_status=1）
    finished_count: int = 0         # 完赛场次（result_status>=1）
    total_spent: float = 0.0        # 累计花费（已缴费的 fee）
    total_distance: float = 0.0     # 跑步里程（按 event_type 推算：全马42.195/半马21.0975/健康跑5/越野30）

    # —— 跑者档案（按 event_type 区分，PB=finish_time 最小）——
    half_pb: Optional[str] = None   # "2:03:15" 格式
    full_pb: Optional[str] = None
    favorited_count: int = 0        # 关注赛事数

    # —— 激励模块 ——
    next_race: Optional[NextRaceItem] = None   # 下一场比赛
    my_rank: Optional[MyRankItem] = None       # 我的最佳排名
    recent_finished: list[RecentFinishedItem] = []
