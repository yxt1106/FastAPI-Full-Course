# T17: contest.py是一个pytest可以自动识别的文件
# 这里用于放置 fixture（测试夹具）及其他共享资源，
# 以便该目录下的所有测试都能使用它们。
# 测试时不需要从这里import任何东西因为pytest会为你处理
import os
from collections.abc import AsyncGenerator

os.environ["DATABASE_URL"] = ( # 测试时用的数据库,名叫test_blog
    "postgresql+psycopg://bloguser:blogpass@localhost/test_blog"
)
os.environ["S3_BUCKET_NAME"] = "test-bucket"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

# 重写了ACCESS_KEY_ID、SECRET_ACCESS_KEY、REGION
# 这些都要和env里的环境变量相匹配
os.environ["S3_ACCESS_KEY_ID"] = "testing"
os.environ["S3_SECRET_ACCESS_KEY"] = "testing"
os.environ["S3_REGION"] = "us-east-1"

# for boto3 testing
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

import boto3
import pytest
from httpx import ASGITransport, AsyncClient
from moto import mock_aws
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from database import Base, get_db
from main import app

pytest_plugins = ["anyio"] 
# 注册pytest plugins, 使得configuration就在代码边并且可以使用它
# 这个注册可以让我们写测试函数
# 一般pytest只会运行常规同步函数
# 但由于我们的app是异步的，我们希望测试也是异步的
# anyio支持异步后端

# scope="session"意味着这个测试运行整个测试session而不是整个test
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

# 我们不希望测试会触及到我们研发或生产环境下的数据库
# 因为测试会对是数据库数据发生变动
# 此外，测试时的数据库类型和研发的不能一样，
# 这意味着测试将以和研发生产相同的方式执行 
# 因此，测试使用Postgres数据库

@pytest.fixture(scope="session")
def test_engine():
    # 创建测试数据库引擎
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        poolclass=NullPool,
    )
    return engine


@pytest.fixture(scope="session")
async def setup_database(test_engine):
    # 创建表格
    async with test_engine.begin() as conn:
        # 因为SQLAlchemy的create_all函数是同步的
        # 因此这里的run_sync是一个过渡函数
        await conn.run_sync(Base.metadata.create_all)

    yield # where all of the tests will run 

    # 测试完成后，运行这些
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()

# 实现事务回滚模式
# 没有scope这意味着这个fixture是function scoped
# 这意味着它将在每个测试运行
@pytest.fixture
async def db_session(
    test_engine,
    setup_database,
) -> AsyncGenerator[AsyncSession]:
    # 创建连接
    conn = await test_engine.connect()
    trans = await conn.begin()

    # 绑定到特定连接
    # 因此所有测试执行的操作将通过这个连接
    test_async_session = async_sessionmaker(
        bind=conn,
        class_=AsyncSession,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    # 从session制作器那里打开一个session然后给测试
    async with test_async_session() as session:
        try:
            yield session
        finally:
            # 关闭session
            await session.close()
            await trans.rollback()
            await conn.close()


@pytest.fixture
 # moto的AWS是一个同步的上下文，全局修补 boto3
 # 我们异步app仍然再mock里工作
def mocked_aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=os.environ["S3_BUCKET_NAME"])
        yield s3


@pytest.fixture
async def client(
    db_session: AsyncSession,
    mocked_aws,
) -> AsyncGenerator[AsyncClient]:

    async def override_get_db():
        yield db_session # 产生之前写的数据库session

    # 在测试期间，只要 FastAPI 想调用 get_db，
    # 就别调用原来的 get_db，改调用 override_get_db
    app.dependency_overrides[get_db] = override_get_db

    # 产生http请求，但在测试时，我们不想请求真实的服务器，这会很麻烦
    # 这里告诉异步客户端要用不同的运输机制
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()

# 创建测试专用的user，传入的参数都是测试专用
async def create_test_user(
    client: AsyncClient,
    username: str = "testuser",
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> dict:
    # 把测试用户数据传给api用户路由
    response = await client.post(
        "/api/users",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )
    # 断言响应状态码必须是 201；
    # 如果不是，就告诉我“创建用户失败”，并把服务器返回的内容一起打印出来。
    # 第二个字符串参数是失败时的信息
    assert response.status_code == 201, f"Failed to create user: {response.text}"
    return response.json()


async def login_user(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "testpassword123",
) -> str:
    response = await client.post(
        "/api/users/token",
        data={
            "username": email,
            "password": password,
        },
    )
    assert response.status_code == 200, f"Failed to login: {response.text}"
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
