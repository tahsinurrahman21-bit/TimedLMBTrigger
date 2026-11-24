r"""Copy upstream license files for the components bundled into the Windows EXE.

Used by release.bat and the GitHub release workflow. Run it with the same Python
interpreter that built the executable, passing the destination folder:

    python tools\collect_licenses.py release\staging\licenses
"""
from importlib import metadata
from pathlib import Path
import shutil
import sys


def copy(src, dest_dir, name):
    src = Path(src)
    if src.is_file():
        shutil.copyfile(src, dest_dir / name)
        print(f"  + {name}")
        return True
    return False


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: collect_licenses.py <destination-folder>")
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)
    base = Path(sys.base_prefix)

    found = copy(base / "LICENSE.txt", dest, "Python-LICENSE.txt")
    for folder in sorted((base / "tcl").glob("tcl8*")):
        found |= copy(folder / "license.terms", dest, "Tcl-license.terms")
    for folder in sorted((base / "tcl").glob("tk8*")):
        found |= copy(folder / "license.terms", dest, "Tk-license.terms")

    try:
        dist = metadata.distribution("pyinstaller")
        for f in dist.files or []:
            if Path(str(f)).name.upper().startswith(("COPYING", "LICENSE")):
                copy(dist.locate_file(f), dest, "PyInstaller-" + Path(str(f)).name)
    except metadata.PackageNotFoundError:
        print("  ! PyInstaller is not installed in this interpreter")

    if not found:
        sys.exit("Could not find Python/Tcl/Tk license files next to this interpreter.")


if __name__ == "__main__":
    main()
