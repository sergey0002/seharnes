# Playwright MCP

Checks UI branches that have no Cest or PHPUnit method.
Codeception remains the primary acceptance test runner.

The workflow opens the agreed environment in a visible browser.
DOM snapshots provide current element references for scenario actions.
Assertions use the application's actual state and supporting screenshots.

Browser profiles and authenticated sessions stay within the current project.
Starting services and changing persistent data require authorization.
The bundled server document preserves setup details and known limitations.
