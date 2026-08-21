/* Paste into the browser console on any Casset page.
 *
 * Reports horizontal overflow — which on a phone is always a bug — and
 * names the element responsible by detaching each top-level node in turn
 * rather than guessing from bounding boxes, which lie once the document
 * has already scrolled sideways.
 */
(() => {
  const vw = document.documentElement.clientWidth;
  const base = document.documentElement.scrollWidth;
  const culprits = [];
  [...document.body.children].forEach((child) => {
    const marker = document.createComment("qa");
    child.replaceWith(marker);
    const without = document.documentElement.scrollWidth;
    marker.replaceWith(child);
    if (without < base) {
      culprits.push({
        tag: child.tagName,
        cls: (child.getAttribute("class") || "").slice(0, 40),
        id: child.id,
        scrollWidthWithout: without,
      });
    }
  });
  return { viewport: vw, scrollWidth: base, overflow: base - vw, culprits };
})();
