/* arccos (inverse cosine) function with 'long double' argument.

   Copyright (C) 2003-2025 Free Software Foundation, Inc.

   This file is free software: you can redistribute it and/or modify
   it under the terms of the GNU Lesser General Public License as
   published by the Free Software Foundation, either version 3 of the
   License, or (at your option) any later version.

   This file is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU Lesser General Public License for more details.

   You should have received a copy of the GNU Lesser General Public License
   along with this program.  If not, see <https://www.gnu.org/licenses/>.  */

/*
 * ====================================================
 * Copyright (C) 1993 by Sun Microsystems, Inc. All rights reserved.
 *
 * Developed at SunPro, a Sun Microsystems, Inc. business.
 * Permission to use, copy, modify, and distribute this
 * software is freely granted, provided that this notice
 * is preserved.
 * ====================================================
 */

#include <config.h>

/* Specification.  */
#include <math.h>

#if HAVE_SAME_LONG_DOUBLE_AS_DOUBLE

long double
acosl (long double x)
{
  return acos (x);
}

#else

/* Code based on glibc/sysdeps/ieee754/ldbl-128/e_asinl.c
   and           glibc/sysdeps/ieee754/ldbl-128/e_acosl.c.  */

/*
  Long double expansions contributed by
  Stephen L. Moshier <moshier@na-net.ornl.gov>
*/

/* asin(x)
 * Method :
 *      Since  asin(x) = x + x^3/6 + x^5*3/40 + x^7*15/336 + ...
 *      we approximate asin(x) on [0,0.5] by
 *              asin(x) = x + x*x^2*R(x^2)
 *      Between .5 and .625 the approximation is
 *              asin(0.5625 + x) = asin(0.5625) + x rS(x) / sS(x)
 *      For x in [0.625,1]
 *              asin(x) = pi/2-2*asin(sqrt((1-x)/2))
 *
 * Special cases:
 *      if x is NaN, return x itself;
 *      if |x|>1, return NaN with invalid signal.
 *
 */


static const long double
  one = 1.0L,
  huge = 1.0e+4932L,
  pi =      3.1415926535897932384626433832795028841972L,
  pio2_hi = 1.5707963267948966192313216916397514420986L,
  pio2_lo = 4.3359050650618905123985220130216759843812E-35L,
  pio4_hi = 7.8539816339744830961566084581987569936977E-1L,

        /* coefficient for R(x^2) */

  /* asin(x) = x + x^3 pS(x^2) / qS(x^2)
     0 <= x <= 0.5
     peak relative error 1.9e-35  */
  pS0 = -8.358099012470680544198472400254596543711E2L,
  pS1 =  3.674973957689619490312782828051860366493E3L,
  pS2 = -6.730729094812979665807581609853656623219E3L,
  pS3 =  6.643843795209060298375552684423454077633E3L,
  pS4 = -3.817341990928606692235481812252049415993E3L,
  pS5 =  1.284635388402653715636722822195716476156E3L,
  pS6 = -2.410736125231549204856567737329112037867E2L,
  pS7 =  2.219191969382402856557594215833622156220E1L,
  pS8 = -7.249056260830627156600112195061001036533E-1L,
  pS9 =  1.055923570937755300061509030361395604448E-3L,

  qS0 = -5.014859407482408326519083440151745519205E3L,
  qS1 =  2.430653047950480068881028451580393430537E4L,
  qS2 = -4.997904737193653607449250593976069726962E4L,
  qS3 =  5.675712336110456923807959930107347511086E4L,
  qS4 = -3.881523118339661268482937768522572588022E4L,
  qS5 =  1.634202194895541569749717032234510811216E4L,
  qS6 = -4.151452662440709301601820849901296953752E3L,
  qS7 =  5.956050864057192019085175976175695342168E2L,
  qS8 = -4.175375777334867025769346564600396877176E1L,
  /* 1.000000000000000000000000000000000000000E0 */

  /* asin(0.5625 + x) = asin(0.5625) + x rS(x) / sS(x)
     -0.0625 <= x <= 0.0625
     peak relative error 3.3e-35  */
  rS0 = -5.619049346208901520945464704848780243887E0L,
  rS1 =  4.460504162777731472539175700169871920352E1L,
  rS2 = -1.317669505315409261479577040530751477488E2L,
  rS3 =  1.626532582423661989632442410808596009227E2L,
  rS4 = -3.144806644195158614904369445440583873264E1L,
  rS5 = -9.806674443470740708765165604769099559553E1L,
  rS6 =  5.708468492052010816555762842394927806920E1L,
  rS7 =  1.396540499232262112248553357962639431922E1L,
  rS8 = -1.126243289311910363001762058295832610344E1L,
  rS9 = -4.956179821329901954211277873774472383512E-1L,
  rS10 =  3.313227657082367169241333738391762525780E-1L,

  sS0 = -4.645814742084009935700221277307007679325E0L,
  sS1 =  3.879074822457694323970438316317961918430E1L,
  sS2 = -1.221986588013474694623973554726201001066E2L,
  sS3 =  1.658821150347718105012079876756201905822E2L,
  sS4 = -4.804379630977558197953176474426239748977E1L,
  sS5 = -1.004296417397316948114344573811562952793E2L,
  sS6 =  7.530281592861320234941101403870010111138E1L,
  sS7 =  1.270735595411673647119592092304357226607E1L,
  sS8 = -1.815144839646376500705105967064792930282E1L,
  sS9 = -7.821597334910963922204235247786840828217E-2L,
  /*  1.000000000000000000000000000000000000000E0 */

 asinr5625 =  5.9740641664535021430381036628424864397707E-1L;


long double
acosl (long double x)
{
  long double t, p, q;

  if (x < 0.0L)
    {
      t = pi - acosl (-x);
      if (huge + x > one) /* return with inexact */
        return t;
    }

  if (x >= 1.0L)        /* |x|>= 1 */
    {
      if (x == 1.0L)
        return 0.0L;   /* return zero */

      return (x - x) / (x - x); /* asin(|x|>1) is NaN */
    }

  else if (x < 0.5L) /* |x| < 0.5 */
    {
      if (x < 0.000000000000000006938893903907228377647697925567626953125L) /* |x| < 2**-57 */
        /* acos(0)=+-pi/2 with inexact */
        return x * pio2_hi + x * pio2_lo;

      t = x * x;
      p = (((((((((pS9 * t
                   + pS8) * t
                  + pS7) * t
                 + pS6) * t
                + pS5) * t
               + pS4) * t
              + pS3) * t
             + pS2) * t
            + pS1) * t
           + pS0) * t;

      q = (((((((( t
                  + qS8) * t
                 + qS7) * t
                + qS6) * t
               + qS5) * t
              + qS4) * t
             + qS3) * t
            + qS2) * t
           + qS1) * t
        + qS0;

      return pio2_hi - (x + x * (p / q) - pio2_lo);
    }

  else if (x < 0.625) /* 0.625 */
    {
      t = x - 0.5625;
      p = ((((((((((rS10 * t
                    + rS9) * t
                   + rS8) * t
                  + rS7) * t
                 + rS6) * t
                + rS5) * t
               + rS4) * t
              + rS3) * t
             + rS2) * t
            + rS1) * t
           + rS0) * t;

      q = ((((((((( t
                    + sS9) * t
                  + sS8) * t
                 + sS7) * t
                + sS6) * t
               + sS5) * t
              + sS4) * t
             + sS3) * t
            + sS2) * t
           + sS1) * t
        + sS0;

      return (pio2_hi - asinr5625) - (p / q - pio2_lo);
    }
  else
    return 2 * asinl (sqrtl ((1 - x) / 2));
}

#endif

#if 0
int
main (void)
{
  printf ("%.18Lg %.18Lg\n",
          acosl (1.0L),
          1.5707963267948966192313216916397514420984L -
          1.5707963267948966192313216916397514420984L);
  printf ("%.18Lg %.18Lg\n",
          acosl (0.7071067811865475244008443621048490392848L),
          1.5707963267948966192313216916397514420984L -
          0.7853981633974483096156608458198757210492L);
  printf ("%.18Lg %.18Lg\n",
          acosl (0.5L),
          1.5707963267948966192313216916397514420984L -
          0.5235987755982988730771072305465838140328L);
  printf ("%.18Lg %.18Lg\n",
          acosl (0.3090169943749474241022934171828190588600L),
          1.5707963267948966192313216916397514420984L -
          0.3141592653589793238462643383279502884196L);
  printf ("%.18Lg %.18Lg\n",
          acosl (-1.0L),
          1.5707963267948966192313216916397514420984L -
          -1.5707963267948966192313216916397514420984L);
  printf ("%.18Lg %.18Lg\n",
          acosl (-0.7071067811865475244008443621048490392848L),
          1.5707963267948966192313216916397514420984L -
          -0.7853981633974483096156608458198757210492L);
  printf ("%.18Lg %.18Lg\n",
          acosl (-0.5L),
          1.5707963267948966192313216916397514420984L -
          -0.5235987755982988730771072305465838140328L);
  printf ("%.18Lg %.18Lg\n",
          acosl (-0.3090169943749474241022934171828190588600L),
          1.5707963267948966192313216916397514420984L -
          -0.3141592653589793238462643383279502884196L);
}
#endif
