"use client";

import { Icon } from "@/components/icons";
import { useI18n } from "@/lib/i18n";

/**
 * Prev/next paging for a list page.
 *
 * There is no total and no page count, deliberately. ERPNext's list API does not
 * return one, so a total would cost a second query per page load to display a
 * number nobody acts on — what people actually need is "is there more, and how
 * do I get to it".
 *
 * Renders nothing when everything fits on one page, so short lists stay clean.
 */
export default function Pagination({
  page,
  size,
  count,
  hasNext,
  onChange,
}: {
  page: number;
  size: number;
  /** Rows actually rendered on this page, after the probe row is trimmed. */
  count: number;
  hasNext: boolean;
  onChange: (page: number) => void;
}) {
  const { t } = useI18n();
  if (page === 0 && !hasNext) return null;

  const first = page * size + 1;
  const last = page * size + count;

  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3 border-t border-divider">
      <span className="text-xs muted">
        {count === 0
          ? t("common.pageEmpty")
          : t("common.showingRange")
              .replace("{first}", String(first))
              .replace("{last}", String(last))}
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(page - 1)}
          disabled={page === 0}
          className="btn btn-text text-[13px] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <span className="inline-block rotate-90">
            <Icon name="chevronDown" size={14} />
          </span>
          {t("common.previous")}
        </button>
        <button
          type="button"
          onClick={() => onChange(page + 1)}
          disabled={!hasNext}
          className="btn btn-text text-[13px] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t("common.next")}
          <span className="inline-block -rotate-90">
            <Icon name="chevronDown" size={14} />
          </span>
        </button>
      </div>
    </div>
  );
}
