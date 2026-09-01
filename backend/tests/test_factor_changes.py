from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import CategoryFactorChange
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
