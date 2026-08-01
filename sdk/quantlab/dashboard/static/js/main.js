/**
 * Main entry point — page detection + dynamic module loader.
 * Self-executing, no exports.
 */
(function () {
  const PAGE_MODULES = {
    "/campaigns/": "CampaignList",
    "/": "CampaignList",
    "/pipeline": "PipelineMonitor",
    "/stats": "StatsDashboard",
  };

  const DETAIL_MODULES = {
    "/campaigns/": "CampaignDetail",
  };

  async function init() {
    const path = window.location.pathname;

    // Check for detail pages first (paths with IDs after the prefix)
    let pageName = null;
    for (const [prefix, name] of Object.entries(DETAIL_MODULES)) {
      if (path.startsWith(prefix) && path.replace(prefix, "").length > 0 && !path.replace(prefix, "").includes("/")) {
        // Path like /campaigns/{id} — load detail page
        pageName = name;
        break;
      }
    }

    // Fall back to list/dashboard pages
    if (!pageName) {
      for (const [prefix, name] of Object.entries(PAGE_MODULES)) {
        if (path === prefix || path.startsWith(prefix)) {
          pageName = name;
          break;
        }
      }
    }

    if (!pageName) return;

    try {
      const module = await import(`./pages/${pageName}.js`);
      if (module.default && typeof module.default === "function") {
        module.default();
      }
    } catch (err) {
      console.error(`Failed to load page module: ${pageName}`, err);
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
