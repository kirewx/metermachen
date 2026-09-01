from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Activity, CategoryFactorChange
from app.services.factors import FactorResolver
from tests.conftest import make_category


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
