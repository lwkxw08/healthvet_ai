import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Format a date/datetime string as dd-mm-yyyy hh:mm (UK format).
 * Accepts ISO strings, Date objects, or any string parseable by `new Date()`.
 * Returns "" for null/undefined/invalid input.
 * Pass `dateOnly: true` to get just dd-mm-yyyy without the time.
 */
export function fmtDate(value: unknown, opts?: { dateOnly?: boolean }): string {
  if (value == null || value === "") return "";
  const d = typeof value === "string" ? new Date(value) : value instanceof Date ? value : null;
  if (!d || isNaN(d.getTime())) return String(value);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  if (opts?.dateOnly) return `${dd}-${mm}-${yyyy}`;
  const hh = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${dd}-${mm}-${yyyy} ${hh}:${min}`;
}
