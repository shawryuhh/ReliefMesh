export type PageRecord = { id: string };
export class PaginationError extends Error {
  readonly code: "invalid_page" | "page_limit";
  constructor(code: "invalid_page" | "page_limit") {
    super(code);
    this.code = code;
    this.name = "PaginationError";
  }
}
export async function collectPages<T extends PageRecord>(
  fetchPage: (limit: number, offset: number) => Promise<unknown>,
  pageSize = 100, maxPages = 5,
): Promise<T[]> {
  if (!Number.isInteger(pageSize) || pageSize < 1 || !Number.isInteger(maxPages) || maxPages < 1)
    throw new PaginationError("invalid_page");
  const all: T[] = [];
  const ids = new Set<string>();
  for (let page = 0; page < maxPages; page++) {
    const result = await fetchPage(pageSize, page * pageSize);
    if (!Array.isArray(result) || result.length > pageSize) throw new PaginationError("invalid_page");
    for (const item of result) {
      if (!item || typeof item !== "object" || Array.isArray(item) ||
        typeof item.id !== "string" || !item.id || ids.has(item.id))
        throw new PaginationError("invalid_page");
      ids.add(item.id);
      all.push(item as T);
    }
    if (result.length < pageSize) return all;
  }
  throw new PaginationError("page_limit");
}
