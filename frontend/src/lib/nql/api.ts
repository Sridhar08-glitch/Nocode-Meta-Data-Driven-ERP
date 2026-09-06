/** NQL execution client (Phase F1.9) — POSTs a wire AST to `/api/v1/nql/query/`. */
import { apiSend } from "@/lib/api/request";

import { serialize } from "./builder";
import type { NqlQuery, NqlResult } from "./types";

export const nqlApi = {
  /** Execute a query AST; the builder state is serialized to the clean wire shape first. */
  query: (ast: NqlQuery) => apiSend<NqlResult>("/api/v1/nql/query/", "POST", serialize(ast)),
};
