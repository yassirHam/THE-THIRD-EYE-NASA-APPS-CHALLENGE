// Static skeleton loader. Reads bundle/bundle_index.json from the same origin only.
// No backend, no third-party requests. Shows file names and sizes, never values.
(function () {
  "use strict";
  var status = document.getElementById("bundle-status");
  var size = document.getElementById("bundle-size");
  var list = document.getElementById("bundle-files");
  fetch("bundle/bundle_index.json", { cache: "no-store" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (index) {
      var kb = function (n) { return (n / 1024).toFixed(1) + " KB"; };
      status.textContent = index.entries.length + " files, bundle " + index.bundle_version +
        (index.data_classification === "production" ? "" : " (development test data)");
      var gz = index.size_report.total_gzip_bytes;
      size.textContent = gz === null ? "Compressed size not measured." :
        "Compressed size " + kb(gz) + " of the " + kb(index.size_report.p0_compressed_target_bytes) + " target.";
      index.entries.forEach(function (e) {
        var li = document.createElement("li");
        li.textContent = e.path + " (" + kb(e.bytes) + ")";
        list.appendChild(li);
      });
    })
    .catch(function (err) {
      status.textContent = "The evidence files could not be loaded (" + err.message + "). Nothing is shown in their place.";
    });
})();