# sigpipe.m4
# serial 3
dnl Copyright (C) 2008-2025 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.
dnl This file is offered as-is, without any warranty.

dnl Tests whether SIGPIPE is provided by <signal.h>.
dnl Sets gl_cv_header_signal_h_SIGPIPE.
AC_DEFUN([gl_SIGNAL_SIGPIPE],
[
  dnl Ensure to expand the default settings once only, before all statements
  dnl that occur in other macros.
  AC_REQUIRE([gl_SIGNAL_SIGPIPE_BODY])
])

AC_DEFUN([gl_SIGNAL_SIGPIPE_BODY],
[
  AC_REQUIRE([AC_PROG_CC])
  AC_CACHE_CHECK([for SIGPIPE], [gl_cv_header_signal_h_SIGPIPE], [
    AC_EGREP_CPP([booboo],[
#include <signal.h>
#if !defined SIGPIPE
booboo
#endif
      ],
      [gl_cv_header_signal_h_SIGPIPE=no],
      [gl_cv_header_signal_h_SIGPIPE=yes])
  ])
])
