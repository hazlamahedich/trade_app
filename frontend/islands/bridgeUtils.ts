import { ComponentType, h, render } from "preact";

interface MountSpec {
  component: ComponentType<any>;
  props?: Record<string, any>;
}

const mountedComponents = new WeakMap<Element, () => void>();

function hydrateIslands(root: ParentNode = document): void {
  const islands = root.querySelectorAll("[data-preact-mount]");
  islands.forEach((el) => {
    if (mountedComponents.has(el)) return;

    const islandName = el.getAttribute("data-preact-mount");
    if (!islandName) return;

    const propsJson = el.getAttribute("data-preact-props");
    const props = propsJson ? JSON.parse(propsJson) : {};

    const spec = getIslandSpec(islandName);
    if (!spec) {
      console.warn(`Unknown Preact island: ${islandName}`);
      return;
    }

    const vnode = h(spec.component, { ...spec.props, ...props });
    render(vnode, el as HTMLElement);

    mountedComponents.set(el, () => {
      render(null, el as HTMLElement);
    });
  });
}

function teardownIslands(root: ParentNode = document): void {
  const islands = root.querySelectorAll("[data-preact-mount]");
  islands.forEach((el) => {
    const unmount = mountedComponents.get(el);
    if (unmount) {
      unmount();
      mountedComponents.delete(el);
    }
  });
}

function getIslandSpec(
  name: string
): MountSpec | null {
  const registry: Record<string, MountSpec> = {};
  return registry[name] || null;
}

export function registerIsland(
  name: string,
  component: ComponentType<any>,
  defaultProps?: Record<string, any>
): void {
  void name;
  void component;
  void defaultProps;
}

export function initBridge(): () => void {
  hydrateIslands();

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of Array.from(mutation.addedNodes)) {
        if (node instanceof HTMLElement) {
          if (node.hasAttribute("data-preact-mount")) {
            hydrateIslands(node);
          }
          hydrateIslands(node);
        }
      }
      for (const node of Array.from(mutation.removedNodes)) {
        if (node instanceof HTMLElement) {
          const unmount = mountedComponents.get(node);
          if (unmount) {
            unmount();
            mountedComponents.delete(node);
          }
          node.querySelectorAll("[data-preact-mount]").forEach((el) => {
            const u = mountedComponents.get(el);
            if (u) {
              u();
              mountedComponents.delete(el);
            }
          });
        }
      }
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  return () => {
    observer.disconnect();
    teardownIslands();
  };
}
