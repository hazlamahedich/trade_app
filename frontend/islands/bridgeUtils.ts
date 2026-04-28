import { ComponentType, h, render } from "preact";

interface MountSpec {
  component: ComponentType<any>;
  props?: Record<string, any>;
}

const islandRegistry = new Map<string, MountSpec>();
const cleanupCallbacks = new WeakMap<Element, () => void>();
let observerCreated = false;

export function registerIsland(
  name: string,
  component: ComponentType<any>,
  defaultProps?: Record<string, any>
): void {
  if (islandRegistry.has(name)) {
    console.warn(`Overwriting previously registered island: ${name}`);
  }
  islandRegistry.set(name, { component, props: defaultProps });
}

function getIslandSpec(name: string): MountSpec | null {
  return islandRegistry.get(name) || null;
}

function hydrateElement(el: Element): void {
  const status = el.getAttribute("data-island-status");
  if (status === "hydrated") return;

  const islandName = el.getAttribute("data-preact-mount");
  if (!islandName) {
    console.warn("Preact island element has empty data-preact-mount value");
    return;
  }

  el.setAttribute("data-island-status", "pending");

  try {
    const spec = getIslandSpec(islandName);
    if (!spec) {
      console.warn(`Unknown Preact island: ${islandName}`);
      el.setAttribute("data-island-status", "error");
      return;
    }

    const propsJson = el.getAttribute("data-preact-props");
    const raw = propsJson?.trim() ? JSON.parse(propsJson) : {};
    const props = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};

    const vnode = h(spec.component, { ...spec.props, ...props });
    render(vnode, el as HTMLElement);
    el.setAttribute("data-island-status", "hydrated");

    cleanupCallbacks.set(el, () => {
      render(null, el as HTMLElement);
    });
  } catch (err) {
    el.setAttribute("data-island-status", "error");
    console.error(`Hydration error for island "${islandName}":`, err);
  }
}

function hydrateIslands(root: ParentNode = document): void {
  const islands = root.querySelectorAll("[data-preact-mount]");
  islands.forEach((el) => hydrateElement(el));
}

function teardownElement(el: Element): void {
  try {
    const cleanup = cleanupCallbacks.get(el);
    if (cleanup) {
      cleanup();
      cleanupCallbacks.delete(el);
    }
    el.removeAttribute("data-island-status");
  } catch (err) {
    console.error("Teardown error:", err);
  }
}

function teardownDescendants(root: Element): void {
  root.querySelectorAll("[data-preact-mount]").forEach((el) => teardownElement(el));
}

export function initBridge(): () => void {
  hydrateIslands();

  if (observerCreated) {
    return () => {};
  }
  observerCreated = true;

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of Array.from(mutation.addedNodes)) {
        if (!(node instanceof HTMLElement)) continue;
        try {
          if (node.hasAttribute("data-preact-mount")) {
            hydrateElement(node);
          }
          hydrateIslands(node);
        } catch (err) {
          console.error("MutationObserver addedNodes error:", err);
        }
      }
      for (const node of Array.from(mutation.removedNodes)) {
        if (!(node instanceof HTMLElement)) continue;
        try {
          teardownElement(node);
          teardownDescendants(node);
        } catch (err) {
          console.error("MutationObserver removedNodes error:", err);
        }
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  return () => {
    observer.disconnect();
    observerCreated = false;
    const islands = document.querySelectorAll("[data-preact-mount]");
    islands.forEach((el) => teardownElement(el));
  };
}
