import sys
import os

linux_pkg_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "linux", "lunifier-adwaita"))
if linux_pkg_dir not in sys.path:
    sys.path.insert(0, linux_pkg_dir)
