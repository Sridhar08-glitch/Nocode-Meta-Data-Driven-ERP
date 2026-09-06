import axe from "axe-core";

/**
 * Run axe-core against a rendered container and return violations.
 * `color-contrast` is disabled because jsdom has no layout engine to compute it
 * (contrast is verified visually in the showcase + theming review).
 */
export async function findA11yViolations(container: Element): Promise<axe.Result[]> {
  const results = await axe.run(container, {
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations;
}
