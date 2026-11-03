"""Höhenmeter (Spec 2026-11-03): MM = (km + hm / 100) × Faktor, wenn die
Kategorie am Aktivitätsdatum Höhenmeter zählt. Zeitversioniert wie Faktoren
(CategoryElevationChange) — weder Admin-Schalter noch ein später Deploy
wirken rückwirkend."""

import json
from datetime import date, timedelta

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

from app.db import migrate
from app.models import Activity, Category, CategoryElevationChange, CategoryFactorChange
from app.services.factors import HM_AB, FactorResolver, elevation_start, set_counts_elevation
from tests.conftest import login, make_category, make_user

TAG = HM_AB + timedelta(days=10)


def act(session, user, cat, *, km=10.0, hm=500.0, on=TAG):
    a = Activity(user_id=user.id, category_id=cat.id, date=on, distance_km=km,
                 elevation_m=hm)
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


def hm_ab(session, cat, on=HM_AB, value=True):
    session.add(CategoryElevationChange(category_id=cat.id, counts_elevation=value, valid_from=on))
    session.commit()


def test_hm_zaehlen_als_km_mal_faktor(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    hm_ab(session, lauf)
    r = FactorResolver.load(session)
    # 10 km + 500 hm = 15 km × 4
    assert r.mm(act(session, user, lauf)) == 60.0
    # 100 hm beim Laufen = 4 MM
    assert r.mm(act(session, user, lauf, km=0.0, hm=100.0)) == 4.0


def test_hm_erst_ab_stichtag(session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    hm_ab(session, lauf)
    alt = act(session, user, lauf, on=HM_AB - timedelta(days=1))
    assert FactorResolver.load(session).mm(alt) == 40.0


def test_ohne_aenderung_keine_hm(session):
    user = make_user(session)
    ebike = make_category(session, name="EBike", factor=0.5)
    assert FactorResolver.load(session).mm(act(session, user, ebike)) == 5.0


def test_ohne_hm_unveraendert(session):
    user = make_user(session)
    rad = make_category(session, name="Rad", factor=1.0)
    hm_ab(session, rad)
    assert FactorResolver.load(session).mm(act(session, user, rad, hm=None)) == 10.0


def test_abschalten_wirkt_nicht_rueckwirkend(session):
    user = make_user(session)
    rad = make_category(session, name="Rad", factor=1.0)
    hm_ab(session, rad)
    vorher = act(session, user, rad, on=TAG)
    set_counts_elevation(session, rad, False, today=TAG + timedelta(days=1))
    session.commit()
    nachher = act(session, user, rad, on=TAG + timedelta(days=1))
    r = FactorResolver.load(session)
    assert r.mm(vorher) == 15.0  # bleibt
    assert r.mm(nachher) == 10.0


def test_schalter_vor_stichtag_ersetzt_geplante_aenderung(session):
    rad = make_category(session, name="Rad", factor=1.0)
    hm_ab(session, rad)  # geplant ab HM_AB
    vorher = HM_AB - timedelta(days=1)
    set_counts_elevation(session, rad, False, today=vorher)
    session.commit()
    assert session.exec(select(CategoryElevationChange)).all() == []
    set_counts_elevation(session, rad, True, today=vorher)
    session.commit()
    rows = session.exec(select(CategoryElevationChange)).all()
    assert [(r.counts_elevation, r.valid_from) for r in rows] == [(True, HM_AB)]


def test_activity_api_zeigt_mm_mit_hm(client, session):
    user = make_user(session)
    lauf = make_category(session, name="Laufen", factor=4.0)
    hm_ab(session, lauf)
    act(session, user, lauf, km=5.0, hm=250.0)
    login(client)
    body = client.get(f"/api/activities?year={TAG.year}").json()
    assert [a["scaled_km"] for a in body] == [30.0]


def test_admin_schalter_legt_datierte_aenderung_an(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session, name="Rad", factor=1.0)
    hm_ab(session, cat)
    login(client, username="chef")
    body = client.get("/api/categories").json()[0]
    assert body["counts_elevation"] is True
    assert body["base_counts_elevation"] is False
    assert body["elevation_changes"] == [{"counts_elevation": True, "valid_from": HM_AB.isoformat()}]

    r = client.patch(f"/api/categories/{cat.id}", json={"counts_elevation": False})
    assert r.status_code == 200
    assert r.json()["counts_elevation"] is False
    start = elevation_start()
    rows = session.exec(select(CategoryElevationChange)).all()
    if start > HM_AB:  # nach dem Stichtag: alte Änderung bleibt Historie
        assert [(x.counts_elevation, x.valid_from) for x in rows] == [
            (True, HM_AB), (False, start),
        ]
    else:  # davor: geplante Änderung wird ersetzt
        assert rows == []


def test_neue_kategorie_bekommt_passenden_hm_standard(client, session):
    make_user(session, username="chef", is_admin=True)
    login(client, username="chef")

    def neu(**kw):
        body = {"name": "X", "factor": 1.0, "color": "#000000", **kw}
        out = client.post("/api/categories", json=body).json()
        assert out["base_counts_elevation"] is False  # nie rückwirkend
        return out["counts_elevation"]

    assert neu(name="Trailrun", icon="laufen", strava_sport_types=["TrailRun"]) is True
    assert neu(name="Yoga", icon="medaille") is False
    assert neu(name="Aquajogging", icon="schwimmen") is False
    assert neu(name="Indoor-Rad", icon="rad") is False
    assert neu(name="Yoga 2", icon="medaille", counts_elevation=True) is True


def _alte_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:  # Bestands-DB ohne die neue Spalte
        conn.execute(text("ALTER TABLE category DROP COLUMN counts_elevation"))
        for name, factor, icon, sports in [
            ("EBike", 0.5, "rad", ["EBikeRide"]),
            ("Wandern", 3.0, "wandern", ["Hike"]),
            ("Radfahren", 1.0, "rad", ["Ride"]),
            ("Joggen", 4.0, "laufen", ["Run"]),
            ("Spazieren", 2.0, "gehen", ["Walk"]),
            ("Schwimmen", 30.0, "schwimmen", ["Swim"]),
            ("Tanzen", 3.0, "tanzen", []),
            ("Tennis", 4.0, "medaille", ["Tennis"]),
            ("Ski/Snowboard", 1.5, "ski", ["Snowboard", "AlpineSki"]),
            ("Spinning", 1.0, "rad", ["VirtualRide"]),
        ]:
            conn.execute(text(
                "INSERT INTO category (name, factor, color, icon, default_km, is_active, "
                "strava_sport_types) VALUES (:n, :f, '#000000', :i, 10, 1, :s)"
            ), {"n": name, "f": factor, "i": icon, "s": json.dumps(sports)})
    return engine


def test_migration_hm_nur_draussen_und_wandern_neuer_faktor(tmp_path):
    engine = _alte_db(tmp_path)
    migrate(engine)
    migrate(engine)  # idempotent
    start = elevation_start()
    with Session(engine) as s:
        cats = {c.id: c for c in s.exec(select(Category)).all()}
        assert not any(c.counts_elevation for c in cats.values())  # nie rückwirkend
        hm = s.exec(select(CategoryElevationChange)).all()
        assert {cats[h.category_id].name for h in hm} == {
            "Wandern", "Radfahren", "Joggen", "Spazieren",
        }
        assert {h.valid_from for h in hm} == {start}
        changes = s.exec(select(CategoryFactorChange)).all()
        assert [(cats[c.category_id].name, c.factor, c.valid_from) for c in changes] == [
            ("Wandern", 2.5, start)
        ]


def test_migration_nach_stichtag_startet_am_deploy_tag(tmp_path, monkeypatch):
    import app.services.factors as factors

    spaet = HM_AB + timedelta(days=3)

    class SpaeterTag(date):
        @classmethod
        def today(cls):
            return spaet

    monkeypatch.setattr(factors, "date_type", SpaeterTag)
    engine = _alte_db(tmp_path)
    migrate(engine)
    with Session(engine) as s:
        assert {h.valid_from for h in s.exec(select(CategoryElevationChange)).all()} == {spaet}
        assert {c.valid_from for c in s.exec(select(CategoryFactorChange)).all()} == {spaet}


def test_strava_indoor_ohne_hm(session):
    from app.services.strava import _derive_fields

    make_category(session, name="Radfahren", factor=1.0)
    base = {"sport_type": "Ride", "distance": 30000, "total_elevation_gain": 400,
            "start_date_local": "2026-11-05T08:00:00Z"}
    assert _derive_fields(session, base)["elevation_m"] == 400.0
    assert _derive_fields(session, {**base, "trainer": True})["elevation_m"] is None
    assert _derive_fields(session, {**base, "sport_type": "VirtualRide"})["elevation_m"] is None
