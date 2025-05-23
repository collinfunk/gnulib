# strtoumax.m4
# serial 13
dnl Copyright (C) 2002-2004, 2006, 2009-2025 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.
dnl This file is offered as-is, without any warranty.

AC_DEFUN([gl_FUNC_STRTOUMAX],
[
  AC_REQUIRE([gl_INTTYPES_H_DEFAULTS])

  dnl On OSF/1 5.1 with cc, this function is declared but not defined.
  AC_CHECK_FUNCS_ONCE([strtoumax])
  AC_CHECK_DECLS_ONCE([strtoumax])
  if test "$ac_cv_have_decl_strtoumax" = yes; then
    if test "$ac_cv_func_strtoumax" != yes; then
      # HP-UX 11.11 has "#define strtoimax(...) ..." but no function.
      REPLACE_STRTOUMAX=1
    fi
  else
    HAVE_DECL_STRTOUMAX=0
  fi
])

# Prerequisites of lib/strtoumax.c.
AC_DEFUN([gl_PREREQ_STRTOUMAX], [
  AC_CHECK_DECLS([strtoull])
])
