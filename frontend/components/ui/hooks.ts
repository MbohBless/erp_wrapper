import { useEffect, useState } from "react";

/** Debounce a rapidly-changing value (e.g. a search box) by `delay` ms. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

/**
 * Server-side paging state for a list page.
 *
 * Fetches one row *more* than the page shows. That extra row is the whole
 * mechanism: if it comes back there is a next page, and if it does not there
 * isn't — no separate count query, and no second round trip to ERPNext on every
 * page load. The caller trims it off before rendering.
 *
 * `resetOn` is the filter state. Changing a filter has to return to the first
 * page: staying on page 4 of a result set that now has one page shows an empty
 * table, which reads as "no matches" rather than "wrong page".
 */
export function usePaged(resetOn: unknown[], size = 25) {
  const [page, setPage] = useState(0);
  const key = JSON.stringify(resetOn);
  useEffect(() => {
    setPage(0);
  }, [key]);
  return { page, setPage, size, start: page * size, fetchLimit: size + 1 };
}
