# Features

- `-debuginfo` packages add
- packages.yaml additional checks:
  - *.so must be in .packages.NAME.files
  - *.debug must be in .packages.NAME.debuginfo.files
  - %{_includedir}, *.pc, *.hpp, *.gir, *.deps, *.vapi must be in .packages.NAME.devel.files
