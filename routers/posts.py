from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from auth import CurrentUser
from config import settings
from database import get_db
from schemas import PaginatedPostsResponse, PostCreate, PostResponse, PostUpdate

router = APIRouter()

# T4: response_model:开始修改 FastAPI 路由。例如：
# @app.get("/api/posts", response_model=list[PostResponse])
# 这说明返回的数据必须符合 list[PostResponse]
@router.get("", response_model=PaginatedPostsResponse)
async def get_posts(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = settings.posts_per_page,
):

    count_result = await db.execute(select(func.count()).select_from(models.Post))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc())
        .offset(skip)
        .limit(limit),
    )
    posts = result.scalars().all()

    has_more = skip + len(posts) < total

    return PaginatedPostsResponse(
        posts=[PostResponse.model_validate(post) for post in posts],
        total=total,
        skip=skip,
        limit=limit,
        has_more=has_more,
    )


@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post(
    post: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    new_post = models.Post(
        title=post.title,
        content=post.content,
        user_id=current_user.id,
    )
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id),
    )
    post = result.scalars().first()
    if post:
        return post
    raise HTTPException(status_code=status.HTTPa_404_NOT_FOUND, detail="Post not found")


# “登录用户修改自己的一篇文章：
# 先通过 ID 找到文章，如果文章不存在返回 404，
# 如果不是自己的返回 403，然后用新数据完整替换标题和内容，
# 提交数据库，最后返回更新后的文章。”
@router.put("/{post_id}", response_model=PostResponse)
async def update_post_full(
    post_id: int,
    post_data: PostCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first() # 查询结果变成 Post 对象
    # 例如数据库：
    # id   title       content
    # 5    FastAPI     Hello

    # 查询之后：
    # post.id       # 5
    # post.title    # "FastAPI"
    # post.content  # "Hello"
    if not post: # 判断文章是否存在
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    # 检查当前用户是不是文章作者
    # 假设数据库中的文章: post.user_id = 3
    # 当前登录用户：current_user.id = 10
    if post.user_id != current_user.id:
        raise HTTPException(
            # 你登录了，但是你没有权限修改这篇文章。
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post",
        )
    # 通过了前面的两个检查之后：
    post.title = post_data.title
    post.content = post_data.content

    await db.commit() # 真正保存到数据库
    # 让 SQLAlchemy 根据数据库中的最新状态重新同步这个 post 对象
    await db.refresh(post, attribute_names=["author"])
    return post


@router.patch("/{post_id}", response_model=PostResponse)
async def update_post_partial(
    post_id: int,
    post_data: PostUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this post",
        )

    # 只保留用户这次请求中真正提供的字段，避免误修改其他没有修改的字段
    # unset 可以简单理解为：这个字段这次请求根本没有设置。
    # exclude_unset为排除掉这次没有设置的字段
    update_data = post_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(post, field, value) # field是字段，value是设置的值

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    if post.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this post",
        )

    await db.delete(post)
    await db.commit()
