/* strerror.c --- POSIX compatible system error routine

   Copyright (C) 2007-2025 Free Software Foundation, Inc.

   This file is free software: you can redistribute it and/or modify
   it under the terms of the GNU Lesser General Public License as
   published by the Free Software Foundation; either version 2.1 of the
   License, or (at your option) any later version.

   This file is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

#include <config.h>

/* Specification.  */
#include <string.h>

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "intprops.h"
#include "strerror-override.h"

/* Use the system functions, not the gnulib overrides in this file.  */
#undef sprintf

/* macOS 12's "warning: 'sprintf' is deprecated" is pointless,
   as sprintf is used safely here.  */
#if defined __APPLE__ && defined __MACH__ && _GL_GNUC_PREREQ (4, 2)
# pragma GCC diagnostic ignored "-Wdeprecated-declarations"
#endif

char *
strerror (int n)
#undef strerror
{
  static char buf[STACKBUF_LEN];
  size_t len;

  /* Cast away const, due to the historical signature of strerror;
     callers should not be modifying the string.  */
  const char *msg = strerror_override (n);
  if (msg)
    return (char *) msg;

  msg = strerror (n);

  /* Our strerror_r implementation might use the system's strerror
     buffer, so all other clients of strerror have to see the error
     copied into a buffer that we manage.  This is not thread-safe,
     even if the system strerror is, but portable programs shouldn't
     be using strerror if they care about thread-safety.  */
  if (!msg || !*msg)
    {
      static char const fmt[] = "Unknown error %d";
      static_assert (sizeof buf >= sizeof (fmt) + INT_STRLEN_BOUND (n));
      sprintf (buf, fmt, n);
      errno = EINVAL;
      return buf;
    }

  /* Fix STACKBUF_LEN if this ever aborts.  */
  len = strlen (msg);
  if (sizeof buf <= len)
    abort ();

  memcpy (buf, msg, len + 1);
  return buf;
}
