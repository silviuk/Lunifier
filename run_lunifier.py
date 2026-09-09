import io
import sys

# When running with console=False on Windows, sys.stdout and sys.stderr can be None.
# Provide dummy streams to protect external libraries from AttributeError.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from lunifier.app import main

if __name__ == "__main__":
    main()

