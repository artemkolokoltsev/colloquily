# Native build recipe. Keep mutable application data and model weights out.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
sys.path[:0] = [str(root), str(root / 'meditech_rag')]
faiss_data, faiss_binaries, faiss_imports = collect_all('faiss')
datas = [(str(root / 'meditech_rag/prompts'), 'prompts'),
         (str(root / 'meditech_rag/configs'), 'configs')]
datas += collect_data_files('sentence_transformers') + collect_data_files('transformers')
datas += copy_metadata('tqdm') + faiss_data
hiddenimports = collect_submodules('backend', filter=lambda name: not name.startswith('backend.tests'))
hiddenimports += collect_submodules('services') + faiss_imports

a = Analysis([str(root / 'backend/launcher.py')],
    pathex=[str(root), str(root / 'meditech_rag')], binaries=faiss_binaries,
    datas=datas, hiddenimports=hiddenimports,
    # Optional training, cloud, notebook and plotting packages are not runtime
    # dependencies of the text-only sentence-transformer/Ollama application.
    excludes=['tensorflow', 'keras', 'matplotlib', 'pandas', 'boto3', 'botocore',
              'IPython', 'notebook', 'jupyter', 'pytest', 'tkinter', 'torchaudio'],
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
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='colloquily-backend',
    console=True, strip=False, upx=False,
    codesign_identity=__import__('os').environ.get('COLLOQUILY_CODESIGN_IDENTITY'))
