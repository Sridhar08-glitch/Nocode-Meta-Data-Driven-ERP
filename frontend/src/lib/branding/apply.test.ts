import { afterEach, describe, expect, it } from "vitest";

import {
  applyBranding,
  applyPersonalization,
  hexToHslChannels,
  radiusValue,
  readBrandingSnapshot,
  resetBranding,
  resetPersonalization,
} from "./apply";

describe("hexToHslChannels", () => {
  it("converts the brand indigo to HSL channels", () => {
    // #6366f1 → ~239 84% 67%
    const hsl = hexToHslChannels("#6366f1");
    expect(hsl).toMatch(/^\d{1,3} \d{1,3}% \d{1,3}%$/);
    const [h, s, l] = (hsl ?? "").split(" ");
    expect(Number(h)).toBeGreaterThanOrEqual(235);
    expect(Number(h)).toBeLessThanOrEqual(245);
    expect(s).toMatch(/%$/);
    expect(l).toMatch(/%$/);
  });

  it("handles shorthand and missing hash", () => {
    expect(hexToHslChannels("fff")).toBe("0 0% 100%");
    expect(hexToHslChannels("#000000")).toBe("0 0% 0%");
  });

  it("returns null for invalid input", () => {
    expect(hexToHslChannels("not-a-color")).toBeNull();
    expect(hexToHslChannels("#12")).toBeNull();
  });
});

describe("applyBranding", () => {
  afterEach(() => resetBranding());

  it("writes CSS variables from branding hex colours", () => {
    applyBranding({ color_primary: "#ff0000", color_background: "#ffffff" });
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--primary")).toBe("0 100% 50%");
    expect(root.style.getPropertyValue("--background")).toBe("0 0% 100%");
  });

  it("ignores invalid colours without throwing", () => {
    expect(() => applyBranding({ color_primary: "garbage" })).not.toThrow();
    expect(document.documentElement.style.getPropertyValue("--primary")).toBe("");
  });

  it("resetBranding removes the variables", () => {
    applyBranding({ color_primary: "#ff0000" });
    resetBranding();
    expect(document.documentElement.style.getPropertyValue("--primary")).toBe("");
  });
});

describe("applyBranding — typography, radius, density, favicon, custom CSS, snapshot", () => {
  afterEach(() => {
    resetBranding();
    document.querySelector('link[rel="icon"]')?.remove();
    window.localStorage.clear();
  });

  it("applies fonts to CSS variables", () => {
    applyBranding({ font_family_heading: "Poppins", font_family_body: "Roboto" });
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--font-heading")).toBe("Poppins");
    expect(root.style.getPropertyValue("--font-body")).toBe("Roboto");
  });

  it("maps a border-radius preset to --radius (radiusValue)", () => {
    expect(radiusValue("none")).toBe("0px");
    expect(radiusValue("lg")).toBe("0.75rem");
    expect(radiusValue("2rem")).toBe("2rem");
    expect(radiusValue("bogus")).toBeNull();
    applyBranding({ border_radius: "none" });
    expect(document.documentElement.style.getPropertyValue("--radius")).toBe("0px");
  });

  it("sets the density data attribute", () => {
    applyBranding({ ui_density: "compact" });
    expect(document.documentElement.dataset.density).toBe("compact");
    resetBranding();
    expect(document.documentElement.dataset.density).toBeUndefined();
  });

  it("injects the favicon and updates it on change", () => {
    applyBranding({ favicon_url: "https://cdn/a.ico" });
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    expect(link?.getAttribute("href")).toBe("https://cdn/a.ico");
    applyBranding({ favicon_url: "https://cdn/b.ico" });
    expect(document.querySelector<HTMLLinkElement>('link[rel="icon"]')?.getAttribute("href")).toBe(
      "https://cdn/b.ico",
    );
  });

  it("injects and removes custom CSS in a single dedicated <style>", () => {
    applyBranding({ custom_css: ".x{color:red}" });
    const style = document.getElementById("nexus-workspace-css");
    expect(style?.textContent).toBe(".x{color:red}");
    resetBranding();
    expect(document.getElementById("nexus-workspace-css")).toBeNull();
  });

  it("snapshots login branding for the pre-auth page", () => {
    applyBranding({ app_name: "Acme", logo_url: "l.png", login_headline: "Welcome" });
    const snap = readBrandingSnapshot();
    expect(snap?.app_name).toBe("Acme");
    expect(snap?.login_headline).toBe("Welcome");
  });
});

describe("applyPersonalization — user overlay on the branding pipeline", () => {
  afterEach(() => {
    resetPersonalization();
    resetBranding();
  });

  it("overrides accent, density and radius on top of branding", () => {
    applyBranding({ color_accent: "#000000", ui_density: "comfortable", border_radius: "md" });
    applyPersonalization({ accent: "#ff0000", density: "compact", radius: "none" });
    const root = document.documentElement;
    expect(root.style.getPropertyValue("--accent")).toBe("0 100% 50%");
    expect(root.dataset.density).toBe("compact");
    expect(root.style.getPropertyValue("--radius")).toBe("0px");
  });

  it("applies font_scale as a 0.8–1.5 multiplier and clears it on reset", () => {
    applyPersonalization({ font_scale: 130 });
    expect(document.documentElement.style.getPropertyValue("--font-scale")).toBe("1.3");
    resetPersonalization();
    expect(document.documentElement.style.getPropertyValue("--font-scale")).toBe("");
  });

  it("toggles the high-contrast class", () => {
    applyPersonalization({ high_contrast: true });
    expect(document.documentElement.classList.contains("hc")).toBe(true);
    applyPersonalization({ high_contrast: false });
    expect(document.documentElement.classList.contains("hc")).toBe(false);
  });

  it("maps reduced_motion to data-motion (on→reduce, off→full, system→unset)", () => {
    const root = document.documentElement;
    applyPersonalization({ reduced_motion: "on" });
    expect(root.dataset.motion).toBe("reduce");
    applyPersonalization({ reduced_motion: "off" });
    expect(root.dataset.motion).toBe("full");
    applyPersonalization({ reduced_motion: "system" });
    expect(root.dataset.motion).toBeUndefined();
  });

  it("ignores an invalid accent hex without throwing", () => {
    expect(() => applyPersonalization({ accent: "nope" })).not.toThrow();
    expect(document.documentElement.style.getPropertyValue("--accent")).toBe("");
  });

  it("null/undefined clears the overlay", () => {
    applyPersonalization({ high_contrast: true, font_scale: 120 });
    applyPersonalization(null);
    expect(document.documentElement.classList.contains("hc")).toBe(false);
    expect(document.documentElement.style.getPropertyValue("--font-scale")).toBe("");
  });
});
