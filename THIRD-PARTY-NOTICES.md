# Third-party components

Timed LMB Trigger's Python source uses the Python standard library, Tkinter, and Windows APIs. A Windows executable built with `build.bat` packages a Python runtime and Tcl/Tk support files; PyInstaller and its build dependencies are used to create the executable. The exact bundled runtime versions depend on the Python installation used for the build.

These components are not authored by this project, and this file does not replace their licenses. Before distributing a built executable, include the applicable upstream license and acknowledgement files from the exact Python/Tcl/Tk build used. The official references are [Python's license and acknowledgements](https://docs.python.org/3/license.html) and [PyInstaller's license](https://pyinstaller.org/en/stable/license.html). PyInstaller's license page explains its GPLv2 exception and the condition that bundled dependencies must also be respected.

The project `LICENSE` is intended to cover only original Timed LMB Trigger code (MIT, © 2026 Timed LMB Trigger contributors). It does not relicense Python, Tcl/Tk, PyInstaller, Windows components, or third-party build dependencies.
