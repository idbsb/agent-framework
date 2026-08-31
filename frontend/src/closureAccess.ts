// Credentials live only in this tab's memory; never in the bundle or browser storage.
let credential = "";
export function setClosureCredential(value: string) { credential = value; }
export function closureHeaders(endpoint: string): Record<string, string> {
  return endpoint.startsWith("/api/closure/") && credential ? { Authorization: `Bearer ${credential}` } : {};
}
