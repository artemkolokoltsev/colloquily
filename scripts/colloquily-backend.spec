# Native build recipe. Keep mutable application data and model weights out.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
sys.path[:0] = [str(root), str(root / 'backend/core')]
faiss_data, faiss_binaries, faiss_imports = collect_all('faiss')
datas = [(str(root / 'backend/core/prompts'), 'prompts')]
datas += copy_metadata('tqdm') + faiss_data
hiddenimports = collect_submodules('backend', filter=lambda name: not name.startswith('backend.tests'))
hiddenimports += collect_submodules('services') + faiss_imports

a = Analysis([str(root / 'backend/launcher.py')],
    pathex=[str(root), str(root / 'backend/core')], binaries=faiss_binaries,
    datas=datas, hiddenimports=hiddenimports,
    # Optional training, cloud, notebook and plotting packages are not runtime
    # dependencies of the local Ollama/LM Studio desktop application.
    excludes=['tensorflow', 'keras', 'matplotlib', 'pandas', 'boto3', 'botocore',
              'IPython', 'notebook', 'jupyter', 'pytest', 'tkinter', 'torchaudio',
              'sentence_transformers', 'transformers', 'torch', 'sklearn', 'scipy',
              'huggingface_hub', 'pkg_resources', 'setuptools', 'fitz', 'pymupdf', 'pymupdf4llm', 'marker', 'surya'],
    noarchive=False)

if sys.platform == 'darwin':
    import faiss
    omp = Path(faiss.__file__).parent / '.dylibs/libomp.dylib'
    if omp.exists():
        # PyInstaller may resolve identical libomp install names to sklearn's
        # older runtime, which lacks symbols required by FAISS. All collected
        # copies must use FAISS's runtime; the post-build self-test verifies it.
        a.binaries = [(dest, str(omp) if Path(dest).name == 'libomp.dylib' and kind == 'BINARY' else source, kind)
                      for dest, source, kind in a.binaries]

pyz = PYZ(a.pure)
sys.path.insert(0, str(root/'scripts'))
from runtime_notices import collect_notices
notices = collect_notices([item[0] for item in a.pure], root/'build/release-notices')
a.datas += [(f'licenses/{file.name}', str(file), 'DATA') for file in notices.iterdir() if file.suffix in {'.txt', '.json'}]
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='colloquily-backend',
    console=True, strip=False, upx=False,
    codesign_identity=__import__('os').environ.get('COLLOQUILY_CODESIGN_IDENTITY'))
