#!/usr/bin/env python3
"""Remove mock and copr build status entries for packages.

Environment variables:
  PACKAGE  Comma-separated list of packages (optional; all packages if empty)
"""

import os
import sys

from lib.yaml_utils import get_packages, pop_build_stages

package_env = os.environ.get("PACKAGE", "")
if package_env:
    pkgs = [p.strip() for p in package_env.split(",") if p.strip()]
else:
    pkgs = list(get_packages())

if not pkgs:
    print("nothing to do", file=sys.stderr)
    sys.exit(0)

affected = pop_build_stages(pkgs)
print(f"cleared mock/copr for: {', '.join(affected)}")
