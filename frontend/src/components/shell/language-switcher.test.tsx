import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const i18n = { locale: "en-US", setLocale: vi.fn(), availableLocales: ["en-US", "fr-FR"] };
vi.mock("@/lib/i18n/context", () => ({ useI18n: () => i18n }));

import { LanguageSwitcher } from "./language-switcher";

beforeEach(() => {
  i18n.locale = "en-US";
  i18n.availableLocales = ["en-US", "fr-FR"];
  vi.clearAllMocks();
});

describe("LanguageSwitcher", () => {
  it("renders nothing when only one locale is enabled", () => {
    i18n.availableLocales = ["en-US"];
    const { container } = render(<LanguageSwitcher />);
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the enabled locales and switches on select", async () => {
    render(<LanguageSwitcher />);
    const trigger = screen.getByRole("button", { name: "Change language" });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "Enter" }); // Radix menus open on Enter
    const items = await screen.findAllByRole("menuitem");
    const fr = items.find((el) => el.textContent?.includes("fr-FR"))!;
    fireEvent.click(fr);
    expect(i18n.setLocale).toHaveBeenCalledWith("fr-FR");
  });
});
