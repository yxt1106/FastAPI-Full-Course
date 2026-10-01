from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import settings

# T5: Engine 本身不是数据库。它是负责管理数据库连接的 SQLAlchemy 组件
engine = create_async_engine(settings.database_url)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass

# get_db: 依赖函数给路由提供session，是一个生成器
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
