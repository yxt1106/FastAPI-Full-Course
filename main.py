from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.exceptions import HTTPException as StarletteHTTPException

import models
from config import settings
from database import engine, get_db
from routers import posts, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

# T2:
# 挂载静态文件目录, app.mount("/static", ...)
# 表示：把 URL 路径 /static 交给一个专门的应用来处理。
# 比如浏览器请求：/static/css/main.css
# FastAPI 就会把这个请求交给后面的 StaticFiles。
# 第一个参数url路径，第二个静态文件实例，指向文件夹里的静态文件
# 可以在模板template里引用的名字
# href="{{ url_for('static', path='icons/favicon.ico') }}"：动态生成 static/icons/favicon.ico 这个静态文件的 URL
# url_for() 根据路由名称动态生成 URL
# 'static' 对应 app.mount(..., name="static")
# path 指定 static 目录下的具体文件
# 最终生成 /static/icons/favicon.ico
# 这行代码表示把你项目本地的 static 文件夹，挂载成网站可以直接访问的静态文件目录
# StaticFiles(directory="static") 表示把本地的 static 文件夹作为静态文件目录
# 静态文件实际存在于当前项目的 static 文件夹。
# name= ... 主要是给这个挂载点起一个名字，方便在 FastAPI / Starlette 的 URL 路由系统中引用。
app.mount("/static", StaticFiles(directory="static"), name="static")

# T2:
# template: 既要向用户提供页面，又要保留用于后端 API 的 JSON 接口。
# 因此，我们配置了 Jinja2 模板，向模板传递数据，利用 Jinja2 语法编写循环和条件判断，并通过 `layout.html` 实现了模板继承。

# ()里的directory="templates"表示导入引用项目里的template文件夹
# 有了这个templates，@app.get("..",response_class=HTMLResponse)里的response_class=HTMLResponse就不用写了
templates = Jinja2Templates(directory="templates")

app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])



@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    response.headers["X-Content-Type-Options"] = "nosniff"

    if "Referrer-Policy" not in response.headers:
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if request.url.hostname not in ("localhost", "127.0.0.1"):
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains"
        )

    return response

# get表示获取，("/health")表示路由
@app.get("/health")
async def health_check(db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "healthy"}

# FastAPI 默认会把路由自动加入 OpenAPI 文档
# 但include_in_schema=False后，则不会放入文档
# 这样可以使得文档更加简洁
# name="home"路由名字
@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
# ()中的Request是Jinja2要求的
# db: Annotated[AsyncSession, Depends(get_db)]表示依赖注入，获取数据库会话
# db告诉API，在运行这个函数之前调用get_db函数然后传递结果作为db的参数
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    count_result = await db.execute(select(func.count()).select_from(models.Post))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .order_by(models.Post.date_posted.desc())
        .limit(settings.posts_per_page),
    )
    posts = result.scalars().all()

    has_more = len(posts) < total

    # 然后templates.TemplateResponse(request, "home.html",)
    # 表示移除了response_class=HTMLResponse，可以用上面这个代替了
    # templates.TemplateResponse第三个表示参数，
    # 是一个字典，里面存储着所有要用到页面中的变量
    return templates.TemplateResponse(
        request,
        "home.html",
        # 字典里的键可以作为参数(或模板上下文)传递到template组件里面
        # 即可以在组件/template里面直接用这些参数
        {
            "posts": posts,
            "title": "Home",
            "limit": settings.posts_per_page,
            "has_more": has_more,
        },
    )


@app.get("/posts/{post_id}", include_in_schema=False)
async def post_page(
    request: Request,
    post_id: int, # T3: 自动捕获了上面/posts/{post_id}的参数
    # post_id: int 表示把post_id限定为特定类型
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id),
    )
    post = result.scalars().first()
    if post:
        title = post.title[:50]
        return templates.TemplateResponse(
            request,
            "post.html",
            {"post": post, "title": title},
        )
    
    # T3:raise HTTPException:
    # 使得在请求失败时返回错误，而不是即使没有请求到也返回200状态码
    # status_code=status.HTTP_404_NOT_FOUND直接返回404状态码
    # detail: 在response里添加的message
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


@app.get("/users/{user_id}/posts", include_in_schema=False, name="user_posts")
async def user_posts_page(
    request: Request,
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first() # 获取第一个用户对象如果没有就为none
    if not user:# 返回空表有两种情况，用户不存在或没发帖，所以要先判断不存在情况
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    count_result = await db.execute(
        select(func.count())
        .select_from(models.Post)
        .where(models.Post.user_id == user_id),
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
        .limit(settings.posts_per_page),
    )
    posts = result.scalars().all()

    has_more = len(posts) < total

    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {
            "posts": posts,
            "user": user,
            "title": f"{user.username}'s Posts",
            "limit": settings.posts_per_page,
            "has_more": has_more,
        },
    )


@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Login"},
    )


@app.get("/register", include_in_schema=False)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"title": "Register"},
    )


@app.get("/account", include_in_schema=False)
async def account_page(request: Request):
    return templates.TemplateResponse(
        request,
        "account.html",
        {"title": "Account"},
    )


@app.get("/forgot-password", include_in_schema=False)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {"title": "Forgot Password"},
    )


@app.get("/reset-password", include_in_schema=False)
async def reset_password_page(request: Request):
    response = templates.TemplateResponse(
        request,
        "reset_password.html",
        {"title": "Reset Password"},
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

# T3: 统一处理整个 FastAPI 应用中的 HTTP 异常，
# 并根据请求是 API 还是普通网页，返回不同格式的错误结果。
# @app.exception_handler(StarletteHTTPException)告诉 FastAPI：
# “以后应用里出现 StarletteHTTPException，不要直接按照默认方式处理，交给我下面这个函数处理。”
@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request, # request: Request 表示请求对象，包含了请求的所有信息，比如 URL、方法、头信息等
    exception: StarletteHTTPException, 
):  
    # 请求的 URL 路径以 /api 开头，说明是 API 请求
    if request.url.path.startswith("/api"):
        # 返回 JSON 格式的错误响应，包含状态码和错误详情
        return await http_exception_handler(request, exception)

    # 若不是api请求, 则返回 HTML 格式的错误页面
    message = ( # 决定HTML 错误页面上到底显示什么文字。它使用 Python 的 or
        exception.detail
        # 如果 exception.detail 是空的，那么使用默认信息：
        or "An error occurred. Please check your request and try again."
    )
    # 返回一个 HTML 错误页面，使用 Jinja2 模板渲染 error.html，并传递状态码、标题和错误信息
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message,
        },
        # 防止即使错误发生了，浏览器仍然显示 200 OK 的状态码，而是返回实际的错误状态码
        status_code=exception.status_code,
    )
# 这是这节课很重要的一个设计思想：同一套数据源，同时服务 API 客户端和浏览器

# T3: 处理请求验证错误的异常处理器
# 因为验证请求不是HTTP异常，而是请求验证错误，所以需要单独处理
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
