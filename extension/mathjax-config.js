// Must load BEFORE mathjax/tex-chtml.js. The html package provides \class (used to
// attach span ids to equation pieces) and is NOT autoloaded — the loader entry is
// required, and the extension file ships bundled at mathjax/input/tex/extensions/.
window.MathJax = {
  loader: { load: ["[tex]/html"] },
  tex: {
    inlineMath: [["\\(", "\\)"]],
    displayMath: [["\\[", "\\]"]],
    packages: { "[+]": ["html"] },
  },
  chtml: { scale: 1.15 },
  startup: { typeset: false },  // the viewer builds DOM first, then typesets
};
