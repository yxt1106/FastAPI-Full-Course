from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from config import settings
from database import Base


class User(Base):
    __tablename__ = "users" # 告诉LQLAlchemy这个模型对应数据库中的users表

    # id, username, email, password_hash, image_file: 定义了User模型的字段及其属性
    # primary_key=True: 表示该字段(id)是主键，唯一标识每条记录，使其在数据库中唯一
    # index=True: 表示该字段需要创建索引，以提高查询性能
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    # T10
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    image_file: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        default=None,
    )

    # posts, reset_tokens: 定义了User模型与Post模型和PasswordResetToken模型之间的关系

    # relationship: 定义了User和Post之间的关系，表示一个用户可以有多个帖子
    # cascade="all, delete-orphan": 表示当用户被删除时，相关的帖子也会被删除
    posts: Mapped[list[Post]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
    )

    reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def image_path(self) -> str:
        if self.image_file: # 如果用户有头像，则返回头像的完整URL路径，否则返回默认头像路径
            return f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), # 这个字段引用 users 表的 id
        nullable=False, # 不能为null，即帖子必须有作者
        index=True, # 给 user_id 建立索引，让按用户查询帖子时更加高效
    )

    # 文章发布时间
    date_posted: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC), # 创建新的 Post 时，如果没有提供发布时间，就自动使用当前 UTC 时间
    )

    # 点赞数
    likes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # back_populates 就是把两边连起来(User.posts <-> Post.author)，这样在查询 Post 时可以直接访问其作者 User，而在查询 User 时也可以直接访问其所有帖子 Post
    author: Mapped[User] = relationship(back_populates="posts")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="reset_tokens")
