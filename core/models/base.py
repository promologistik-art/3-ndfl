from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from bot.config import DATABASE_URL

engine = None
async_session = None


class Base(DeclarativeBase):
    pass


def _init_engine():
    global engine, async_session
    if engine is None:
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, async_session


async def get_session() -> AsyncSession:
    _, sessionmaker = _init_engine()
    async with sessionmaker() as session:
        yield session


async def init_db():
    eng, _ = _init_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)