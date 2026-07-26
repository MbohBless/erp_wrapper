// Report catalogue + signed-PDF download helper.

export type ReportKey =
  | "income-statement"
  | "balance-sheet"
  | "compte-de-resultat"
  | "bilan"
  | "flux-de-tresorerie"
  | "receivables"
  | "payables"
  | "current-stock"
  | "low-stock";

export type ReportParams = {
  company?: string;
  fiscal_year?: string;
  from_date?: string;
  to_date?: string;
  warehouse?: string;
};

/**
 * Fetch a branded, digitally-signed report PDF (auth required) and trigger a
 * browser download. Returns nothing; throws with the API detail on failure.
 */
export async function downloadReportPdf(
  token: string,
  key: ReportKey,
  params: ReportParams = {}
): Promise<void> {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v) sp.set(k, v);
  }
  const qs = sp.toString();
  const res = await fetch(`/api/reports/${key}/pdf${qs ? `?${qs}` : ""}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    let detail = "Could not generate the report PDF.";
    try {
      detail = (await res.json())?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const cd = res.headers.get("Content-Disposition");
  a.download = cd?.match(/filename="?([^"]+)"?/)?.[1] ?? `${key}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
