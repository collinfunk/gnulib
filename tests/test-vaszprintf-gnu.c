/* Test of POSIX and GNU compatible vaszprintf() and aszprintf() functions.
   Copyright (C) 2007-2025 Free Software Foundation, Inc.

   This program is free software: you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation, either version 3 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

/* Written by Bruno Haible <bruno@clisp.org>, 2024.  */

/* This test exercises only a few POSIX compliance problems that are still
   visible on platforms relevant in 2024.  For a much more complete test suite,
   see test-vasprintf-posix.c.  */

#include <config.h>

#include <stdio.h>

#include <stdarg.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#include "macros.h"

#include "test-vaszprintf-gnu.h"

static ptrdiff_t
my_aszprintf (char **result, const char *format, ...)
{
  va_list args;
  ptrdiff_t ret;

  va_start (args, format);
  ret = vaszprintf (result, format, args);
  va_end (args);
  return ret;
}

static void
test_vaszprintf ()
{
  test_function (my_aszprintf);
}

static void
test_aszprintf ()
{
  test_function (aszprintf);
}

int
main (int argc, char *argv[])
{
  test_vaszprintf ();
  test_aszprintf ();
  return test_exit_status;
}
