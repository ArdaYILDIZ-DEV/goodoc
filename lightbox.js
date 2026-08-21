/**
 * lightbox.js — Retro image overlay for goodoc
 * =================================================
 * Enhances every ``figure img`` and standalone ``p > img`` with a modal
 * lightbox (zoom, pan, keyboard and touch support). Only the image
 * transforms (``translate → scale``) so the caption stays fixed.
 *
 * Features
 * --------
 * - Click any figure/standalone image → overlay at 150% centered
 * - Toolbar: zoom in / out / reset, live percentage
 * - Drag to pan (when zoomed), wheel zoom, double-click toggle,
 *   pinch-zoom and ``+/-/0/Esc`` keys
 * - Accessible: ``role=dialog``, ``aria-modal``, focus restore, body scroll lock
 * - Safe re-init guard (``window.__lightboxInit``) for hot reload
 *
 * Usage
 * -----
 * Include after the page content (``build.py`` injects ``<script src="lightbox.js">``
 * with a relative path per page). No configuration needed.
 *
 * @module lightbox
 */
(function () {
  "use strict";
  // Guard against double init (e.g., hot reload or duplicate script tag)
  if (window.__lightboxInit) return;
  window.__lightboxInit = true;

  /**
   * Initialize the lightbox: query images, build overlay DOM and wire events.
   * No-op if no eligible images exist on the page.
   * @returns {void}
   */
  function init() {
    var imgs = document.querySelectorAll("figure img, p > img:only-child, li > img:only-child, p > a:only-child > img:only-child");
    if (!imgs.length) return;

    var overlay = document.createElement("div");
    overlay.className = "lightbox-overlay";
    overlay.setAttribute("aria-hidden", "true");
    overlay.innerHTML =
      '<div class="lightbox-frame" role="dialog" aria-modal="true" aria-label="Görsel büyütme">' +
      '<button class="lightbox-close" type="button" aria-label="Kapat">×</button>' +
      '<div class="lightbox-viewport"><img alt=""></div>' +
      '<div class="lightbox-caption"></div>' +
      '<div class="lightbox-toolbar" aria-label="Yakınlaştırma">' +
      '<button type="button" class="lb-zoom-out" aria-label="Uzaklaştır">−</button>' +
      '<span class="lb-zoom-level">150%</span>' +
      '<button type="button" class="lb-zoom-in" aria-label="Yakınlaştır">+</button>' +
      '<button type="button" class="lb-zoom-reset" aria-label="Sıfırla">↺</button>' +
      '</div></div>';
    document.body.appendChild(overlay);

    var frame = overlay.querySelector(".lightbox-frame");
    var viewport = overlay.querySelector(".lightbox-viewport");
    var largeImg = viewport.querySelector("img");
    var captionEl = overlay.querySelector(".lightbox-caption");
    var closeBtn = overlay.querySelector(".lightbox-close");
    var zoomInBtn = overlay.querySelector(".lb-zoom-in");
    var zoomOutBtn = overlay.querySelector(".lb-zoom-out");
    var zoomResetBtn = overlay.querySelector(".lb-zoom-reset");
    var zoomLevelEl = overlay.querySelector(".lb-zoom-level");

    var scale = 1.5, tx = 0, ty = 0;
    var minScale = 1, maxScale = 1.5, step = 0.15; // default 150% (scale 1.5) on open, per dokuman.md
    var baseW = 0, baseH = 0;
    var lastFocus = null;
    var isDragging = false, startX = 0, startY = 0, startTX = 0, startTY = 0;
    var globalAttached = false;

    /**
     * Clamp a number to [min, max].
     * @param {number} v - Value to clamp.
     * @param {number} min - Lower bound.
     * @param {number} max - Upper bound.
     * @returns {number} Clamped value.
     */
    function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

    /**
     * Update the toolbar percentage label from current ``scale``.
     * @returns {void}
     */
    function updateLevel() {
      zoomLevelEl.textContent = Math.round(scale * 100) + "%";
    }
    /**
     * Apply current ``translate`` + ``scale`` to the enlarged image.
     * Transform order is ``translate → scale`` so pan distance stays in
     * screen pixels (caption remains fixed). Resets to 100% when scale
     * drops near 1.
     * @returns {void}
     */
    function applyTransform() {
      // D1: only image moves, caption fixed (viewport clip)
      largeImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
      updateLevel();
      viewport.style.cursor = scale > 1 ? "grab" : "zoom-in";
      if (scale <= 1.01) {
        tx = 0; ty = 0;
        largeImg.style.transform = "translate(0px,0px) scale(1)";
      }
    }
    /**
     * Compute allowed pan bounds for the current zoom.
     * Visual size is ``base * scale``; excess over viewport is the
     * pan range in screen pixels.
     * @returns {{maxX: number, maxY: number}} Half-range on each axis.
     */
    function getBounds() {
      var vw = viewport.clientWidth;
      var vh = viewport.clientHeight;
      var iw = baseW, ih = baseH;
      if (!iw || !ih) return { maxX: 0, maxY: 0 };
      // visual size at scale is iw*scale; allowed translate is (visual - viewport)/2 in screen pixels
      var sw = iw * scale;
      var sh = ih * scale;
      var maxX = Math.max(0, (sw - vw) / 2);
      var maxY = Math.max(0, (sh - vh) / 2);
      return { maxX: maxX, maxY: maxY };
    }
    /**
     * Clamp ``tx``/``ty`` to the current bounds.
     * @returns {void}
     */
    function clampTranslate() {
      var b = getBounds();
      tx = clamp(tx, -b.maxX, b.maxX);
      ty = clamp(ty, -b.maxY, b.maxY);
    }
    /**
     * Set a new zoom level, optionally keeping the point under the cursor fixed.
     * @param {number} newScale - Target scale (clamped to [minScale, maxScale]).
     * @param {number} [cx] - Client X of the zoom origin (e.g., wheel position).
     * @param {number} [cy] - Client Y of the zoom origin.
     * @returns {void}
     */
    function setScale(newScale, cx, cy) {
      newScale = clamp(newScale, minScale, maxScale);
      if (newScale === scale) return;
      if (typeof cx === "number" && typeof cy === "number") {
        var rect = viewport.getBoundingClientRect();
        var vx = cx - rect.left - rect.width / 2;
        var vy = cy - rect.top - rect.height / 2;
        var ratio = newScale / scale;
        tx = vx - (vx - tx) * ratio;
        ty = vy - (vy - ty) * ratio;
      }
      scale = newScale;
      if (scale <= 1.01) { scale = 1; tx = 0; ty = 0; }
      else clampTranslate();
      applyTransform();
    }
    /**
     * Reset to the default 150% centered view and clear dragging state.
     * @returns {void}
     */
    function reset() {
      scale = 1.5; tx = 0; ty = 0; // default 150% — restore to initial zoom, centered
      largeImg.classList.remove("is-dragging");
      viewport.classList.remove("is-grabbing");
      applyTransform();
    }

    /**
     * Handle pointer down on the viewport — start dragging if zoomed.
     * @param {MouseEvent} e
     * @returns {void}
     */
    function onPointerDown(e) {
      if (scale <= 1) return;
      isDragging = true;
      largeImg.classList.add("is-dragging");
      viewport.classList.add("is-grabbing");
      startX = e.clientX;
      startY = e.clientY;
      startTX = tx; startTY = ty;
      e.preventDefault();
    }
    /**
     * Handle pointer move while dragging — update ``tx``/``ty`` with damping.
     * @param {MouseEvent} e
     * @returns {void}
     */
    function onPointerMove(e) {
      if (!isDragging) return;
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      tx = startTX + dx * 0.85;
      ty = startTY + dy * 0.85;
      clampTranslate();
      largeImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
    }
    /**
     * Handle pointer up — end dragging and clear grabbing styles.
     * @returns {void}
     */
    function onPointerUp() {
      if (!isDragging) return;
      isDragging = false;
      largeImg.classList.remove("is-dragging");
      viewport.classList.remove("is-grabbing");
    }
    /**
     * Attach global mousemove/mouseup listeners (only while overlay is open).
     * Idempotent.
     * @returns {void}
     */
    function attachGlobal() {
      if (globalAttached) return;
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      globalAttached = true;
    }
    /**
     * Detach global listeners.
     * @returns {void}
     */
    function detachGlobal() {
      if (!globalAttached) return;
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      globalAttached = false;
    }

    /**
     * Open the overlay for a given image.
     * @param {string} src - Image URL (``currentSrc`` or ``src``).
     * @param {string} alt - Alt text for accessibility.
     * @param {string} caption - Caption text (from ``figcaption`` or alt).
     * @returns {void}
     */
    function open(src, alt, caption) {
      largeImg.src = src;
      largeImg.alt = alt || "";
      captionEl.textContent = caption || alt || "";
      captionEl.style.display = captionEl.textContent ? "block" : "none";
      overlay.classList.add("is-open");
      overlay.setAttribute("aria-hidden", "false");
      lastFocus = document.activeElement;
      scale = 1.5; tx = 0; ty = 0;
      largeImg.style.transform = "translate(0px,0px) scale(1.5)"; // open at 150%, centered, bounds allow edge pan
      updateLevel();
      document.body.style.overflow = "hidden";
      attachGlobal();
      // M12: error fallback
      largeImg.onerror = function () {
        captionEl.textContent = "Görsel yüklenemedi";
        captionEl.style.display = "block";
        baseW = 0; baseH = 0;
        reset();
      };
      largeImg.onload = function () {
        requestAnimationFrame(function () {
          var r = largeImg.getBoundingClientRect();
          baseW = r.width;
          baseH = r.height;
          reset();
        });
      };
      if (largeImg.complete && largeImg.naturalWidth) {
        setTimeout(function () {
          var r = largeImg.getBoundingClientRect();
          baseW = r.width; baseH = r.height;
          reset();
        }, 30);
      } else if (largeImg.complete) {
        // cached but not loaded yet (error case already handled)
        setTimeout(function () {
          if (!baseW) {
            var r = largeImg.getBoundingClientRect();
            baseW = r.width; baseH = r.height;
            reset();
          }
        }, 30);
      }
      try { closeBtn.focus(); } catch (e) {}
    }
    /**
     * Close the overlay, restore focus and body scroll.
     * @returns {void}
     */
    function close() {
      overlay.classList.remove("is-open");
      overlay.setAttribute("aria-hidden", "true");
      document.body.style.overflow = "";
      detachGlobal();
      setTimeout(reset, 240);
      if (lastFocus) { try { lastFocus.focus(); } catch (e) {} }
    }

    // wiring
    imgs.forEach(function (img) {
      img.addEventListener("click", function (e) {
        e.preventDefault();
        var fig = img.closest("figure");
        var caption = "";
        if (fig) {
          var fc = fig.querySelector("figcaption");
          if (fc) caption = fc.innerText.trim();
        }
        if (!caption) caption = img.alt || "";
        open(img.currentSrc || img.src, img.alt, caption);
      });
    });

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) close();
    });
    closeBtn.addEventListener("click", close);

    zoomInBtn.addEventListener("click", function () { setScale(scale + step); });
    zoomOutBtn.addEventListener("click", function () { setScale(scale - step); });
    zoomResetBtn.addEventListener("click", reset);

    // M6: normalized wheel with deltaMode
    viewport.addEventListener("wheel", function (e) {
      e.preventDefault();
      var delta = e.deltaY;
      if (e.deltaMode === 1) delta *= 16; // line mode
      else if (e.deltaMode === 2) delta *= 100; // page mode
      var zoomDelta = delta > 0 ? -0.08 : 0.08;
      var s = clamp(scale + zoomDelta, minScale, maxScale);
      setScale(s, e.clientX, e.clientY);
    }, { passive: false });

    viewport.addEventListener("dblclick", function (e) {
      e.preventDefault();
      // toggle between 100% (min) and 150% (default) — reset goes to 150%
      if (scale > 1.01) setScale(1, e.clientX, e.clientY);
      else setScale(1.5, e.clientX, e.clientY);
    });

    viewport.addEventListener("mousedown", onPointerDown);

    // touch
    var lastTouchDist = 0;
    viewport.addEventListener("touchstart", function (e) {
      if (e.touches.length === 1) {
        if (scale <= 1) return;
        isDragging = true;
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
        startTX = tx; startTY = ty;
      } else if (e.touches.length === 2) {
        e.preventDefault();
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        lastTouchDist = Math.hypot(dx, dy);
      }
    }, { passive: false });
    viewport.addEventListener("touchmove", function (e) {
      if (e.touches.length === 1 && isDragging) {
        e.preventDefault();
        var dx = e.touches[0].clientX - startX;
        var dy = e.touches[0].clientY - startY;
        tx = startTX + dx * 0.85; ty = startTY + dy * 0.85;
        clampTranslate();
        largeImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
      } else if (e.touches.length === 2) {
        e.preventDefault();
        var dx = e.touches[0].clientX - e.touches[1].clientX;
        var dy = e.touches[0].clientY - e.touches[1].clientY;
        var dist = Math.hypot(dx, dy);
        if (lastTouchDist) {
          var ratio = dist / lastTouchDist;
          var cx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
          var cy = (e.touches[0].clientY + e.touches[1].clientY) / 2;
          setScale(clamp(scale * ratio, minScale, maxScale), cx, cy);
        }
        lastTouchDist = dist;
      }
    }, { passive: false });
    viewport.addEventListener("touchend", function (e) {
      if (e.touches.length === 0) { isDragging = false; lastTouchDist = 0; viewport.classList.remove("is-grabbing"); largeImg.classList.remove("is-dragging"); }
      if (e.touches.length === 1) {
        startX = e.touches[0].clientX; startY = e.touches[0].clientY; startTX = tx; startTY = ty;
      }
    });

    document.addEventListener("keydown", function (e) {
      if (!overlay.classList.contains("is-open")) return;
      if (e.key === "Escape") close();
      else if (e.key === "+" || e.key === "=") { e.preventDefault(); setScale(scale + step); }
      else if (e.key === "-" || e.key === "_") { e.preventDefault(); setScale(scale - step); }
      else if (e.key === "0") { e.preventDefault(); reset(); }
    });

    window.addEventListener("resize", function () {
      if (!overlay.classList.contains("is-open")) return;
      var r = largeImg.getBoundingClientRect();
      if (scale > 0) { baseW = r.width / scale; baseH = r.height / scale; }
      clampTranslate(); applyTransform();
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
