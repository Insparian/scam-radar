// Ephemeral navigation handoff only. Never serialize a query into URLs or storage.
let pendingQuery = "";

export function setPendingQuery(value: string): void {
  pendingQuery = value;
}

export function getPendingQuery(): string {
  return pendingQuery;
}

export function clearPendingQuery(): void {
  pendingQuery = "";
}
