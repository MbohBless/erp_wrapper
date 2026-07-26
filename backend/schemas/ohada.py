"""OHADA / SYSCOHADA statutory financial-statement schemas (Pydantic v2).

Système Normal presentation: Compte de résultat (par nature, with the
soldes intermédiaires de gestion) and Bilan (Actif / Passif).
"""

from pydantic import BaseModel


class OhadaLine(BaseModel):
    code: str = ""          # OHADA reference code (TA, RA, XA, AD, …) — blank for headers
    label: str
    amount: float = 0.0
    level: int = 0          # indent level for sub-lines
    kind: str = "line"      # "header" | "line" | "subtotal" | "total"


class OhadaStatement(BaseModel):
    title: str
    subtitle: str = ""
    currency: str = "XAF"
    fiscal_year: str | None = None
    lines: list[OhadaLine]
