# 0.1.3 PDF loading regression

The 0.1.2 browser smoke used the Vite development server without the production
Content Security Policy. The packaged reader fetched a token-protected source,
created a blob URL, then asked PDF.js to fetch that URL again. `connect-src`
blocked this second fetch. A valid two-page synthetic PDF reproduced the user's
exact error when the built frontend was served with the unmodified Tauri CSP.

The reader now passes authenticated source bytes to PDF.js. It does not relax
CSP or use an external viewer. Canonical font/CMap/WASM URLs resolve against
the app origin. Separate PDF and note error states prevent note API failures
from masquerading as damaged documents, and each Retry reruns its own loader.

`scripts/smoke_pdf_reader.mjs` serves the actual production build with the
configured desktop CSP, simulates the desktop connection/token and uses only
a synthetic PDF and in-memory notes. It checks real nonblank canvas rendering,
page navigation, Unicode source filenames, note save/reopen, a transient PDF
failure/retry, independent note failure/retry, and absence of policy violations
in Chromium and WebKit. The release workflow requires this check before it
publishes installers. No production workspace or original PDF is modified.

There is no database migration; schema 11 and the app's identity/data paths
remain unchanged. Existing documents and notes do not need reimporting.

Local verification: production-CSP regression passed in both Chromium and
WebKit; frontend unit tests and English/German parity checks passed; the
TypeScript/Vite build and Rust check passed. The desktop and signed-release
workflows both require the new PDF browser regression.
