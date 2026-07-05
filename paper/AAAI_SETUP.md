# AAAI-27 LaTeX Setup & Compile Guide

How to compile `deletion_completeness_aaai.tex` with the **AAAI-27 (AAAI 2027)**
author kit. Verified against the *actual* kit already in this repo at
`paper/AuthorKit27/` (byte-for-byte the official kit: `aaai2027.sty` = 16,915 B,
`aaai2027.bst` = 30,207 B).

> There is **no LaTeX toolchain on this machine** (no `pdflatex`/`bibtex`/
> `latexmk`), so the paper cannot be compiled or page-counted locally. Do the
> compile and the **7-page limit check in Overleaf** (or another TeX install).

---

## (a) Download URLs

| What | URL |
|------|-----|
| Official AAAI-27 author kit (zip: `aaai2027.sty`, `aaai2027.bst`, samples) | https://aaai.org/authorkit27/ |
| AAAI-27 conference / author page | https://aaai.org/conference/aaai/aaai-27/ |
| Overleaf — AAAI templates gallery (pick the **2027** "AAAI Press Formatting Instructions" when browsing) | https://www.overleaf.com/latex/templates/tagged/aaai |
| Overleaf — generic "AAAI Press LaTeX Template" (fallback) | https://www.overleaf.com/latex/templates/aaai-press-latex-template/jymjdgdpdmxp |

You do **not** need to re-download anything: the real kit is already unpacked at
`paper/AuthorKit27/`. As of now there is no confirmed 2027-specific Overleaf URL;
the fastest route is to upload the on-disk kit files (below).

## (b) Files that MUST be present to compile

The paper is self-contained (TikZ diagrams, **no** external image files, no
`\input`/`\include`). To compile, these four files must sit **in the same folder
as the `.tex`** (or the Overleaf project root):

1. `deletion_completeness_aaai.tex`  — the paper (already here)
2. `references.bib`                  — the bibliography database (already here)
3. `aaai2027.sty`                    — **copy from `paper/AuthorKit27/`**
4. `aaai2027.bst`                    — **copy from `paper/AuthorKit27/`**

> ⚠️ **Location gotcha:** in this repo the style/bib-style files live in the
> `AuthorKit27/` **subfolder**, *not* next to the `.tex`. LaTeX resolves
> `\usepackage{aaai2027}` and BibTeX resolves `\bibliographystyle{aaai2027}` by
> looking on the TeX search path / current directory — a plain subfolder is
> **not** searched. So you must **copy (or move) `aaai2027.sty` and
> `aaai2027.bst` next to `deletion_completeness_aaai.tex`** (or into the Overleaf
> project root) before compiling.

Not needed for this paper: `aaai2027.bib` (the kit's *sample* bibliography — we
use `references.bib` instead), the sample `.tex` files, the `Word/` and
`Figures/` folders.

## (c) Two ways to compile in Overleaf

**Option 1 — Upload the kit into a blank project (recommended; uses the real files).**
1. Create a new **Blank Project** in Overleaf.
2. Upload `deletion_completeness_aaai.tex`, `references.bib`, and — from
   `paper/AuthorKit27/` — `aaai2027.sty` and `aaai2027.bst`, all into the
   **project root** (same level, no subfolder).
3. Set the main document to `deletion_completeness_aaai.tex`
   (Menu → Main document).
4. Menu → Compiler → **pdfLaTeX**. Compile.

*(You can instead drag the whole `AuthorKit27.zip` in and let Overleaf unzip it,
but then move `aaai2027.sty`/`aaai2027.bst` up to the project root so they sit
beside the `.tex`.)*

**Option 2 — Start from the AAAI-27 Overleaf template, paste in your content.**
1. Open the AAAI template from Overleaf (gallery link above; choose the 2027
   "AAAI Press Formatting Instructions" version — it already contains
   `aaai2027.sty`/`aaai2027.bst`).
2. Replace the template's `main.tex` body with the body of
   `deletion_completeness_aaai.tex`, and upload `references.bib`.
3. Keep the template's preamble conventions (see the flagged items below so your
   preamble matches: no font packages, `/TemplateVersion (2027.1)` in
   `\pdfinfo`, `\bibliographystyle{aaai2027}` or none).

## (d) Compile order

```
pdflatex  deletion_completeness_aaai
bibtex    deletion_completeness_aaai
pdflatex  deletion_completeness_aaai
pdflatex  deletion_completeness_aaai
```

i.e. **pdflatex → bibtex → pdflatex → pdflatex** (two final pdflatex passes so
citations/labels/cross-refs settle). In Overleaf this whole cycle runs
automatically when the compiler is **pdfLaTeX** (it detects `\bibliography` and
runs BibTeX for you); `latexmk -pdf` does the same. **Check the 7-page main-text
limit here** — it cannot be verified locally.

---

## (e) Preamble items — what was changed and what to review

All changes are confined to the **preamble** of `deletion_completeness_aaai.tex`
plus the single `\bibliographystyle` line. The body was not touched.

### Fixed (clear violations, verified against `AuthorKit27/aaai2027.sty`)

1. **Bibliography style — build-breaking, now fixed.**
   `\bibliographystyle{aaai}`  →  `\bibliographystyle{aaai2027}`
   The kit ships **`aaai2027.bst`** only — there is **no `aaai.bst`**, so the old
   line would make BibTeX fail. `aaai2027.sty` (line 354) already sets
   `\bibliographystyle{aaai2027}` internally, so this line is technically
   redundant and could instead be **deleted** — but keeping it explicit and
   correct is safe and harmless.

2. **Font packages removed.** Deleted `\usepackage{times}`,
   `\usepackage{helvet}`, `\usepackage{courier}`.
   `aaai2027.sty` (lines 64–73) auto-loads the fonts itself
   (`newtxtext` + `helvet` + `courier`) and states *"Authors must not load
   `\usepackage{times}` … or any competing text-font package."* `times`
   conflicts with the kit's `newtxtext`; `helvet`/`courier` were redundant. Both
   kit samples (`AnonymousSubmission2027.tex`, `CameraReady2027.tex`) omit all
   three. A comment noting this was left in place.

3. **`\pdfinfo` — added the mandated version tag.** Added
   `/TemplateVersion (2027.1)` (the exact value both kit samples use). The
   pre-existing `/Title` and `/Author` lines were kept (harmless metadata) — but
   see the anonymization TODO below.

### Flagged for you to decide (`% TODO(AAAI kit)` comments in the .tex)

4. **Submission vs. camera-ready / anonymity.** The paper currently uses
   `\usepackage{aaai2027}` (no option = **camera-ready / non-anonymous**) with
   real author names. AAAI review is **double-blind**. If you are submitting for
   review, you must:
   - change to `\usepackage[submission]{aaai2027}`,
   - anonymize the `\author`/`\affiliations` block, **and**
   - remove the `/Author (...)` line from `\pdfinfo` (otherwise your name leaks
     via PDF metadata).
   Leave it as-is only if this is the accepted **camera-ready**.

### Recommended (not enforced by the sty; optional)

5. **`caption` package.** Both kit samples load `\usepackage{caption}` (no
   options). The paper omits it; the sty does **not** hard-require it, so this is
   optional — add `\usepackage{caption}` if figure/table caption styling looks
   off. (If you add algorithm floats or code listings later, the kit also
   suggests `\usepackage{algorithm}`, `\usepackage{algorithmic}`,
   `\usepackage{newfloat}`, `\usepackage{listings}`.)

### Already compliant — no change needed

- `\documentclass[letterpaper]{article}` ✔ (kit: "DO NOT CHANGE THIS")
- `\usepackage{aaai2027}` present, no disallowed option ✔
- `\frenchspacing` ✔ ; `\setlength{\pdfpagewidth}{8.5in}` / `{11in}` ✔
- `\setcounter{secnumdepth}{2}` ✔ (kit allows 0, or 1/2 if section numbers wanted)
- `\usepackage[hyphens]{url}`, `\urlstyle{rm}`, `\def\UrlFont{\rm}` ✔
- `\usepackage{natbib}` with no options ✔ ; `graphicx`, `booktabs`, `amsmath`,
  `tikz` are all allowed ✔
- **No forbidden packages/commands anywhere.** `aaai2027.sty` hard-errors
  (`\PackageError`) on: `hyperref`, `bbm`, `authblk`, `balance`, `CJK`,
  `flushend`, `fullpage`, `geometry`, `navigator`, `savetrees`, `setspace`,
  `stfloats`, `tabu`, `titlesec`, `tocbibind`, `ulem`, `wrapfig` — none are used.
- **`\nocopyright` is NOT used** — correct. The kit forbids it
  ("Your paper will not be published if you use this command").

### Full disallowed list (from the kit samples, for reference)

- **Packages:** `authblk`, `balance`, `CJK`, `float`, `flushend`, `fullpage`,
  `geometry`, `hyperref`, `navigator`, `indentfirst`, `layout`, `multicol`,
  `nameref`, `savetrees`, `setspace`, `stfloats`, `tabu`, `titlesec`,
  `tocbibind`, `ulem`, `wrapfig` (plus any font package such as `times`).
- **Commands:** `\nocopyright`, `\addtolength`, `\balance`, `\baselinestretch`,
  `\clearpage`, `\columnsep`, `\newpage`, `\pagebreak`, `\pagestyle`, `\tiny`,
  and any negative `\vspace{-...}` / `\vskip{-...}` near a caption, figure,
  table, section heading, or reference.
