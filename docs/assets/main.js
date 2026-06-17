/*
 * SPDX-FileCopyrightText: © 2026 Tyler Nivin
 * SPDX-License-Identifier: MIT
 */

(function () {
  "use strict";

  const root = document.documentElement;

  // ---- Theme toggle (initial theme is set inline in <head> to avoid FOUC) --
  const toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    toggle.addEventListener("click", function () {
      const next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try {
        localStorage.setItem("theme", next);
      } catch (e) {
        /* private mode / storage disabled — theme just won't persist */
      }
    });
  }

  // ---- Mobile nav ----------------------------------------------------------
  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      const open = nav.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) nav.classList.remove("open");
    });
  }

  // ---- Active nav link -----------------------------------------------------
  const here = location.pathname.split("/").pop() || "index.html";
  document.querySelectorAll("[data-nav] a").forEach(function (a) {
    const target = a.getAttribute("href");
    if (target === here || (here === "index.html" && target === "./")) {
      a.setAttribute("aria-current", "page");
    }
  });

  // ---- Copy buttons on code blocks ----------------------------------------
  // The Clipboard API needs a secure context (https or localhost). The site is
  // meant to be viewed over GitHub Pages or the `launch-docs` fish function (both
  // secure); if it's opened another way (file://, plain http to a LAN IP) the
  // button explains why copy is unavailable instead of throwing a TypeError.
  const clipboardOK = !!(navigator.clipboard && window.isSecureContext);
  document.querySelectorAll("pre > code").forEach(function (code) {
    const pre = code.parentElement;
    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "copy";
    function flash(text, ms) {
      btn.textContent = text;
      setTimeout(function () {
        btn.textContent = "copy";
      }, ms);
    }
    btn.addEventListener("click", function () {
      if (!clipboardOK) {
        flash("needs https/localhost", 2400);
        console.warn(
          "Copy unavailable: the Clipboard API needs a secure context (https or " +
            "localhost). Open the site via GitHub Pages or `launch-docs`, not file:// " +
            "or plain http. (location.protocol = " + location.protocol + ")",
        );
        return;
      }
      navigator.clipboard.writeText(code.innerText).then(
        function () {
          flash("copied!", 1400);
        },
        function (err) {
          flash("copy failed", 1800);
          console.warn("Clipboard write failed:", err);
        },
      );
    });
    pre.appendChild(btn);
  });

  // ---- Asciinema casts -----------------------------------------------------
  // Players are mounted only on pages that load asciinema-player.min.js (the
  // Commands page). Each mount carries data-cast (the .cast file) and optional
  // data-cols/data-rows. If the script didn't load, the CSS :empty fallback
  // text stays visible — the page degrades gracefully.
  const mounts = document.querySelectorAll(".cast__player[data-cast]");
  if (mounts.length && window.AsciinemaPlayer) {
    mounts.forEach(function (el) {
      const opts = {
        theme: "asciinema",
        fit: "width",
        controls: true,
        terminalFontFamily:
          '"MesloLGS NF", ui-monospace, SFMono-Regular, Menlo, monospace',
      };
      const cols = el.getAttribute("data-cols");
      const rows = el.getAttribute("data-rows");
      if (cols) opts.cols = Number(cols);
      if (rows) opts.rows = Number(rows);
      try {
        window.AsciinemaPlayer.create(el.getAttribute("data-cast"), el, opts);
      } catch (e) {
        console.warn("asciinema player failed for", el.getAttribute("data-cast"), e);
      }
    });
  }

  // ---- Footer year ---------------------------------------------------------
  const year = document.querySelector("[data-year]");
  if (year) year.textContent = String(new Date().getFullYear());
})();
