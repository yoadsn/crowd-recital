from contextlib import AbstractContextManager
from typing import Callable, Iterator

from sqlmodel import Session, select

from models.user import User


class UsersRA:

    def __init__(self, session_factory: Callable[..., AbstractContextManager[Session]]) -> None:
        self.session_factory = session_factory

    def get_all(self) -> Iterator[User]:
        with self.session_factory() as session:
            return session.exec(select(User))

    def get_by_id(self, id: str) -> User:
        with self.session_factory() as session:
            results = session.exec(select(User).filter(User.id == id))
            return results.first()

    def get_by_email(self, email: str) -> User:
        with self.session_factory() as session:
            results = session.exec(select(User).filter(User.email == email))
            return results.first()

    def upsert(self, user: User) -> None:
        with self.session_factory() as session:
            session.merge(user)
            session.commit()
            return user
