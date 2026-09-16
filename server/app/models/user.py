from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """用户表 mi_user

    gender: 0未知/未设置 1男 2女
    user_type: 0普通用户 1管理员
    status: 0正常 1停用
    platform: 1=weapp 2=douyin 9=h5沙盒

    openid 在同一 platform 内唯一，跨 platform 不保证唯一。
    复合唯一约束 uk_platform_openid(platform, openid) 保证不出现同平台重复用户。
    """

    __tablename__ = "mi_user"
    __table_args__ = (
        UniqueConstraint("platform", "openid", name="uk_platform_openid"),
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, comment="用户名")
    password: Mapped[str] = mapped_column(String(100), nullable=False, comment="密码")
    nickname: Mapped[Optional[str]] = mapped_column(String(50), comment="昵称")
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, comment="手机号")
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, comment="邮箱")
    gender: Mapped[int] = mapped_column(Integer, default=0, comment="性别")
    age_group: Mapped[int] = mapped_column(Integer, default=0, comment="年龄段")
    avatar: Mapped[Optional[str]] = mapped_column(String(255), comment="头像")
    openid: Mapped[Optional[str]] = mapped_column(String(100), comment="平台openid（微信/抖音通用）")
    platform: Mapped[int] = mapped_column(
        Integer, default=1, comment="登录平台：1=weapp 2=douyin 9=h5沙盒"
    )
    app_id: Mapped[Optional[str]] = mapped_column(
        String(50), comment="登录时使用的小程序appid（精确匹配secret用）"
    )
    user_type: Mapped[int] = mapped_column(Integer, default=0, comment="用户类型")
    status: Mapped[int] = mapped_column(Integer, default=0, comment="状态")
    login_ip: Mapped[Optional[str]] = mapped_column(String(50), comment="最后登录IP")
    login_date: Mapped[Optional[str]] = mapped_column(DateTime, comment="最后登录时间")
    create_by: Mapped[Optional[str]] = mapped_column(String(50), comment="创建者")
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_by: Mapped[Optional[str]] = mapped_column(String(50), comment="更新者")
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
    remark: Mapped[Optional[str]] = mapped_column(String(500), comment="备注")
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
