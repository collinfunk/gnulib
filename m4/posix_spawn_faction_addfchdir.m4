# posix_spawn_faction_addfchdir.m4
# serial 2
dnl Copyright (C) 2018-2025 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.
dnl This file is offered as-is, without any warranty.

AC_DEFUN([gl_FUNC_POSIX_SPAWN_FILE_ACTIONS_ADDFCHDIR],
[
  AC_REQUIRE([gl_SPAWN_H_DEFAULTS])
  AC_REQUIRE([AC_PROG_CC])
  gl_POSIX_SPAWN
  AC_CHECK_FUNCS_ONCE([posix_spawn_file_actions_addfchdir])
  gl_CHECK_FUNCS_ANDROID([posix_spawn_file_actions_addfchdir_np],
    [[#include <spawn.h>]])
  if test $ac_cv_func_posix_spawn_file_actions_addfchdir = yes; then
    dnl This function is not yet standardized. Therefore override the
    dnl system's implementation always.
    REPLACE_POSIX_SPAWN_FILE_ACTIONS_ADDFCHDIR=1
  else
    HAVE_POSIX_SPAWN_FILE_ACTIONS_ADDFCHDIR=0
  fi
])
