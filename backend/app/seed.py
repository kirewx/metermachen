from sqlmodel import Session, select

from . import auth
from .models import Category, Season, User

DEFAULT_CATEGORIES = [
    ("Joggen", 4.0, "#e74c3c", "🏃"),
    ("Laufen", 4.0, "#c0392b", "👟"),
    ("Spazieren", 3.0, "#f1c40f", "🚶"),
    ("Wandern", 3.0, "#27ae60", "🥾"),
    ("Schwimmen", 10.0, "#9b59b6", "🏊"),
    ("Radfahren", 1.0, "#3498db", "🚴"),
    ("Tanzen", 3.0, "#e67e22", "💃"),
]


def seed_all(session: Session, admin_user: str, admin_password: str, year: int) -> None:
    if session.exec(select(User)).first() is None:
        session.add(
            User(
                username=admin_user,
                password_hash=auth.hash_password(admin_password),
                display_name=admin_user.capitalize(),
                is_admin=True,
            )
        )
    if session.exec(select(Category)).first() is None:
        for name, factor, color, emoji in DEFAULT_CATEGORIES:
            session.add(Category(name=name, factor=factor, color=color, icon_emoji=emoji))
    if session.exec(select(Season).where(Season.year == year)).first() is None:
        session.add(Season(year=year, goal_km=1000.0))
    session.commit()
