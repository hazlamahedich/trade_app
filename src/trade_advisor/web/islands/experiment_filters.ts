import { h, render } from "preact";
import { useEffect, useRef } from "preact/hooks";

function ExperimentFilters() {
  const formRef = useRef(null);

  useEffect(() => {
    const el = document.getElementById("filter-controls");
    if (el) el.setAttribute("data-island-status", "ready");
  }, []);

  function onChange() {
    if (formRef.current) {
      const formData = new FormData(formRef.current);
      const params = new URLSearchParams(formData as any);
      const sort = params.get("sort") || "created_at";
      const dir = params.get("dir") || "desc";
      params.set("sort", sort);
      params.set("dir", dir);
      htmx.ajax("GET", `/experiments?${params.toString()}`, {
        target: "#experiment-table-body",
        swap: "innerHTML",
      });
    }
  }

  return h("div", { class: "experiment-filters" }, [
    h("select", {
      name: "strategy",
      form: "experiment-filters-form",
      onChange,
    }),
    h("select", {
      name: "status",
      form: "experiment-filters-form",
      onChange,
    }),
  ]);
}

const mount = document.getElementById("filter-controls");
if (mount) {
  render(h(ExperimentFilters, {}), mount);
}
