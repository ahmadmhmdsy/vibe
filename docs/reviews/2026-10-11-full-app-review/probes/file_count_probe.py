
import pathlib
from vibe.workspace import relative_files
root = pathlib.Path(r"C:\Users\AhmadMhmoud\vibe-workspaces\2943b651ae98")
if not root.exists():
    print("E2E workspace missing:", root)
else:
    files = list(relative_files(root))
    ignored = [f for f in files if "node_modules" in f]
    print("workspace exists:", root)
    print("total paths returned by the shared walk:", len(files))
    print("paths under node_modules:", len(ignored))
    print("sample:", files[:6])
