# Licensing and redistribution

Colloquily's original code and documentation use **Apache-2.0**, as specified by
the project owner. The canonical text is in [LICENSE](../LICENSE); attribution
is in [NOTICE](../NOTICE). Apache-2.0 preserves a permissive project license and
provides an explicit patent grant. MIT would also suit original application
code, but Apache-2.0 follows the owner's stated preference.

Dependencies retain their licenses; they are not relicensed as Apache-2.0.

| Components | License treatment |
|---|---|
| React, FastAPI, FAISS and most runtime packages | MIT/BSD and other permissive licenses; retain copyright and license texts |
| pypdfium2 and PDFium | Apache/BSD binding licenses plus the native wheel's dependency notices |
| Python interpreter | Full PSF and historical interpreter license texts |
| PyInstaller bootloader | GPL-2.0-or-later **with the bootloader exception**, permitting differently licensed applications; preserve the exception |
| certifi and MPL-covered Rust dependencies | MPL-2.0 applies to those files, not Colloquily's independent source files; corresponding covered sources are provided |
| Some GCC/native runtime notices | Preserve the applicable runtime exception where included by native wheels |

PyMuPDF, Marker, Surya and their AGPL dependencies are not distribution
dependencies. Generation fails on AGPL package metadata or actual AGPL license
headings, and refuses missing license texts. Legacy parser names are accepted
only to normalize saved settings to PDFium, not to load removed dependencies.

Each native build inventories its actual frozen Python graph and target-specific
Rust dependency graph, along with the production npm graph. The inventory also
retains Vite, Rollup, esbuild and TypeScript notices for emitted runtime helpers.
`scripts/release_notices.py` and `scripts/runtime_notices.py` produce full notices, versioned inventories,
and `MPL-SOURCES.zip`. Notices omitted by crate archives are retrieved from their
recorded upstream VCS commit. MPL source headers can additionally refer to the
canonical full Mozilla license text; both those headers and the covered source
files are preserved.

One reviewed, version-specific notice under `licenses/overrides/` addresses
`sigchld 0.2.5`: its crate manifest explicitly declares MIT and its author, but
the upstream archive/repository omit a standalone license file. The notice
reproduces the corresponding MIT terms and author attribution; the collector
checks the exact version, declaration and VCS SHA before using it. Other missing
notices remain build errors, not a generic metadata-only fallback.

Every installer includes the `licenses/` resources. The release also contains
three platform-specific `licenses-*.zip` assets with these same notices and
covered sources. **Download the matching license bundle with the installer.**
MPL source files remain under MPL-2.0; recipients may exercise their rights to
those sources independently of Colloquily's Apache-2.0 license.

Course material, user workspaces and model weights are not included in releases.
Models downloaded separately through Ollama retain their upstream model terms.
Apache-2.0 does not grant redistribution rights to users' course documents or
change any model license.

Primary references:

- [Apache license and application guidance](https://www.apache.org/legal/apply-license.html)
- [PDFium/pypdfium2 distribution requirements](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing)
- [PyInstaller licensing and bootloader exception](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt)
- [Mozilla's MPL distribution and Apache-combination FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)

This is a repository-grounded license inventory, not a legal warranty. Review
the generated inventory again whenever dependencies or native builds change.
