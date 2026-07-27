from contextlib import AbstractContextManager
from datetime import datetime
from typing import Callable

from dependency_injector.wiring import Provide
from pydantic import BaseModel
from sqlmodel import Numeric, Session, cast, desc, func, select

from models.recital_session import RecitalSession, SessionStatus
from models.user import User
from utility.cache.stats import CacheKeys, region


class UserLeaderBoard(BaseModel):
    name: str
    created_at: datetime
    total_duration: float
    total_recordings: int


class UserStats(BaseModel):
    global_rank: int
    total_duration: float
    total_recordings: int
    next_higher_duration: float | None


class TotalStats(BaseModel):
    total_duration: float
    total_recordings: int


class StatsRA:
    def __init__(
        self,
        session_factory: Callable[..., AbstractContextManager[Session]],
    ) -> None:
        self.session_factory = session_factory

    @region.cache_on_arguments(namespace={"key_range": CacheKeys.user_stats}, expiration_time=60 * 1)
    def user_stats(self, user_id: str):
        with self.session_factory() as session:

            user_session_totals = (
                select(
                    RecitalSession.user_id,
                    cast(func.sum(RecitalSession.duration).label("total_duration"), Numeric),
                    func.count(RecitalSession.id).label("total_recordings"),
                )
                .filter(RecitalSession.status == SessionStatus.UPLOADED)
                .group_by(RecitalSession.user_id)
                .cte(name="user_session_totals")
            )

            user_session_totals_with_ranks = (
                select(
                    user_session_totals.c.user_id,
                    user_session_totals.c.total_duration,
                    user_session_totals.c.total_recordings,
                    func.dense_rank().over(order_by=user_session_totals.c.total_duration.desc()).label("global_rank"),
                    func.lag(user_session_totals.c.total_duration)
                    .over(order_by=user_session_totals.c.total_duration.desc())
                    .label("next_higher_duration"),
                )
                .select_from(user_session_totals)
                .cte(name="user_session_totals_with_ranks")
            )

            this_user_total = select(
                user_session_totals_with_ranks.c.global_rank,
                user_session_totals_with_ranks.c.total_duration,
                user_session_totals_with_ranks.c.total_recordings,
                user_session_totals_with_ranks.c.next_higher_duration,
            ).filter(user_session_totals_with_ranks.c.user_id == user_id)

            results = session.exec(this_user_total)
            user_stats = results.one_or_none()

            if not user_stats:
                return UserStats(global_rank=0, total_duration=0, total_recordings=0, next_higher_duration=0)

            return UserStats(
                global_rank=user_stats.global_rank,
                total_duration=user_stats.total_duration,
                total_recordings=user_stats.total_recordings,
                next_higher_duration=user_stats.next_higher_duration,
            )

    @region.cache_on_arguments(namespace={"fixed_key": CacheKeys.leaderboard}, expiration_time=60 * 1)
    def leader_board(self, top: int = 10) -> list[UserLeaderBoard]:
        with self.session_factory() as session:

            user_session_totals = (
                select(
                    RecitalSession.user_id,
                    cast(func.sum(RecitalSession.duration).label("total_duration"), Numeric),
                    func.count(RecitalSession.id).label("total_recordings"),
                )
                .filter(RecitalSession.status == SessionStatus.UPLOADED)
                .group_by(RecitalSession.user_id)
                .cte(name="user_session_totals")
            )
            leader_board_selectable = (
                select(
                    User.name,
                    User.created_at,
                    user_session_totals.c.total_duration,
                    user_session_totals.c.total_recordings,
                )
                .join(User)
                .order_by(user_session_totals.c.total_duration.desc())
                .limit(top)
            )

            results = session.exec(leader_board_selectable)

            return results.all()

    @region.cache_on_arguments(namespace={"fixed_key": CacheKeys.totals}, expiration_time=60 * 10)
    def totals(self) -> TotalStats:
        with self.session_factory() as session:

            system_totals = select(
                cast(func.sum(RecitalSession.duration).label("total_duration"), Numeric),
                func.count(RecitalSession.id).label("total_recordings"),
            ).filter(RecitalSession.status == SessionStatus.UPLOADED)

            results = session.exec(system_totals)
            totals = results.one_or_none()

            if totals is not None:
                # SUM() with no GROUP BY over zero matching rows still returns exactly one
                # row, with SUM(duration) = NULL (not zero rows) - so total_duration can be
                # None here even though `totals` itself isn't. Only ever hit on an empty/fresh
                # database (e.g. a brand-new preview channel with no uploaded sessions yet).
                return TotalStats(
                    total_duration=totals.total_duration or 0,
                    total_recordings=totals.total_recordings or 0,
                )
            else:
                return TotalStats(total_duration=0, total_recordings=0)
