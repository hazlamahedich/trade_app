(function () {
  function init() {
    var form = document.getElementById("experiment-filters-form");
    if (!form) return;

    var selects = form.querySelectorAll("select");
    selects.forEach(function (sel) {
      sel.addEventListener("change", function () {
        var formData = new FormData(form);
        var params = new URLSearchParams();
        formData.forEach(function (val, key) {
          if (val) params.set(key, val);
        });
        if (!params.has("sort")) params.set("sort", "created_at");
        if (!params.has("dir")) params.set("dir", "desc");
        htmx.ajax("GET", "/experiments?" + params.toString(), {
          target: "#experiment-table-body",
          swap: "innerHTML",
        });
      });
    });

    var controls = document.getElementById("filter-controls");
    if (controls) controls.setAttribute("data-island-status", "ready");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
