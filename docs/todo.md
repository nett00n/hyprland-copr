# Features

- `-debuginfo` packages add
- packages.yaml additional checks(add to full-cycle as prep-step):
  - general validity
  - *.so must be in .packages.NAME.files
  - *.debug must be in .packages.NAME.debuginfo.files
  - %{_includedir}, *.pc, *.hpp, *.gir, *.deps, *.vapi must be in .packages.NAME.devel.files
- depends_on field. Ensure package is already built or incluede it in full-cycle build
- case-insensity PACKAGE environment in Makefile
- check if .gitmodules stores all modules in ./submodules/
- check if all submodules are in http-format only
