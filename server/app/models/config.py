from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Config(Base):
    """系统配置字典表 mi_config —— 前台下拉框/枚举数据源

    通用字典设计：一类枚举 = 一个 config_type，一项取值 = 一行记录。
    业务表存 int（config_code 的数字部分），展示文案取 config_name；
    前端下拉数据统一 GET /api/v1/configs 从这里取，加选项 = 加一行，不用发版。

    config_type 约定（与各业务 model 注释 / 前端常量逐字对齐）：
      gender         性别       0未设置 1男 2女            (mi_user.gender)
      age_group      年龄段     0未设置 1<=34 2:35-39 ... 8>=65  (mi_user.age_group)
      reg_status     报名状态   0未报名 1已报名            (mi_registration.registration_status)
      pay_status     缴费状态   0未缴费 1已缴费            (mi_registration.payment_status)
      lottery_status 中签状态   0未中签 1已中签 2抽签中    (mi_registration.lottery_status)
      result_status  完赛状态   0未完赛 1已完赛 2PB        (mi_registration.result_status)
      event_type     赛事类型   1马拉松 2半程马拉松 3健康跑 4越野跑 5其他
      event_status   赛事状态   1未开始 2报名中 3报名结束 4比赛中 5已结束
      event_level    赛事级别   1白金 2金标 3精英标 4标牌 5田协
    """

    __tablename__ = "mi_config"
    __table_args__ = (
        UniqueConstraint("config_type", "config_code", name="uk_type_code"),
    )

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="配置类别")
    config_code: Mapped[str] = mapped_column(String(50), nullable=False, comment="字典值")
    config_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="展示文案")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    status: Mapped[int] = mapped_column(Integer, default=1, comment="1启用 0停用")
    remark: Mapped[Optional[str]] = mapped_column(String(255), comment="备注")
    create_by: Mapped[Optional[str]] = mapped_column(String(50), comment="创建者")
    create_time: Mapped[Optional[str]] = mapped_column(
        DateTime, server_default=func.current_timestamp(), comment="创建时间"
    )
    update_by: Mapped[Optional[str]] = mapped_column(String(50), comment="更新者")
    update_time: Mapped[Optional[str]] = mapped_column(
        DateTime, onupdate=func.current_timestamp(), comment="更新时间"
    )
    deleted: Mapped[int] = mapped_column(Integer, default=0, comment="删除标志")
