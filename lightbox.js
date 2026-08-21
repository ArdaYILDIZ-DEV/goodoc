// lightbox.js — image lightbox overlay: zoom, pan, keyboard and touch support.
// Only the <img> transforms (translate -> scale); caption and toolbar stay fixed.
(function () {
  "use strict";
  // Guard against double init (e.g., hot reload or duplicate script tag)
  if (window.__lightboxInit) return;
  window.__lightboxInit = true;

  // Build the overlay DOM and wire all events; no-op without eligible images.
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
    var minScale = 1, maxScale = 1.5, step = 0.15;
    var baseW = 0, baseH = 0;
    var lastFocus = null;
    var isDragging = false, startX = 0, startY = 0, startTX = 0, startTY = 0;
    var globalAttached = false;

    function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

    // Live zoom percentage for the toolbar.
    function updateLevel() {
      zoomLevelEl.textContent = Math.round(scale * 100) + "%";
    }
    // translate runs before scale so pan distances stay in screen pixels;
    // snap back to a clean 100% when zoomed out.
    function applyTransform() {
      largeImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
      updateLevel();
      viewport.style.cursor = scale > 1 ? "grab" : "zoom-in";
      if (scale <= 1.01) {
        tx = 0; ty = 0;
        largeImg.style.transform = "translate(0px,0px) scale(1)";
      }
    }
    // Pan range per axis: (visual size - viewport) / 2, in screen pixels.
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
    // Keep the pan offset inside bounds.
    function clampTranslate() {
      var b = getBounds();
      tx = clamp(tx, -b.maxX, b.maxX);
      ty = clamp(ty, -b.maxY, b.maxY);
    }
    // Zoom to newScale; when (cx, cy) is given, the point under it stays put.
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
    // Back to the default centered 150% view.
    function reset() {
      scale = 1.5; tx = 0; ty = 0; // default 150% — restore to initial zoom, centered
      largeImg.classList.remove("is-dragging");
      viewport.classList.remove("is-grabbing");
      applyTransform();
    }

    // Start dragging; only meaningful while zoomed in.
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
    // Drag with damping (0.85) for a slightly weighted feel.
    function onPointerMove(e) {
      if (!isDragging) return;
      var dx = e.clientX - startX;
      var dy = e.clientY - startY;
      tx = startTX + dx * 0.85;
      ty = startTY + dy * 0.85;
      clampTranslate();
      largeImg.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
    }
    // End dragging and clear grabbing styles.
    function onPointerUp() {
      if (!isDragging) return;
      isDragging = false;
      largeImg.classList.remove("is-dragging");
      viewport.classList.remove("is-grabbing");
    }
    // Track mouse globally only while the overlay is open; idempotent.
    function attachGlobal() {
      if (globalAttached) return;
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      globalAttached = true;
    }
    // Drop the global listeners.
    function detachGlobal() {
      if (!globalAttached) return;
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      globalAttached = false;
    }

    // Open the overlay: swap src, show caption, lock body scroll, measure after layout.
    function open(src, alt, caption) {
      largeImg.src = src;
      largeImg.alt = alt || "";
      captionEl.textContent = caption || alt || "";
      captionEl.style.display = captionEl.textContent ? "block" : "none";
      overlay.classList.add("is-open");
      overlay.setAttribute("aria-hidden", "false");
      lastFocus = document.activeElement;
      scale = 1.5; tx = 0; ty = 0;
      largeImg.style.transform = "translate(0px,0px) scale(1.5)";
      updateLevel();
      document.body.style.overflow = "hidden";
      attachGlobal();
      // Friendly fallback if the enlarged image fails to load.
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
    // Close: restore focus and scroll; delayed reset lets the fade-out finish.
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

    // Normalize wheel deltas across deltaMode (line/page) for consistent zoom speed.
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
      if (scale > 1.01) setScale(1, e.clientX, e.clientY);
      else setScale(1.5, e.clientX, e.clientY);
    });

    viewport.addEventListener("mousedown", onPointerDown);

    // Touch: one finger pans while zoomed, two fingers pinch-zoom.
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

    // Keyboard shortcuts: + / - zoom, 0 reset, Esc close.
    document.addEventListener("keydown", function (e) {
      if (!overlay.classList.contains("is-open")) return;
      if (e.key === "Escape") close();
      else if (e.key === "+" || e.key === "=") { e.preventDefault(); setScale(scale + step); }
      else if (e.key === "-" || e.key === "_") { e.preventDefault(); setScale(scale - step); }
      else if (e.key === "0") { e.preventDefault(); reset(); }
    });

    // Re-measure on resize so pan bounds stay valid.
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
