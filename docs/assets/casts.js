/*
 * SPDX-FileCopyrightText: © 2026 Tyler Nivin
 * SPDX-License-Identifier: MIT
 */

/* Hydrates every .cast__player[data-cast] mount with asciinema-player (see castify's
   embedding.md reference doc). Wrapped in document$.subscribe rather than a plain
   DOMContentLoaded listener so a page navigated to via Material's instant-nav still gets
   its player hydrated, not just the first page loaded. */
document$.subscribe(function () {
  var mounts = document.querySelectorAll(".cast__player[data-cast]");
  if (!mounts.length || !window.AsciinemaPlayer) { return; }
  mounts.forEach(function (el) {
    var opts = { theme: "asciinema", fit: "width", controls: true };
    var cols = el.getAttribute("data-cols");
    var rows = el.getAttribute("data-rows");
    if (cols) { opts.cols = Number(cols); }
    if (rows) { opts.rows = Number(rows); }
    try {
      window.AsciinemaPlayer.create(el.getAttribute("data-cast"), el, opts);
    } catch (e) {
      console.warn("asciinema player failed for", el.getAttribute("data-cast"), e);
    }
  });
});
