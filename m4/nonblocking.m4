# nonblocking.m4
# serial 4
dnl Copyright (C) 2011-2025 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.
dnl This file is offered as-is, without any warranty.

dnl Tests whether non-blocking I/O is natively supported by read(), write().
dnl Sets gl_cv_have_nonblocking.
dnl Also tests whether open() supports O_NONBLOCK.
dnl Sets gl_cv_have_open_O_NONBLOCK.
AC_DEFUN([gl_NONBLOCKING_IO],
[
  dnl Ensure to expand the default settings once only, before all statements
  dnl that occur in other macros.
  AC_REQUIRE([gl_NONBLOCKING_IO_BODY])
])

AC_DEFUN([gl_NONBLOCKING_IO_BODY],
[
  AC_REQUIRE([AC_CANONICAL_HOST])
  case "$host_os" in
    mingw* | windows*) gl_cv_have_nonblocking=no ;;
    *)                 gl_cv_have_nonblocking=yes ;;
  esac
  case "$host_os" in
    mingw* | windows*) gl_cv_have_open_O_NONBLOCK=no ;;
    *)                 gl_cv_have_open_O_NONBLOCK=yes ;;
  esac
])
