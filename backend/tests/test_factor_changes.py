from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Activity, CategoryFactorChange, Challenge
from app.services import bet_metrics
from app.services.challenges import metric_mm
from app.services.factors import FactorResolver
from tests.conftest import login, make_category, make_user


def make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1)):
    ch = CategoryFactorChange(category_id=cat.id, factor=factor, valid_from=valid_from)
    session.add(ch)
    session.commit()
    session.refresh(ch)
    return ch


def test_factor_change_unique_pro_kategorie_und_tag(session):
    cat = make_category(session)
    make_change(session, cat)
    with pytest.raises(IntegrityError):
        make_change(session, cat, factor=20.0)  # gleicher Tag → verboten
    session.rollback()
    # Gleicher Tag bei ANDERER Kategorie ist ok.
    andere = make_category(session, name="Rad", factor=1.0)
    make_change(session, andere)


def test_resolver_ohne_aenderungen_nutzt_urfaktor(session):
    cat = make_category(session)  # factor=4.0
    r = FactorResolver.load(session)
    assert r.factor(cat.id, date(2026, 8, 31)) == 4.0


def test_resolver_stichtag_und_mehrere_aenderungen(session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    make_change(session, cat, factor=20.0, valid_from=date(2026, 10, 1))
    r = FactorResolver.load(session)
    assert r.factor(cat.id, date(2026, 8, 31)) == 30.0  # vor Stichtag: Ur-Faktor
    assert r.factor(cat.id, date(2026, 9, 1)) == 25.0   # genau am Stichtag: neu
    assert r.factor(cat.id, date(2026, 9, 30)) == 25.0
    assert r.factor(cat.id, date(2026, 10, 1)) == 20.0  # jüngste Änderung gewinnt


def test_resolver_mm_und_unbekannte_kategorie(session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    r = FactorResolver.load(session)
    alt = Activity(user_id=1, category_id=cat.id, date=date(2026, 8, 31), distance_km=2.0)
    neu = Activity(user_id=1, category_id=cat.id, date=date(2026, 9, 1), distance_km=2.0)
    assert r.mm(alt) == 60.0
    assert r.mm(neu) == 50.0
    # Unbekannte Kategorie → 0.0 (entspricht dem bisherigen Überspringen).
    fremd = Activity(user_id=1, category_id=999, date=date(2026, 9, 1), distance_km=2.0)
    assert r.mm(fremd) == 0.0


def test_categories_liefern_effektiven_faktor_und_listen(client, session):
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    heute = date.today()
    make_change(session, cat, factor=25.0, valid_from=heute)  # wirksam
    make_change(session, cat, factor=20.0, valid_from=heute + timedelta(days=30))
    r = client.get("/api/categories")
    assert r.status_code == 200
    c = r.json()[0]
    assert c["factor"] == 25.0        # heute gültig
    assert c["base_factor"] == 30.0   # Ur-Faktor
    assert [p["factor"] for p in c["pending_changes"]] == [20.0]
    assert [h["factor"] for h in c["history"]] == [25.0]


def test_categories_ohne_aenderungen_wie_bisher(client, session):
    make_category(session)  # factor=4.0
    c = client.get("/api/categories").json()[0]
    assert c["factor"] == 4.0
    assert c["base_factor"] == 4.0
    assert c["pending_changes"] == [] and c["history"] == []


def test_factor_change_anlegen_nur_admin(client, session):
    make_user(session)
    cat = make_category(session)
    login(client)
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 403


def test_factor_change_anlegen_validierung(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    login(client, username="chef")
    gestern = (date.today() - timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": gestern},
    )
    assert r.status_code == 400  # nicht rückwirkend
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 422  # factor > 0
    r = client.post(
        "/api/categories/999/factor-changes",
        json={"factor": 25.0, "valid_from": date.today().isoformat()},
    )
    assert r.status_code == 404


def test_factor_change_anlegen_und_duplikat(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    login(client, username="chef")
    morgen = (date.today() + timedelta(days=1)).isoformat()
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 25.0, "valid_from": morgen},
    )
    assert r.status_code == 201
    assert r.json()["factor"] == 25.0
    r = client.post(
        f"/api/categories/{cat.id}/factor-changes",
        json={"factor": 20.0, "valid_from": morgen},
    )
    assert r.status_code == 409  # gleicher Tag doppelt


def test_factor_change_loeschen(client, session):
    make_user(session, username="chef", is_admin=True)
    cat = make_category(session)
    heute = make_change(session, cat, factor=25.0, valid_from=date.today())
    alt = make_change(session, cat, factor=28.0, valid_from=date(2026, 1, 1))
    login(client, username="chef")
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/{heute.id}")
    assert r.status_code == 204  # valid_from >= heute → löschbar (Vertipper-Korrektur)
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/{alt.id}")
    assert r.status_code == 409  # Historie ist unantastbar
    r = client.delete(f"/api/categories/{cat.id}/factor-changes/9999")
    assert r.status_code == 404


def test_wett_metriken_rechnen_datumsabhaengig(client, session):
    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2.0))  # 60 MM
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2.0))   # 50 MM
    session.commit()
    assert bet_metrics.scaled_km(
        session, user.id, date(2026, 8, 1), date(2026, 9, 30)
    ) == 110.0


def test_challenge_metrik_rechnet_datumsabhaengig(client, session):
    user = make_user(session)
    cat = make_category(session, name="Schwimmen", factor=30.0, icon="schwimmen")
    make_change(session, cat, factor=25.0, valid_from=date(2026, 9, 1))
    ch = Challenge(
        title="Test", creator_id=user.id, mode="ziel", target=1000.0, metric="mm",
        join_mode="auto", period_start=date(2026, 8, 1), period_end=date(2026, 9, 30),
        status="laufend",
    )
    session.add(ch)
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 8, 31), distance_km=2.0))
    session.add(Activity(user_id=user.id, category_id=cat.id,
                         date=date(2026, 9, 1), distance_km=2.0))
    session.commit()
    assert metric_mm(session, user.id, ch) == 110.0
