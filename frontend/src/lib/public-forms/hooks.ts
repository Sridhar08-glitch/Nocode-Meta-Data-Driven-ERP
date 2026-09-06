"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { publicFormsApi } from "./api";

export function usePublicFormSchema(formId: string) {
  return useQuery({
    queryKey: ["public-form", formId],
    queryFn: () => publicFormsApi.schema(formId),
    enabled: !!formId,
    retry: false,
    staleTime: 60_000,
  });
}

export function useSubmitPublicForm(formId: string) {
  return useMutation({ mutationFn: (data: Record<string, unknown>) => publicFormsApi.submit(formId, data) });
}
