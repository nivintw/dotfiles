# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function __launch_docs_port_open --description "Exit 0 if something is listening on localhost:PORT"
    # Dependency-free TCP probe via python3 — already required to serve the docs site, so
    # launch-docs' port-in-use preflight and its readiness poll behave identically on
    # macOS/Linux/WSL with no reliance on `nc` (not guaranteed on a minimal Linux/WSL box).
    # Exit 0 = a listener accepted the connection (port in use / server ready); exit 1 = refused
    # or unreachable (port free / not ready yet). A short timeout keeps the poll loop responsive.
    python3 -c '
import socket, sys

sock = socket.socket()
sock.settimeout(0.2)
try:
    sock.connect(("localhost", int(sys.argv[1])))
except OSError:
    sys.exit(1)
finally:
    sock.close()
sys.exit(0)
' $argv[1]
end
