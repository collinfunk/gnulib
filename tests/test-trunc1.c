/* Test of rounding towards zero.
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

/* Written by Bruno Haible <bruno@clisp.org>, 2007.  */

#include <config.h>

#include <math.h>

#include "signature.h"
SIGNATURE_CHECK (trunc, double, (double));

#include "isnand-nolibm.h"
#include "minus-zero.h"
#include "infinity.h"
#include "nan.h"
#include "macros.h"

int
main ()
{
  /* Zero.  */
  ASSERT (trunc (0.0) == 0.0);
  ASSERT (trunc (minus_zerod) == 0.0);
  /* Positive numbers.  */
  ASSERT (trunc (0.3) == 0.0);
  ASSERT (trunc (0.7) == 0.0);
  ASSERT (trunc (1.0) == 1.0);
  ASSERT (trunc (1.5) == 1.0);
  ASSERT (trunc (1.999) == 1.0);
  ASSERT (trunc (2.0) == 2.0);
  ASSERT (trunc (65535.999) == 65535.0);
  ASSERT (trunc (65536.0) == 65536.0);
  ASSERT (trunc (2.341e31) == 2.341e31);
  /* Negative numbers.  */
  ASSERT (trunc (-0.3) == 0.0);
  ASSERT (trunc (-0.7) == 0.0);
  ASSERT (trunc (-1.0) == -1.0);
  ASSERT (trunc (-1.5) == -1.0);
  ASSERT (trunc (-1.999) == -1.0);
  ASSERT (trunc (-2.0) == -2.0);
  ASSERT (trunc (-65535.999) == -65535.0);
  ASSERT (trunc (-65536.0) == -65536.0);
  ASSERT (trunc (-2.341e31) == -2.341e31);
  /* Infinite numbers.  */
  ASSERT (trunc (Infinityd ()) == Infinityd ());
  ASSERT (trunc (- Infinityd ()) == - Infinityd ());
  /* NaNs.  */
  ASSERT (isnand (trunc (NaNd ())));

  return test_exit_status;
}
