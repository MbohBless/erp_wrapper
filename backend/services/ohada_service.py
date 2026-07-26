"""OHADA / SYSCOHADA statutory statements from SYSCOHADA trial-balance data.

Builds the **Compte de résultat** (par nature, with the soldes intermédiaires
de gestion) and the **Bilan** (Système Normal, list presentation) by aggregating
account balances on their SYSCOHADA account-number prefix.

Notes / simplifications (documented on the statements):
- Covers the principal lines of the Système Normal; rarely-used lines resolve to
  zero when no matching account carries a balance.
- Accounts are classified by their natural class; balance-sign reclassification
  (e.g. a débit balance on a 44 État account) is simplified.
"""

from __future__ import annotations

import re

from schemas.finance import BookResult
from schemas.ohada import OhadaLine, OhadaStatement


class _Ledger:
    """Aggregates {number, debit, credit} balances by account-number prefix."""

    def __init__(self, accounts: list[dict]) -> None:
        self.accounts = accounts

    def _match(self, prefixes: tuple[str, ...]) -> list[dict]:
        return [a for a in self.accounts if a["number"].startswith(prefixes)]

    def debit(self, *prefixes: str) -> float:
        """Net débit (positive for assets/charges)."""
        return round(sum(a["debit"] - a["credit"] for a in self._match(prefixes)), 2)

    def credit(self, *prefixes: str) -> float:
        """Net crédit (positive for products/liabilities/equity)."""
        return round(sum(a["credit"] - a["debit"] for a in self._match(prefixes)), 2)

    def debit_only(self, *prefixes: str) -> float:
        """Sum of per-account net-débit balances (créances side of mixed classes)."""
        return round(sum(max(a["debit"] - a["credit"], 0) for a in self._match(prefixes)), 2)

    def credit_only(self, *prefixes: str) -> float:
        """Sum of per-account net-crédit balances (dettes side of mixed classes)."""
        return round(sum(max(a["credit"] - a["debit"], 0) for a in self._match(prefixes)), 2)


def _r(x: float) -> float:
    return round(x, 2)


def is_smt(regime: str | None) -> bool:
    """True for the Système Minimal de Trésorerie."""
    r = (regime or "").strip().lower()
    return r == "smt" or "minimal" in r


# ---------------------------------------------------------------------------
# Compte de résultat (par nature) — soldes intermédiaires de gestion
# ---------------------------------------------------------------------------
def compte_de_resultat(
    accounts: list[dict], fiscal_year: str | None = None, regime: str | None = None
) -> OhadaStatement:
    if is_smt(regime):
        return _smt_compte_de_resultat(accounts, fiscal_year)
    L = _Ledger(accounts)

    ventes_march = L.credit("701")
    achats_march = L.debit("601")
    var_stock_march = L.debit("6031")
    marge_com = _r(ventes_march - achats_march - var_stock_march)

    ventes_prod = L.credit("702", "703", "704", "705", "706")
    prod_stockee = L.credit("73")
    prod_immob = L.credit("72")
    production = _r(ventes_prod + prod_stockee + prod_immob)

    ca = L.credit("70")
    autres_produits = L.credit("75")
    subventions = L.credit("71")

    achats_mp = L.debit("602")
    var_mp = L.debit("6032")
    autres_achats = L.debit("604", "605", "608")
    var_autres = L.debit("6033", "6035")
    transport = L.debit("61")
    services_ext = L.debit("62", "63")
    consommations = _r(achats_mp + var_mp + autres_achats + var_autres + transport + services_ext)

    valeur_ajoutee = _r(marge_com + production + autres_produits - consommations)

    impots_taxes = L.debit("64")
    charges_personnel = L.debit("66")
    ebe = _r(valeur_ajoutee + subventions - impots_taxes - charges_personnel)

    reprises_expl = L.credit("781", "791", "798")
    autres_charges = L.debit("65")
    dotations_expl = L.debit("681", "691")
    resultat_expl = _r(ebe + reprises_expl - autres_charges - dotations_expl)

    revenus_fin = L.credit("77", "787", "797")
    frais_fin = L.debit("67", "687", "697")
    resultat_fin = _r(revenus_fin - frais_fin)

    rao = _r(resultat_expl + resultat_fin)

    produits_hao = L.credit("82", "84", "86", "88")
    charges_hao = L.debit("81", "83", "85")
    resultat_hao = _r(produits_hao - charges_hao)

    participation = L.debit("87")
    impot_resultat = L.debit("89")
    resultat_net = _r(rao + resultat_hao - participation - impot_resultat)

    def line(code, label, amount, kind="line", level=0):
        return OhadaLine(code=code, label=label, amount=_r(amount), kind=kind, level=level)

    lines = [
        line("", "ACTIVITÉ D'EXPLOITATION", 0, kind="header"),
        line("TA", "Ventes de marchandises", ventes_march),
        line("RA", "Achats de marchandises", -achats_march),
        line("RB", "Variation de stocks de marchandises", -var_stock_march),
        line("XA", "MARGE COMMERCIALE", marge_com, kind="subtotal"),
        line("TB", "Ventes de produits fabriqués & services", ventes_prod),
        line("TC", "Production stockée / immobilisée", _r(prod_stockee + prod_immob)),
        line("TH", "Autres produits", autres_produits),
        line("RC", "Achats de matières & autres achats", -_r(achats_mp + autres_achats)),
        line("RD", "Variation de stocks", -_r(var_mp + var_autres)),
        line("RG", "Transports", -transport),
        line("RH", "Services extérieurs", -services_ext),
        line("XB", "VALEUR AJOUTÉE", valeur_ajoutee, kind="subtotal"),
        line("RK", "Charges de personnel", -charges_personnel),
        line("TG", "Subventions d'exploitation", subventions),
        line("RI", "Impôts et taxes", -impots_taxes),
        line("XC", "EXCÉDENT BRUT D'EXPLOITATION (EBE)", ebe, kind="subtotal"),
        line("TJ", "Reprises de provisions & transferts de charges", reprises_expl),
        line("RJ", "Autres charges", -autres_charges),
        line("RL", "Dotations aux amortissements & provisions", -dotations_expl),
        line("XD", "RÉSULTAT D'EXPLOITATION", resultat_expl, kind="subtotal"),
        line("", "ACTIVITÉ FINANCIÈRE", 0, kind="header"),
        line("TK", "Revenus financiers", revenus_fin),
        line("RM", "Frais financiers", -frais_fin),
        line("XE", "RÉSULTAT FINANCIER", resultat_fin, kind="subtotal"),
        line("XF", "RÉSULTAT DES ACTIVITÉS ORDINAIRES (RAO)", rao, kind="subtotal"),
        line("", "HORS ACTIVITÉS ORDINAIRES (HAO)", 0, kind="header"),
        line("TN", "Produits HAO", produits_hao),
        line("RO", "Charges HAO", -charges_hao),
        line("XG", "RÉSULTAT HAO", resultat_hao, kind="subtotal"),
        line("RP", "Participation des travailleurs", -participation),
        line("RQ", "Impôts sur le résultat", -impot_resultat),
        line("XH", "RÉSULTAT NET", resultat_net, kind="total"),
    ]
    return OhadaStatement(
        title="Compte de Résultat",
        subtitle="OHADA · Système Normal — charges et produits par nature",
        fiscal_year=fiscal_year,
        lines=lines,
    )


# ---------------------------------------------------------------------------
# Bilan (Système Normal, list presentation)
# ---------------------------------------------------------------------------
def bilan(
    accounts: list[dict], fiscal_year: str | None = None, regime: str | None = None
) -> OhadaStatement:
    if is_smt(regime):
        return _smt_bilan(accounts, fiscal_year)
    L = _Ledger(accounts)

    # ACTIF
    immob_incorp = L.debit("21", "281", "291", "2181", "2191")
    immob_corp = L.debit("22", "23", "24", "282", "283", "284", "292", "293", "294")
    immob_fin = L.debit("26", "27", "296", "297")
    actif_immobilise = _r(immob_incorp + immob_corp + immob_fin)

    stocks = L.debit("31", "32", "33", "34", "35", "36", "38", "39")
    # Per-account sign split so client receivables aren't cancelled by supplier
    # payables (both live in class 4).
    _class4 = ("40", "41", "42", "43", "44", "45", "46", "47", "48", "49")
    creances = L.debit_only(*_class4)
    actif_circulant = _r(stocks + creances)

    tresorerie_actif = L.debit("50", "51", "52", "53", "54", "57", "58")
    tresorerie_actif = _r(max(tresorerie_actif, 0))

    total_actif = _r(actif_immobilise + actif_circulant + tresorerie_actif)

    # PASSIF
    resultat_net = compte_de_resultat(accounts).lines[-1].amount
    capital = L.credit("101", "102", "103", "104", "105", "108", "109")
    primes_reserves = L.credit("11", "12", "14", "15")
    report_nouveau = L.credit("12")
    capitaux_propres = _r(capital + primes_reserves + resultat_net)

    dettes_financieres = L.credit("16", "17", "18", "19")
    ressources_stables = _r(capitaux_propres + dettes_financieres)

    dettes_circulantes = L.credit_only(*_class4)

    tresorerie_passif = L.credit("561", "564", "565", "566", "52")
    tresorerie_passif = _r(max(tresorerie_passif, 0))

    total_passif = _r(ressources_stables + dettes_circulantes + tresorerie_passif)

    def line(code, label, amount, kind="line", level=0):
        return OhadaLine(code=code, label=label, amount=_r(amount), kind=kind, level=level)

    lines = [
        line("", "ACTIF", 0, kind="header"),
        line("AD", "Actif immobilisé", actif_immobilise, kind="subtotal"),
        line("AE", "Immobilisations incorporelles", immob_incorp, level=1),
        line("AF", "Immobilisations corporelles", immob_corp, level=1),
        line("AG", "Immobilisations financières", immob_fin, level=1),
        line("BA", "Actif circulant", actif_circulant, kind="subtotal"),
        line("BB", "Stocks et en-cours", stocks, level=1),
        line("BG", "Créances et emplois assimilés", creances, level=1),
        line("BT", "Trésorerie-Actif", tresorerie_actif, kind="subtotal"),
        line("BZ", "TOTAL ACTIF", total_actif, kind="total"),
        line("", "PASSIF", 0, kind="header"),
        line("CP", "Capitaux propres", capitaux_propres, kind="subtotal"),
        line("CA", "Capital", capital, level=1),
        line("CD", "Réserves, primes & report à nouveau", _r(primes_reserves), level=1),
        line("CI", "Résultat net de l'exercice", resultat_net, level=1),
        line("DA", "Dettes financières & ressources assimilées", dettes_financieres, kind="subtotal"),
        line("DP", "Passif circulant", dettes_circulantes, kind="subtotal"),
        line("DT", "Trésorerie-Passif", tresorerie_passif, kind="subtotal"),
        line("DZ", "TOTAL PASSIF", total_passif, kind="total"),
    ]
    return OhadaStatement(
        title="Bilan",
        subtitle="OHADA · Système Normal — présentation en liste",
        fiscal_year=fiscal_year,
        lines=lines,
    )


# ---------------------------------------------------------------------------
# Tableau des Flux de Trésorerie (TFT) — direct method by counterpart class
# ---------------------------------------------------------------------------
def _counter_class(against: str | None) -> str:
    """Leading class digit of the first counter-account in a GL 'against' string."""
    if not against:
        return ""
    first = str(against).split(",")[0].strip()
    m = re.match(r"(\d)", first)
    return m.group(1) if m else ""


def tableau_flux(book: BookResult, fiscal_year: str | None = None) -> OhadaStatement:
    """OHADA cash-flow statement (direct method).

    Each treasury (class 5) GL movement is attributed to an activity by the
    class of its counter-account: class 2 → investissement, class 1 →
    financement, other → opérationnel. Internal transfers between treasury
    accounts (counterpart class 5) net to zero and are skipped.
    """
    operationnel = investissement = financement = 0.0
    for e in book.entries:
        cls = _counter_class(e.against)
        if cls == "5":  # treasury-to-treasury transfer
            continue
        flow = _r(e.debit - e.credit)  # inflow positive
        if cls == "2":
            investissement += flow
        elif cls == "1":
            financement += flow
        else:
            operationnel += flow

    operationnel, investissement, financement = _r(operationnel), _r(investissement), _r(financement)
    variation = _r(operationnel + investissement + financement)
    ouverture = _r(book.opening)
    cloture = _r(ouverture + variation)

    def line(code, label, amount, kind="line", level=0):
        return OhadaLine(code=code, label=label, amount=_r(amount), kind=kind, level=level)

    lines = [
        line("ZA", "Flux de trésorerie des activités opérationnelles", operationnel, kind="subtotal"),
        line("ZB", "Flux de trésorerie des activités d'investissement", investissement, kind="subtotal"),
        line("ZC", "Flux de trésorerie des activités de financement", financement, kind="subtotal"),
        line("ZE", "VARIATION DE LA TRÉSORERIE NETTE DE LA PÉRIODE", variation, kind="total"),
        line("", "TRÉSORERIE", 0, kind="header"),
        line("ZF", "Trésorerie nette au début de l'exercice", ouverture),
        line("ZG", "Trésorerie nette à la clôture de l'exercice", cloture, kind="total"),
    ]
    return OhadaStatement(
        title="Tableau des Flux de Trésorerie",
        subtitle="OHADA · Système Normal — méthode directe",
        fiscal_year=fiscal_year,
        lines=lines,
    )


# ---------------------------------------------------------------------------
# Système Minimal de Trésorerie (SMT) — condensed statements
# ---------------------------------------------------------------------------
def _smt_compte_de_resultat(accounts: list[dict], fiscal_year: str | None) -> OhadaStatement:
    L = _Ledger(accounts)
    produits = _r(L.credit("7") + L.credit("82", "84", "86", "88"))
    charges = _r(L.debit("6") + L.debit("81", "83", "85") + L.debit("89"))
    resultat = _r(produits - charges)

    def line(code, label, amount, kind="line", level=0):
        return OhadaLine(code=code, label=label, amount=_r(amount), kind=kind, level=level)

    lines = [
        line("RE", "Recettes / Produits de l'exercice", produits),
        line("DE", "Dépenses / Charges de l'exercice", -charges),
        line("RN", "RÉSULTAT (excédent / déficit)", resultat, kind="total"),
    ]
    return OhadaStatement(
        title="Compte de Résultat",
        subtitle="OHADA · Système Minimal de Trésorerie — présentation simplifiée",
        fiscal_year=fiscal_year,
        lines=lines,
    )


def _smt_bilan(accounts: list[dict], fiscal_year: str | None) -> OhadaStatement:
    L = _Ledger(accounts)
    _class4 = ("40", "41", "42", "43", "44", "45", "46", "47", "48", "49")
    immob = _r(L.debit("2"))
    stocks = _r(L.debit("3"))
    creances = L.debit_only(*_class4)
    tresorerie = _r(max(L.debit("5"), 0))
    total_actif = _r(immob + stocks + creances + tresorerie)

    resultat = _smt_compte_de_resultat(accounts, fiscal_year).lines[-1].amount
    capital = _r(L.credit("10", "11", "12", "14", "15"))
    capitaux = _r(capital + resultat)
    dettes_fin = _r(L.credit("16", "17", "18", "19"))
    dettes = L.credit_only(*_class4)
    tresorerie_passif = _r(max(L.credit("561", "564", "565", "566"), 0))
    total_passif = _r(capitaux + dettes_fin + dettes + tresorerie_passif)

    def line(code, label, amount, kind="line", level=0):
        return OhadaLine(code=code, label=label, amount=_r(amount), kind=kind, level=level)

    lines = [
        line("", "ACTIF", 0, kind="header"),
        line("AI", "Immobilisations (net)", immob),
        line("AS", "Stocks", stocks),
        line("AC", "Créances", creances),
        line("AT", "Trésorerie-Actif", tresorerie),
        line("AZ", "TOTAL ACTIF", total_actif, kind="total"),
        line("", "PASSIF", 0, kind="header"),
        line("CP", "Capitaux propres (résultat inclus)", capitaux),
        line("DF", "Dettes financières", dettes_fin),
        line("DC", "Dettes circulantes", dettes),
        line("DT", "Trésorerie-Passif", tresorerie_passif),
        line("DZ", "TOTAL PASSIF", total_passif, kind="total"),
    ]
    return OhadaStatement(
        title="Bilan",
        subtitle="OHADA · Système Minimal de Trésorerie — présentation simplifiée",
        fiscal_year=fiscal_year,
        lines=lines,
    )


# ---------------------------------------------------------------------------
# État annexé (notes annexes) — data-driven scaffold of the principal notes
# ---------------------------------------------------------------------------
def etat_annexe(
    accounts: list[dict], fiscal_year: str | None = None, currency: str = "XAF"
) -> OhadaStatement:
    def leaves(prefixes: tuple[str, ...], credit: bool = False,
               positive_only: bool = True) -> list[OhadaLine]:
        rows: list[OhadaLine] = []
        for a in sorted(accounts, key=lambda x: x["number"]):
            if a["number"].startswith(prefixes):
                amt = _r((a["credit"] - a["debit"]) if credit else (a["debit"] - a["credit"]))
                keep = amt > 0 if positive_only else amt != 0
                if keep:
                    rows.append(OhadaLine(code=a["number"], label=a["name"], amount=amt, level=1))
        return rows

    _c4 = ("40", "41", "42", "43", "44", "45", "46", "47", "48", "49")

    lines: list[OhadaLine] = []

    def note(title: str, rows: list[OhadaLine], empty: str = "Néant"):
        lines.append(OhadaLine(code="", label=title, amount=0, kind="header"))
        if rows:
            lines.extend(rows)
            total = _r(sum(r.amount for r in rows))
            lines.append(OhadaLine(code="", label="Total", amount=total, kind="subtotal"))
        else:
            lines.append(OhadaLine(code="", label=empty, amount=0, kind="note"))

    # Note 1 — règles et méthodes comptables (narrative)
    lines.append(OhadaLine(code="", label="Note 1 — Règles et méthodes comptables", amount=0, kind="header"))
    for txt in (
        f"Référentiel comptable : SYSCOHADA révisé (OHADA). Devise : {currency}.",
        "Immobilisations évaluées au coût historique ; amortissement linéaire.",
        "Stocks valorisés selon la méthode du coût unitaire moyen pondéré (CUMP) / FIFO.",
    ):
        lines.append(OhadaLine(code="", label=txt, amount=0, kind="note"))

    note("Note 3 — Immobilisations brutes & amortissements (classe 2)",
         leaves(("2",), positive_only=False))
    note("Note 6 — Stocks et en-cours (classe 3)", leaves(("3",)))
    note("Note 7 — Créances et emplois assimilés (classe 4 · débit)",
         leaves(_c4, credit=False, positive_only=True))
    note("Note 9 — Trésorerie (classe 5)", leaves(("5",), positive_only=False))
    note("Note 15 — Capitaux propres (classe 1 · 10 à 15)",
         leaves(("10", "11", "12", "13", "14", "15"), credit=True))
    note("Note 16 — Dettes financières (classe 1 · 16 à 19)",
         leaves(("16", "17", "18", "19"), credit=True))
    note("Note 17 — Dettes circulantes (classe 4 · crédit)",
         leaves(_c4, credit=True, positive_only=True))
    note("Note 21 — Chiffre d'affaires et autres produits (classe 7)", leaves(("7",), credit=True))
    note("Note 22 — Charges par nature (classe 6)", leaves(("6",)))

    return OhadaStatement(
        title="État Annexé",
        subtitle="OHADA · notes annexes — principales notes établies à partir de la balance",
        fiscal_year=fiscal_year,
        lines=lines,
    )
