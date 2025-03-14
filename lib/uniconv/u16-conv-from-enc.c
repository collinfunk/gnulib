/* Conversion to UTF-16 from legacy encodings.
   Copyright (C) 2002, 2006-2007, 2009-2025 Free Software Foundation, Inc.

   This file is free software.
   It is dual-licensed under "the GNU LGPLv3+ or the GNU GPLv2+".
   You can redistribute it and/or modify it under either
     - the terms of the GNU Lesser General Public License as published
       by the Free Software Foundation, either version 3, or (at your
       option) any later version, or
     - the terms of the GNU General Public License as published by the
       Free Software Foundation; either version 2, or (at your option)
       any later version, or
     - the same dual license "the GNU LGPLv3+ or the GNU GPLv2+".

   This file is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Lesser General Public License and the GNU General Public License
   for more details.

   You should have received a copy of the GNU Lesser General Public
   License and of the GNU General Public License along with this
   program.  If not, see <https://www.gnu.org/licenses/>.  */

/* Written by Bruno Haible <bruno@clisp.org>.  */

#include <config.h>

/* Specification.  */
#include "uniconv.h"

#include <errno.h>
#include <stdlib.h>

#include "striconveha.h"
#include "unistr.h"

/* Name of UTF-16 encoding with machine dependent endianness and alignment.  */
#if (defined _LIBICONV_VERSION && !(_LIBICONV_VERSION == 0x10b && defined __APPLE__)) \
    || (((__GLIBC__ > 2) || (__GLIBC__ == 2 && __GLIBC_MINOR__ >= 2)) && !defined __UCLIBC__)
# ifdef WORDS_BIGENDIAN
#  define UTF16_NAME "UTF-16BE"
# else
#  define UTF16_NAME "UTF-16LE"
# endif
#endif

#define FUNC u16_conv_from_encoding
#define UNIT uint16_t
#define U8_TO_U u8_to_u16
#define U_MBLEN u16_mblen
#if defined UTF16_NAME
# define UTF_NAME UTF16_NAME
# define HAVE_UTF_NAME 1
#endif
#include "u-conv-from-enc.h"
