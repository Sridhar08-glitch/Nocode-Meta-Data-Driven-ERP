"use client";

import { useMutation } from "@tanstack/react-query";

import { useTenant } from "@/lib/tenant/context";

import { nqlApi } from "./api";
import { validate } from "./builder";
import type { NqlQuery, NqlResult } from "./types";

/**
 * Run an NQL query on demand (live preview / playground). A mutation rather than a query because
 * the AST is edited continuously and the user explicitly triggers a run. Throws before hitting the
 * network when the AST is invalid or no workspace is active.
 */
export function useRunNql() {
  const { workspace, isReady } = useTenant();
  return useMutation<NqlResult, Error, NqlQuery>({
    mutationFn: (ast) => {
      if (!isReady || !workspace) throw new Error("No active workspace");
      const errors = validate(ast);
      if (errors.length) throw new Error(errors[0]);
      return nqlApi.query(ast);
    },
  });
}
