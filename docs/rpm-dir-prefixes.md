# RPM directories prefixes

## Core prefix macros

%{_prefix} -> /usr
%{_exec_prefix} -> /usr
%{_root_prefix} -> /

## Binary and executable paths

%{_bindir} -> /usr/bin
%{_sbindir} -> /usr/sbin
%{_libexecdir} -> /usr/libexec

## Library paths

%{_libdir} -> /usr/lib64 (on x86_64)
%{_lib} -> lib64 (on x86_64)
%{_usr} -> /usr

## Data and shared resources

%{_datadir} -> /usr/share
%{_datarootdir} -> /usr/share
%{_docdir} -> /usr/share/doc
%{_mandir} -> /usr/share/man
%{_infodir} -> /usr/share/info

## Configuration paths

%{_sysconfdir} -> /etc
%{_localstatedir} -> /var
%{_sharedstatedir} -> /var/lib
%{_rundir} -> /run

## Source and build macros

%{_sourcedir} -> ~/rpmbuild/SOURCES
%{_specdir} -> ~/rpmbuild/SPECS
%{_builddir} -> ~/rpmbuild/BUILD
%{_rpmdir} -> ~/rpmbuild/RPMS
%{_srcrpmdir} -> ~/rpmbuild/SRPMS

## System integration

%{_unitdir} -> /usr/lib/systemd/system
%{_userunitdir} -> /usr/lib/systemd/user
%{_tmpfilesdir} -> /usr/lib/tmpfiles.d
%{_sysusersdir} -> /usr/lib/sysusers.d

## Development and pkg-config

%{_includedir} -> /usr/include
%{_pkgconfigdir} -> /usr/lib64/pkgconfig
%{_pkgconfigdatadir} -> /usr/share/pkgconfig
