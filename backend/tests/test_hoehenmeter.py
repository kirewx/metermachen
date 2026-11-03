"""Höhenmeter zählen ab HM_AB: MM = (km + hm / 100) × Faktor, außer bei
Kategorien mit counts_elevation=False (E-Bike). Nie rückwirkend."""

import json
from datetime import timedelta

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import migrate
from app.models import Activity, Category, CategoryFactorChange
from app.services.factors import HM_AB, FactorResolver
from tests.conftest import login, make_category, make_user


def act(session, user, cat, *, km=10.0, hm=500.0, on=HM_AB):
    a = Activity(user_id=user.id, category_id=cat.id, date=on, distance_km=km,
                 elevation_m=hm)
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


def test_hm_zaehlen_als_km_mal_faktor(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    r = FactorResolver.load(session)
    # 10 km + 500 hm = 15 km × 4
    assert r.mm(act(session, user, lauf)) == 60.0
    # 100 hm beim Laufen = 4 MM
    assert r.mm(act(session, user, lauf, km=0.0, hm=100.0)) == 4.0


def test_hm_nicht_rueckwirkend(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    alt = act(session, user, lauf, on=HM_AB - timedelta(days=1))
    assert FactorResolver.load(session).mm(alt) == 40.0


def test_ebike_ohne_hm(session):
    user = make_user(session)
    ebike = make_category(session, name="EBike", factor=0.5)
    ebike.counts_elevation = False
    session.add(ebike)
    session.commit()
    assert FactorResolver.load(session).mm(act(session, user, ebike)) == 5.0


def test_ohne_hm_unveraendert(session):
    user = make_user(session)
    rad = make_category(session, name="Rad", factor=1.0)
    assert FactorResolver.load(session).mm(act(session, user, rad, hm=None)) == 10.0


def test_activity_api_zeigt_mm_mit_hm(client, session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    act(session, user, lauf, km=5.0, hm=250.0)
    login(client)
    body = client.get(f"/api/activities?year={HM_AB.year}").json()
    assert [a["scaled_km"] for a in body] == [30.0]


def test_admin_kann_hm_je_kategorie_abschalten(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session, name="Rad", factor=1.0)
    login(client, username="chef")
    body = client.get("/api/categories").json()[0]
    assert body["counts_elevation"] is True
    assert body["elevation_from"] == HM_AB.isoformat()
    r = client.patch(f"/api/categories/{cat.id}", json={"counts_elevation": False})
    assert r.status_code == 200
    assert r.json()["counts_elevation"] is False


def test_migration_ebike_aus_und_wandern_neuer_faktor(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:  # Bestands-DB ohne die neue Spalte
        conn.execute(text("ALTER TABLE category DROP COLUMN counts_elevation"))
        for name, factor, icon, sports in [
            ("EBike", 0.5, "rad", ["EBikeRide"]),
            ("Wandern", 3.0, "wandern", ["Hike"]),
            ("Radfahren", 1.0, "rad", ["Ride"]),
        ]:
            conn.execute(text(
                "INSERT INTO category (name, factor, color, icon, default_km, is_active, "
                "strava_sport_types) VALUES (:n, :f, '#000000', :i, 10, 1, :s)"
            ), {"n": name, "f": factor, "i": icon, "s": json.dumps(sports)})
    migrate(engine)
    migrate(engine)  # idempotent
    with Session(engine) as s:
        cats = {c.name: c for c in s.exec(select(Category)).all()}
        assert cats["EBike"].counts_elevation is False
        assert cats["Radfahren"].counts_elevation is True
        changes = s.exec(select(CategoryFactorChange)).all()
        assert [(c.category_id, c.factor, c.valid_from) for c in changes] == [
            (cats["Wandern"].id, 2.5, HM_AB)
        ]
