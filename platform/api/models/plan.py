"""Subscription plans: the feature set and limits a tenant is entitled to.

``features`` is the contract between billing and the product: the tenant app
reads the same list through tenant resolution and gates routes on it with
``require_feature(...)``. Selling a capability is therefore a data change here,
not a code change there.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# Capability names the tenant app knows how to gate on.
FEATURE_BRANDING = "branding"
FEATURE_DASHBOARD_LAYOUT = "dashboard_layout"
FEATURE_CUSTOM_DOMAIN = "custom_domain"
FEATURE_REPORTS = "reports"
FEATURE_BUDGET = "budget"
FEATURE_DEDICATED_ERP = "dedicated_erp"

KNOWN_FEATURES = (
    FEATURE_BRANDING,
    FEATURE_DASHBOARD_LAYOUT,
    FEATURE_CUSTOM_DOMAIN,
    FEATURE_REPORTS,
    FEATURE_BUDGET,
    FEATURE_DEDICATED_ERP,
)


class Plan(Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    # JSON array of feature names drawn from KNOWN_FEATURES.
    features_json: Mapped[str] = mapped_column(Text, default="[]")
    max_users: Mapped[int] = mapped_column(Integer, default=10)
    # Monthly price in XAF — the currency the business actually bills in.
    price_xaf: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# Seeded on first start so a fresh control plane is immediately usable.
DEFAULT_PLANS = (
    {
        "code": "starter",
        "name": "Starter",
        "description": "Single warehouse, core distribution workflow.",
        "features": [FEATURE_REPORTS],
        "max_users": 5,
        "price_xaf": 45000,
    },
    {
        "code": "business",
        "name": "Business",
        "description": "Branding, budgets and the full reporting suite.",
        "features": [FEATURE_REPORTS, FEATURE_BUDGET, FEATURE_BRANDING],
        "max_users": 25,
        "price_xaf": 120000,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "White-label, custom dashboards and your own domain.",
        "features": [
            FEATURE_REPORTS,
            FEATURE_BUDGET,
            FEATURE_BRANDING,
            FEATURE_DASHBOARD_LAYOUT,
            FEATURE_CUSTOM_DOMAIN,
        ],
        "max_users": 100,
        "price_xaf": 300000,
    },
    {
        "code": "dedicated",
        "name": "Dedicated instance",
        "description": "Isolated ERPNext stack, managed by us on your domain.",
        "features": list(KNOWN_FEATURES),
        "max_users": 500,
        "price_xaf": 750000,
    },
)
