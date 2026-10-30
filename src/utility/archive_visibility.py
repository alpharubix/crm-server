from typing import Any
from sqlalchemy import and_, or_, exists, select
from sqlalchemy.orm import Query

from src.models.account import Account
from src.models.deal import Deal
from src.models.contact import Contact
from src.models.ticket import Ticket
from src.models.revenue import Revenue
from src.models.account_task import AccountTask
from src.models.deal_task import DealTask
from src.models.deal_document import DealDocument


def active_account_condition():
    """Account is visible only if its own archived_at IS NULL."""
    return Account.archived_at.is_(None)


def active_contact_condition():
    """
    Contact is visible only if:
    1. contact.archived_at IS NULL
    2. parent account.archived_at IS NULL
    """
    account_active_subq = exists().where(
        and_(
            Account.id == Contact.account_id,
            Account.archived_at.is_(None),
        )
    )
    # If account_id is None, contact is visible if its own archived_at is NULL
    return and_(
        Contact.archived_at.is_(None),
        or_(Contact.account_id.is_(None), account_active_subq),
    )


def active_deal_condition():
    """
    Deal is visible only if:
    1. deal.archived_at IS NULL
    2. parent account.archived_at IS NULL
    """
    account_active_subq = exists().where(
        and_(
            Account.id == Deal.account_id,
            Account.archived_at.is_(None),
        )
    )
    return and_(
        Deal.archived_at.is_(None),
        or_(Deal.account_id.is_(None), account_active_subq),
    )


def active_ticket_condition():
    """
    Ticket is visible only if:
    1. ticket.archived_at IS NULL
    2. parent deal.archived_at IS NULL
    3. deal's parent account.archived_at IS NULL
    4. direct account_id (if present) account.archived_at IS NULL
    """
    deal_and_account_active_subq = exists().where(
        and_(
            Deal.id == Ticket.deal_id,
            Deal.archived_at.is_(None),
            exists().where(
                and_(
                    Account.id == Deal.account_id,
                    Account.archived_at.is_(None),
                )
            ),
        )
    )
    direct_account_active_subq = exists().where(
        and_(
            Account.id == Ticket.account_id,
            Account.archived_at.is_(None),
        )
    )
    return and_(
        Ticket.archived_at.is_(None),
        deal_and_account_active_subq,
        or_(Ticket.account_id.is_(None), direct_account_active_subq),
    )


def active_revenue_condition():
    """
    Revenue is visible only if:
    1. revenue.archived_at IS NULL
    2. parent deal.archived_at IS NULL
    3. deal's parent account.archived_at IS NULL
    """
    deal_and_account_active_subq = exists().where(
        and_(
            Deal.id == Revenue.deal_id,
            Deal.archived_at.is_(None),
            exists().where(
                and_(
                    Account.id == Deal.account_id,
                    Account.archived_at.is_(None),
                )
            ),
        )
    )
    return and_(
        Revenue.archived_at.is_(None),
        deal_and_account_active_subq,
    )


def active_account_task_condition():
    """
    AccountTask is visible only if:
    1. account_task.archived_at IS NULL
    2. parent account.archived_at IS NULL
    """
    account_active_subq = exists().where(
        and_(
            Account.id == AccountTask.account_id,
            Account.archived_at.is_(None),
        )
    )
    return and_(
        AccountTask.archived_at.is_(None),
        or_(AccountTask.account_id.is_(None), account_active_subq),
    )


def active_deal_task_condition():
    """
    DealTask is visible only if:
    1. deal_task.archived_at IS NULL
    2. parent deal.archived_at IS NULL
    3. deal's parent account.archived_at IS NULL
    """
    deal_and_account_active_subq = exists().where(
        and_(
            Deal.id == DealTask.deal_id,
            Deal.archived_at.is_(None),
            exists().where(
                and_(
                    Account.id == Deal.account_id,
                    Account.archived_at.is_(None),
                )
            ),
        )
    )
    return and_(
        DealTask.archived_at.is_(None),
        deal_and_account_active_subq,
    )


def active_deal_document_condition():
    """
    DealDocument is visible only if:
    1. deal_document.archived_at IS NULL
    2. parent deal.archived_at IS NULL
    3. deal's parent account.archived_at IS NULL
    """
    deal_and_account_active_subq = exists().where(
        and_(
            Deal.id == DealDocument.deal_id,
            Deal.archived_at.is_(None),
            exists().where(
                and_(
                    Account.id == Deal.account_id,
                    Account.archived_at.is_(None),
                )
            ),
        )
    )
    return and_(
        DealDocument.archived_at.is_(None),
        deal_and_account_active_subq,
    )


def is_super_admin(role: str | None) -> bool:
    """Helper to check if a normalized role string has Super Admin privileges."""
    if not role:
        return False
    norm = str(role).strip().lower().replace(" ", "_")
    return norm in ("super_admin", "superadmin")
