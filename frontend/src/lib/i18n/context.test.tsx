import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const tenant = { workspace: { slug: "acme" } as { slug: string } | null, isReady: true };
vi.mock("@/lib/tenant/context", () => ({ useTenant: () => tenant }));
vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  localizationApi: {
    getLocale: vi.fn(() => Promise.resolve({ default_locale: "en-US", default_currency: "USD", enabled_locales: ["en-US", "ar-EG"] })),
    translations: vi.fn((locale: string) => Promise.resolve({ locale, translations: { "ui.save": "Save" } })),
  },
}));

import { I18nProvider, useI18n } from "./context";

function Probe() {
  const { t, dir, locale, setLocale, formatCurrency, availableLocales } = useI18n();
  return (
    <div>
      <span data-testid="t">{t("ui.save")}</span>
      <span data-testid="missing">{t("ui.nope", "Fallback")}</span>
      <span data-testid="dir">{dir}</span>
      <span data-testid="locale">{locale}</span>
      <span data-testid="cur">{formatCurrency(1000)}</span>
      <span data-testid="avail">{availableLocales.join(",")}</span>
      <button onClick={() => setLocale("ar-EG")}>arabic</button>
    </div>
  );
}

function renderProbe() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <I18nProvider>
        <Probe />
      </I18nProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  tenant.workspace = { slug: "acme" };
  window.localStorage.clear();
  document.documentElement.dir = "ltr";
  vi.clearAllMocks();
});

describe("I18nProvider", () => {
  it("translates dotted keys, falls back, and exposes locale-aware formatting", async () => {
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("t")).toHaveTextContent("Save"));
    expect(screen.getByTestId("missing")).toHaveTextContent("Fallback");
    expect(screen.getByTestId("dir")).toHaveTextContent("ltr");
    expect(screen.getByTestId("cur").textContent).toMatch(/\$1,000/); // en-US currency format
    expect(screen.getByTestId("avail")).toHaveTextContent("en-US,ar-EG");
  });

  it("switching to an RTL locale flips direction + persists the choice", async () => {
    renderProbe();
    await waitFor(() => expect(screen.getByTestId("locale")).toHaveTextContent("en-US"));
    act(() => screen.getByText("arabic").click());
    await waitFor(() => expect(screen.getByTestId("dir")).toHaveTextContent("rtl"));
    expect(screen.getByTestId("locale")).toHaveTextContent("ar-EG");
    expect(window.localStorage.getItem("nexus.locale")).toBe("ar-EG");
    expect(document.documentElement.dir).toBe("rtl");
  });
});
