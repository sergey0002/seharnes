---
name: playwright
description: "Verify uncovered UI behavior in a visible browser using Playwright MCP. Use for DOM inspection, clicks and screenshots when the scenario has no Cest or PHPUnit method."
---

# Playwright MCP

Codeception Acceptance provides primary coverage. Use Playwright only for behavior
branches without an existing Cest or PHPUnit method, through the test workflow.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/playwright.mdc) and
   [server document](docs/mcp/playwright.md) for enabled tools and browser setup.
2. Establish the scenario, expected result, project environment, URL and authorized
   role. Check existing test methods before opening a browser.
3. Use the configured headed browser and `browser_navigate` to the agreed URL.
   Take `browser_snapshot` and obtain current element references from that page.
4. Perform only the scenario's actions with `browser_click`, `browser_type` or
   `browser_fill_form`. Refresh the snapshot after page changes.
5. Verify the expected state with a snapshot; use read-only `browser_evaluate`
   or `browser_take_screenshot` when the assertion needs DOM or visual evidence.
6. Report the observed result, environment and evidence path. A screenshot of a
   mockup or manually modified DOM is not proof of the application's behavior.

## Isolation And Safety

- Use the current project's browser/profile and explicit environment URL. Do not
  reuse another project's authenticated session.
- Keep the browser visible; do not switch to cloud or hidden browser services.
- Do not start a test stand or chromedriver without user authorization.
- Do not edit templates or page state to make an assertion pass.
- Form submission, uploads, deletion and other persistent changes require scope
  authorization. Avoid evaluating mutating scripts as a testing shortcut.
- Do not enable disabled tools or install a browser as an implicit fallback.
  Report unavailable runtime access and the resulting verification gap.
