from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Activity, CategoryFactorChange
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
