from sqlmodel import Session, select

from . import auth
from .models import Category, Season, User

DEFAULT_CATEGORIES = [
    # (Name, Faktor, Farbe, Icon, Standard-km)
    ("Joggen", 4.0, "#e74c3c", "laufen", 5.0),
    ("Laufen", 4.0, "#c0392b", "laufen", 5.0),
    ("Spazieren", 3.0, "#f1c40f", "gehen", 5.0),
    ("Wandern", 3.0, "#27ae60", "wandern", 10.0),
    ("Schwimmen", 10.0, "#9b59b6", "schwimmen", 1.0),
    ("Radfahren", 1.0, "#3498db", "rad", 20.0),
    ("Tanzen", 3.0, "#e67e22", "tanzen", 5.0),
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
        for name, factor, color, icon, default_km in DEFAULT_CATEGORIES:
            session.add(
                Category(name=name, factor=factor, color=color, icon=icon, default_km=default_km)
            )
    if session.exec(select(Season).where(Season.year == year)).first() is None:
        session.add(Season(year=year, goal_km=1000.0))
    session.commit()
