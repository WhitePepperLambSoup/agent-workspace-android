# Android PDF and Visible Storage Implementation Plan

**Goal:** Read real Chinese/scanned PDFs, create valid PDFs and expose existing workspaces to Android file browsers.

**Architecture:** Keep the shared pypdf reader for reliable text and diagnose missing mappings, blank pages and parse failures. Android document tools stage checked snapshots in UUID private native jobs. PdfRenderer and bundled Chinese ML Kit supply OCR/page images; PdfDocument supplies paginated text PDFs. Python owns workspace CAS, rollback checkpoints and output receipts. A DocumentsProvider exposes allowed workspace files without moving user data.

**Constraints:** No model training; no unrelated process changes; do not reinstall while user tasks are active; preserve existing workspace/session data and frozen training files.

- [ ] Add real PDF regression fixtures for text, CJK mapping, missing ToUnicode, scanned/blank, damaged/encrypted pages and selected page ranges. Run failures before repairing the shared reader.
- [ ] Add an off-main-thread native document bridge and real device tests. Only private UUID jobs, fixed filenames, bounded rendering/ML Kit OCR and native text pagination are supported.
- [ ] Add Android read_document fallback, render_pdf and create_pdf tools with snapshot identity checks, native output validation, repeated-cancellation settlement, CAS and file/image events. Test OCR fallbacks, page ranges, failures and cross-workspace safety with a bridge fixture.
- [ ] Register only runnable native tools and guide cloud/local tasks to read_document/create_pdf instead of shell binary editing.
- [ ] Expose workspace files through the Android system document provider and add file-browser navigation/public folder guidance. Preserve restricted internal files and unrelated workspaces.
- [ ] Run affected Python/Web tests and native generation/render/OCR/storage tests; visually inspect rendered Chinese PDF and install the next APK when the phone task has finished.

PDF creation initially covers paginated text with title and A4 layout. PDF replacement requires the existing SHA and a durable checkpoint. OCR reports its method and possible recognition errors; empty or encrypted documents never masquerade as successful text extraction. Rendering alone is not OCR and images require a model with vision support.
