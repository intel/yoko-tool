# We follow the Fedora guide for versioning. Fedora recommends to use something like '1.0-0.rc7' for
# release candidate rc7 and '1.0-1' for the '1.0' release.
%define rc_str %{?rc_num:0.rc%{rc_num}}%{!?rc_num:1}

Name: yoko-tools
Summary: Tools to control the Yokogawa WT310 power meter
Version: 1.2

%if 0%{?opensuse_bs}
Release: %{rc_str}.<CI_CNT>.<B_CNT>
%else
Release: %{rc_str}.0.0
%endif

Group: Development/Tools/Other
License: GPL-2.0
BuildArch: noarch
URL: https://github.com/01org/yoko-tool
Source0: %{name}_%{version}.tar.gz

BuildRequires: python-distribute

%description
This package provides yokotool - a Linux command-line tool for controlling the Yokogawa WT310 power
meter. Namely, it allows for configuring the power meter and reading the measurements data. There
are also python modules which provide the power meter control APIs for external python programs.

%prep
%setup -q -n %{name}-%{version}

%build

%install
rm -rf %{buildroot}

%{__python} setup.py install --prefix=%{_prefix} --root=%{buildroot}

mkdir -p %{buildroot}/%{_mandir}/man1
install -m644 docs/man1/yokotool.1 %{buildroot}/%{_mandir}/man1

%files
%defattr(-,root,root,-)
%dir /usr/lib/python*/site-packages/yokotools
/usr/lib/python*/site-packages/yoko_tools*
/usr/lib/python*/site-packages/yokotools/*
%{_bindir}/*

%doc docs/RELEASE_NOTES COPYING
%{_mandir}/man1/*
