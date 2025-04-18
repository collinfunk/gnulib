# passfd.m4
# serial 10
dnl Copyright (C) 2011-2025 Free Software Foundation, Inc.
dnl This file is free software; the Free Software Foundation
dnl gives unlimited permission to copy and/or distribute it,
dnl with or without modifications, as long as this notice is preserved.
dnl This file is offered as-is, without any warranty.

AC_DEFUN([gl_PASSFD],
[
  AC_REQUIRE([gl_SYS_SOCKET_H])
  AC_CHECK_FUNCS_ONCE([recvmsg sendmsg])

  dnl Persuade AIX 5.2 <sys/socket.h> to declare CMSG_SPACE, CMSG_LEN.
  dnl CMSG_FIRSTHDR is POSIX 2008, but CMSG_SPACE is only in RFC 3542.
  AC_DEFINE([_LINUX_SOURCE_COMPAT], [1],
    [Define so that AIX headers are more compatible with GNU/Linux.])

  dnl Passfd prefers the POSIX use of msg.msg_control if the CMSG_* macros
  dnl are present, but can fall back to BSD 4.3 style of msg.msg_accrights.
  AC_CHECK_MEMBERS([struct msghdr.msg_accrights], [], [], [[
    #include <sys/types.h>
    #include <sys/socket.h>
  ]])
])
