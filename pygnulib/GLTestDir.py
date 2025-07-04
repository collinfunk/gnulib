# Copyright (C) 2002-2025 Free Software Foundation, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

#===============================================================================
# Define global imports
#===============================================================================
import os
import re
import sys
import shlex
import subprocess as sp
from pathlib import Path
from .constants import (
    DIRS,
    TESTS,
    UTILS,
    combine_lines,
    execute,
    ensure_writable,
    force_output,
    hardlink,
    joinpath,
    link_relative,
    lines_to_multiline,
    movefile,
    copyfile,
    substart,
    bold_escapes,
    relinverse,
    rmtree,
)
from .functions import rewrite_file_name
from .enums import CopyAction
from .GLError import GLError
from .GLConfig import GLConfig
from .GLModuleSystem import GLModuleTable, GLModuleSystem
from .GLFileSystem import GLFileSystem
from .GLMakefileTable import GLMakefileTable
from .GLEmiter import GLEmiter
from .GLFileTable import GLFileTable


def _patch_test_driver() -> None:
    '''Patch the test-driver script in testdirs.'''
    test_driver = joinpath('build-aux', 'test-driver')
    print('patching file %s' % test_driver)
    diffs = [ joinpath(DIRS['root'], name)
              for name in [joinpath('build-aux', 'test-driver.diff'),
                           joinpath('build-aux', 'test-driver-1.16.3.diff')] ]
    patched = False
    for diff in diffs:
        command = f'patch {shlex.quote(test_driver)} < {shlex.quote(diff)}'
        try:
            result = sp.call(command, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL)
        except OSError as exc:
            if os.path.isfile(f'{test_driver}.orig'):
                os.remove(f'{test_driver}.orig')
            if os.path.isfile(f'{test_driver}.rej'):
                os.remove(f'{test_driver}.rej')
            raise GLError(20, None) from exc
        if result == 0:
            patched = True
            break
        if os.path.isfile(f'{test_driver}.orig'):
            os.remove(f'{test_driver}.orig')
        if os.path.isfile(f'{test_driver}.rej'):
            os.remove(f'{test_driver}.rej')
    if not patched:
        raise GLError(20, None)
    if os.path.isfile(f'{test_driver}.orig'):
        os.remove(f'{test_driver}.orig')


#===============================================================================
# Define GLTestDir class
#===============================================================================
class GLTestDir:
    '''GLTestDir class is used to create a scratch package with the given
    list of the modules.'''

    config: GLConfig
    testdir: str
    emitter: GLEmiter
    filesystem: GLFileSystem
    modulesystem: GLModuleSystem
    makefiletable: GLMakefileTable

    def __init__(self, config: GLConfig, testdir: str) -> None:
        '''Create new GLTestDir instance.'''
        if type(config) is not GLConfig:
            raise TypeError('config must be a GLConfig, not %s'
                            % type(config).__name__)
        if type(testdir) is not str:
            raise TypeError('testdir must be a string, not %s'
                            % type(testdir).__name__)
        self.config = config
        self.testdir = os.path.normpath(testdir)
        # Don't overwrite the directory.
        if os.path.exists(self.testdir):
            raise GLError(22, self.testdir)
        # Try to create directory.
        try:
            os.mkdir(self.testdir)
        except Exception as exc:
            raise GLError(19, self.testdir) from exc
        self.emitter = GLEmiter(self.config)
        self.filesystem = GLFileSystem(self.config)
        self.modulesystem = GLModuleSystem(self.config)
        self.makefiletable = GLMakefileTable(self.config)

        # Subdirectory names.
        self.config.setSourceBase('gllib')
        self.config.setM4Base('glm4')
        self.config.setDocBase('gldoc')
        self.config.setTestsBase('gltests')
        self.config.setMacroPrefix('gl')
        self.config.resetPoBase()
        self.config.resetPoDomain()
        self.config.resetWitnessCMacro()
        self.config.resetVCFiles()

    def execute(self) -> None:
        '''Create a scratch package with the given modules.'''
        auxdir = self.config['auxdir']
        sourcebase = self.config['sourcebase']
        m4base = self.config['m4base']
        testsbase = self.config['testsbase']
        libname = self.config['libname']
        libtool = self.config['libtool']
        single_configure = self.config['single_configure']
        macro_prefix = self.config['macro_prefix']
        verbose = self.config['verbosity']

        specified_modules = self.config['modules']
        if len(specified_modules) == 0:
            # All modules together, except those that are not usable in a testdir.
            specified_modules = self.modulesystem.list()
            specified_modules = [ module_name
                                  for module_name in specified_modules
                                  if self.modulesystem.find(module_name) is not None \
                                      and self.modulesystem.find(module_name).getUsabilityInTestdir() != 'no' ]

        # Canonicalize the list of specified modules.
        modules = set()
        for module_name in specified_modules:
            module = self.modulesystem.find(module_name)
            if module is not None:
                if module.getUsabilityInTestdir() == 'no':
                    if self.config['errors']:
                        raise GLError(24, module_name)
                    else:  # if not self.config['errors']
                        sys.stderr.write('gnulib-tool: warning: ')
                        sys.stderr.write('module %s cannot be used in a testdir\n' % module_name)
                else:
                    modules.add(module)
        specified_modules = sorted(modules)

        # Test modules which invoke AC_CONFIG_FILES cannot be used with --with-tests
        # (without --two-configures). Avoid them.
        inctests = self.config.checkInclTestCategory(TESTS['tests'])
        if inctests and self.config.checkSingleConfigure():
            self.config.addAvoid('havelib-tests')

        # Now it's time to create the GLModuleTable.
        moduletable = GLModuleTable(self.config,
                                    True,
                                    self.config.checkInclTestCategory(TESTS['all-tests']))

        # When computing transitive closures, don't consider $module to depend on
        # $module-tests. Need this because tests are implicitly GPL and may depend
        # on GPL modules - therefore we don't want a warning in this case.
        saved_inctests = self.config.checkInclTestCategory(TESTS['tests'])
        self.config.disableInclTestCategory(TESTS['tests'])
        for requested_module in specified_modules:
            requested_licence = requested_module.getLicense()
            if requested_licence != 'GPL':
                # Here we use moduletable.transitive_closure([module]), not
                # just module.getDependencies, so that we also detect weird
                # situations like an LGPL module which depends on a GPLed build
                # tool module which depends on a GPL module.
                modules = moduletable.transitive_closure([requested_module])
                for module in modules:
                    license = module.getLicense()
                    if license not in ['GPLv2+ build tool', 'GPLed build tool',
                                       'public domain', 'unlimited', 'unmodifiable license text']:
                        incompatible = False
                        if requested_licence == 'GPLv3+' or requested_licence == 'GPL':
                            if license not in ['LGPLv2+', 'LGPLv3+ or GPLv2+', 'LGPLv3+', 'LGPL', 'GPLv2+', 'GPLv3+', 'GPL']:
                                incompatible = True
                        elif requested_licence == 'GPLv2+':
                            if license not in ['LGPLv2+', 'LGPLv3+ or GPLv2+', 'GPLv2+']:
                                incompatible = True
                        elif requested_licence == 'LGPLv3+' or requested_licence == 'LGPL':
                            if license not in ['LGPLv2+', 'LGPLv3+ or GPLv2+', 'LGPLv3+', 'LGPL']:
                                incompatible = True
                        elif requested_licence == 'LGPLv3+ or GPLv2+':
                            if license not in ['LGPLv2+', 'LGPLv3+ or GPLv2+']:
                                incompatible = True
                        elif requested_licence == 'LGPLv2+':
                            if license not in ['LGPLv2+']:
                                incompatible = True
                        if incompatible:
                            warningmsg = 'module %s depends on a module with an incompatible license: %s' % (requested_module, module)
                            sys.stderr.write('gnulib-tool: warning: %s\n' % warningmsg)
        self.config.setInclTestCategory(TESTS['tests'], saved_inctests)

        # Determine final module list.
        modules = moduletable.transitive_closure(specified_modules)
        final_modules = list(modules)

        # Show final module list.
        if verbose >= 0:
            (bold_on, bold_off) = bold_escapes()
            print('Module list with included dependencies (indented):')
            specified_modules_set = { module.name
                                      for module in specified_modules }
            for module in final_modules:
                if module.name in specified_modules_set:
                    print('  %s%s%s' % (bold_on, module.name, bold_off))
                else:  # if module.name not in specified_modules_set
                    print('    %s' % module.name)

        # Generate lists of the modules.
        if single_configure:
            # Determine main module list and tests-related module list separately.
            main_modules, tests_modules = \
                moduletable.transitive_closure_separately(specified_modules, final_modules)
            # Print main_modules and tests_modules.
            if verbose >= 1:
                print('Main module list:')
                for module in main_modules:
                    print('  %s' % module.name)
                print('Tests-related module list:')
                for module in tests_modules:
                    print('  %s' % module.name)
            # Determine whether a $testsbase/libtests.a is needed.
            libtests = False
            for module in tests_modules:
                files = module.getFiles()
                for file in files:
                    if file.startswith('lib/'):
                        libtests = True
                        break
            self.emitter.config.setLibtests(libtests)

        if single_configure:
            # Add the dummy module to the main module list if needed.
            main_modules = moduletable.add_dummy(main_modules)
            if libtests:  # if we need to use libtests.a
                # Add the dummy module to the tests-related module list if needed.
                tests_modules = moduletable.add_dummy(tests_modules)
        else:  # if not single_configure
            modules = moduletable.add_dummy(modules)

        # Show banner notice of every module.
        if single_configure:
            if verbose >= -1:
                for module in main_modules:
                    notice = module.getNotice().strip('\n')
                    if notice:
                        print('Notice from module %s:' % module.name)
                        pattern = re.compile(r'^(.*)$', re.M)
                        notice = pattern.sub(r'  \1', notice)
                        print(notice)
        else:  # if not single_configure
            if verbose >= -1:
                for module in modules:
                    notice = module.getNotice().strip('\n')
                    if notice:
                        print('Notice from module %s:' % module.name)
                        pattern = re.compile(r'^(.*)$', re.M)
                        notice = pattern.sub(r'  \1', notice)
                        print(notice)

        # Determine final file list.
        if single_configure:
            main_filelist, tests_filelist = \
                moduletable.filelist_separately(main_modules, tests_modules)
        else:  # if not single_configure
            main_modules = modules
            tests_modules = [ module
                              for module in modules
                              if module.repeatModuleInTests() ]
            main_filelist, tests_filelist = \
                moduletable.filelist_separately(main_modules, tests_modules)

        filelist = sorted(set(main_filelist + tests_filelist))

        # Print list of files.
        if verbose >= 0:
            print('File list:')
            for file in filelist:
                if file.startswith('tests=lib/'):
                    rest = file[10:]
                    print('  lib/%s -> tests/%s' % (rest, rest))
                else:
                    print('  %s' % file)

        # Add files for which the copy in gnulib is newer than the one that
        # "automake --add-missing --copy" would provide.
        filelist = sorted(set(filelist + ['build-aux/config.guess', 'build-aux/config.sub']))

        # new_table is a table with two columns: (rewritten-file-name original-file-name),
        # representing the files after this gnulib-tool invocation.
        new_table = { (rewrite_file_name(file_name, self.config, True), file_name)
                      for file_name in filelist }

        # Setup the file table.
        filetable = GLFileTable(filelist)
        filetable.new_files = sorted(new_table, key=lambda pair: pair[0])

        # Create directories.
        directories = sorted({ joinpath(self.testdir, os.path.dirname(pair[0]))
                               for pair in filetable.new_files })
        for directory in directories:
            if not os.path.isdir(directory):
                os.makedirs(directory)

        # Copy files or make symbolic links or hard links.
        for (dest, src) in filetable.new_files:
            destpath = joinpath(self.testdir, dest)
            if src.startswith('tests=lib/'):
                src = substart('tests=lib/', 'lib/', src)
            lookedup, flag = self.filesystem.lookup(src)
            if os.path.isfile(destpath):
                os.remove(destpath)
            if flag:
                copyfile(lookedup, destpath)
                ensure_writable(destpath)
            else:  # if not flag
                if self.filesystem.shouldLink(src, lookedup) == CopyAction.Symlink:
                    link_relative(lookedup, destpath)
                elif self.filesystem.shouldLink(src, lookedup) == CopyAction.Hardlink:
                    hardlink(lookedup, destpath)
                else:
                    copyfile(lookedup, destpath)
                    ensure_writable(destpath)

        # Create $sourcebase/Makefile.am.
        for_test = True
        directory = joinpath(self.testdir, sourcebase)
        if not os.path.isdir(directory):
            os.mkdir(directory)
        destfile = joinpath(directory, 'Makefile.am')
        if single_configure:
            emit = self.emitter.lib_Makefile_am(destfile, main_modules,
                                                moduletable, self.makefiletable, '', for_test)
        else:  # if not single_configure
            emit = self.emitter.lib_Makefile_am(destfile, modules,
                                                moduletable, self.makefiletable, '', for_test)
        with open(destfile, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        # Create $m4base/Makefile.am.
        directory = joinpath(self.testdir, m4base)
        if not os.path.isdir(directory):
            os.mkdir(directory)
        destfile = joinpath(directory, 'Makefile.am')
        emit = '## Process this file with automake to produce Makefile.in.\n\n'
        emit += 'EXTRA_DIST =\n'
        for file in filetable.all_files:
            if file.startswith('m4/'):
                file = substart('m4/', '', file)
                emit += 'EXTRA_DIST += %s\n' % file
        with open(destfile, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        subdirs = [sourcebase, m4base]
        subdirs_with_configure_ac = []

        inctests = self.config.checkInclTestCategory(TESTS['tests'])
        if inctests:
            directory = joinpath(self.testdir, testsbase)
            if not os.path.isdir(directory):
                os.mkdir(directory)
            if single_configure:
                # Create $testsbase/Makefile.am.
                destfile = joinpath(directory, 'Makefile.am')
                witness_macro = '%stests_WITNESS' % macro_prefix
                emit = self.emitter.tests_Makefile_am(destfile, tests_modules, moduletable,
                                                      self.makefiletable, witness_macro, for_test)
                with open(destfile, mode='w', newline='\n', encoding='utf-8') as file:
                    file.write(emit)
            else:  # if not single_configure
                # Create $testsbase/Makefile.am.
                destfile = joinpath(directory, 'Makefile.am')
                libtests = False
                self.config.setLibtests(False)
                emit = self.emitter.tests_Makefile_am(destfile, modules, moduletable,
                                                      self.makefiletable, '', for_test)
                with open(destfile, mode='w', newline='\n', encoding='utf-8') as file:
                    file.write(emit)
                # Viewed from the $testsbase subdirectory, $auxdir is different.
                emit = ''
                saved_auxdir = auxdir
                auxdir = os.path.normpath(joinpath(relinverse(testsbase), auxdir))
                self.config.setAuxDir(auxdir)
                # Create $testsbase/configure.ac.
                emit += '# Process this file with autoconf '
                emit += 'to produce a configure script.\n'
                emit += 'AC_INIT([dummy], [0])\n'
                emit += 'AC_CONFIG_AUX_DIR([%s])\n' % auxdir
                emit += 'AM_INIT_AUTOMAKE\n\n'
                emit += 'AC_CONFIG_HEADERS([config.h])\n\n'
                emit += 'AC_PROG_CC\n'
                emit += 'AC_PROG_INSTALL\n'
                emit += 'AC_PROG_MAKE_SET\n'
                emit += self.emitter.preEarlyMacros(False, '', modules)
                snippets = []
                for module in modules:
                    if module.name in ['gnumakefile', 'maintainer-makefile']:
                        # These are meant to be used only in the top-level directory.
                        pass
                    # if module.name not in ['gnumakefile', 'maintainer-makefile']
                    else:
                        snippet = module.getAutoconfEarlySnippet()
                        lines = [ line
                                  for line in snippet.split('\n')
                                  if line.strip() ]
                        snippet = lines_to_multiline(lines)
                        pattern = re.compile(r'AC_REQUIRE\(\[([^()]*)]\)', re.M)
                        snippet = pattern.sub(r'\1', snippet)
                        snippet = snippet.strip()
                        snippets.append(snippet)
                snippets = [ snippet
                             for snippet in snippets
                             if snippet.strip()]
                emit += lines_to_multiline(snippets)
                if libtool:
                    emit += 'LT_INIT([win32-dll])\n'
                    emit += 'LT_LANG([C++])\n'
                    emit += 'AM_CONDITIONAL([GL_COND_LIBTOOL], [true])\n'
                    emit += 'gl_cond_libtool=true\n'
                else:  # if not libtool
                    emit += 'AM_CONDITIONAL([GL_COND_LIBTOOL], [false])\n'
                    emit += 'gl_cond_libtool=false\n'
                    emit += 'gl_libdeps=\n'
                    emit += 'gl_ltlibdeps=\n'
                # Wrap the set of autoconf snippets into an autoconf macro that is then
                # invoked. This is needed because autoconf does not support AC_REQUIRE
                # at the top level:
                #   error: AC_REQUIRE(gt_CSHARPCOMP): cannot be used outside of an
                #     AC_DEFUN'd macro
                # but we want the AC_REQUIRE to have its normal meaning (provide one
                # expansion of the required macro before the current point, and only
                # one expansion total).
                emit += 'AC_DEFUN([gl_INIT], [\n'
                replace_auxdir = True
                emit += "gl_m4_base='../%s'\n" % m4base
                emit += self.emitter.initmacro_start(macro_prefix, True)
                # We don't have explicit ordering constraints between the various
                # autoconf snippets. It's cleanest to put those of the library before
                # those of the tests.
                emit += self.emitter.shellvars_init(True, f'../{sourcebase}')
                emit += self.emitter.autoconfSnippets(modules, modules, moduletable,
                                                      lambda module: module.isNonTests(),
                                                      False, False, False, replace_auxdir)
                emit += self.emitter.shellvars_init(True, '.')
                emit += self.emitter.autoconfSnippets(modules, modules, moduletable,
                                                      lambda module: module.isTests(),
                                                      False, False, False, replace_auxdir)
                emit += self.emitter.initmacro_end(macro_prefix, True)
                # _LIBDEPS and _LTLIBDEPS variables are not needed if this library is
                # created using libtool, because libtool already handles the
                # dependencies.
                if not libtool:
                    libname_upper = libname.upper().replace('-', '_')
                    emit += '  %s_LIBDEPS="$gl_libdeps"\n' % libname_upper
                    emit += '  AC_SUBST([%s_LIBDEPS])\n' % libname_upper
                    emit += '  %s_LTLIBDEPS="$gl_ltlibdeps"\n' % libname_upper
                    emit += '  AC_SUBST([%s_LTLIBDEPS])\n' % libname_upper
                emit += '])\n'
                # FIXME use $sourcebase or $testsbase?
                emit += self.emitter.initmacro_done(macro_prefix, sourcebase)
                emit += '\ngl_INIT\n\n'
                # Usually $testsbase/config.h will be a superset of config.h. Verify
                # this by "merging" config.h into $testsbase/config.h; look out for gcc
                # warnings.
                emit += 'AH_TOP([#include \"../config.h\"])\n\n'
                emit += 'AC_CONFIG_FILES([Makefile])\n'
                emit += 'AC_OUTPUT\n'
                path = joinpath(self.testdir, testsbase, 'configure.ac')
                with open(path, mode='w', newline='\n', encoding='utf-8') as file:
                    file.write(emit)

                # Restore changed variables.
                self.config.setAuxDir(saved_auxdir)
                auxdir = self.config['auxdir']
                subdirs_with_configure_ac.append(testsbase)

            subdirs.append(testsbase)

        # Create Makefile.am.
        emit = '## Process this file with automake to produce Makefile.in.\n\n'
        emit += 'AUTOMAKE_OPTIONS = 1.14 foreign\n\n'
        emit += 'SUBDIRS = %s\n\n' % ' '.join(subdirs)
        emit += 'ACLOCAL_AMFLAGS = -I %s\n' % m4base
        path = joinpath(self.testdir, 'Makefile.am')
        with open(path, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        # Create configure.ac
        emit = '# Process this file with autoconf '
        emit += 'to produce a configure script.\n'
        emit += 'AC_INIT([dummy], [0])\n'
        if auxdir != '.':
            emit += 'AC_CONFIG_AUX_DIR([%s])\n' % auxdir
        emit += 'AM_INIT_AUTOMAKE\n\n'
        emit += 'AC_CONFIG_HEADERS([config.h])\n\n'
        emit += 'AC_PROG_CC\n'
        emit += 'AC_PROG_INSTALL\n'
        emit += 'AC_PROG_MAKE_SET\n\n'
        emit += '# For autobuild.\n'
        emit += 'AC_CANONICAL_BUILD\n'
        emit += 'AC_CANONICAL_HOST\n\n'
        emit += 'm4_pattern_forbid([^gl_[A-Z]])dnl the gnulib macro namespace\n'
        emit += 'm4_pattern_allow([^gl_ES$])dnl a valid locale name\n'
        emit += 'm4_pattern_allow([^gl_LIBOBJS$])dnl a variable\n'
        emit += 'm4_pattern_allow([^gl_LTLIBOBJS$])dnl a variable\n'
        emit += self.emitter.preEarlyMacros(False, '', modules)
        snippets = []
        for module in final_modules:
            if single_configure:
                solution = True
            else:  # if not single_configure
                solution = module.isNonTests()
            if solution:
                snippet = module.getAutoconfEarlySnippet()
                lines = [ line
                          for line in snippet.split('\n')
                          if line.strip() ]
                snippet = lines_to_multiline(lines)
                pattern = re.compile(r'AC_REQUIRE\(\[([^()]*)]\)', re.M)
                snippet = pattern.sub(r'\1', snippet)
                snippet = snippet.strip()
                snippets.append(snippet)
        snippets = [ snippet
                     for snippet in snippets
                     if snippet.strip() ]
        emit += lines_to_multiline(snippets)
        if libtool:
            emit += 'LT_INIT([win32-dll])\n'
            emit += 'LT_LANG([C++])\n'
            emit += 'AM_CONDITIONAL([GL_COND_LIBTOOL], [true])\n'
            emit += 'gl_cond_libtool=true\n'
        else:  # if not libtool
            emit += 'AM_CONDITIONAL([GL_COND_LIBTOOL], [false])\n'
            emit += 'gl_cond_libtool=false\n'
            emit += 'gl_libdeps=\n'
            emit += 'gl_ltlibdeps=\n'
        # Wrap the set of autoconf snippets into an autoconf macro that is then
        # invoked. This is needed because autoconf does not support AC_REQUIRE
        # at the top level:
        #   error: AC_REQUIRE(gt_CSHARPCOMP): cannot be used outside of an
        #     AC_DEFUN'd macro
        # but we want the AC_REQUIRE to have its normal meaning (provide one
        # expansion of the required macro before the current point, and only one
        # expansion total).
        emit += 'AC_DEFUN([gl_INIT], [\n'
        if auxdir != 'build-aux':
            replace_auxdir = True
        else:  # auxdir == 'build-aux'
            replace_auxdir = False
        emit += 'gl_m4_base=\'%s\'\n' % m4base
        emit += self.emitter.initmacro_start(macro_prefix, False)
        emit += self.emitter.shellvars_init(False, sourcebase)
        if single_configure:
            emit += self.emitter.autoconfSnippets(main_modules, main_modules, moduletable,
                                                  lambda module: True,
                                                  True, False, False, replace_auxdir)
        else:  # if not single_configure
            emit += self.emitter.autoconfSnippets(modules, modules, moduletable,
                                                  lambda module: module.isNonTests(),
                                                  True, False, False, replace_auxdir)
        emit += self.emitter.initmacro_end(macro_prefix, False)
        if single_configure:
            emit += '  gltests_libdeps=\n'
            emit += '  gltests_ltlibdeps=\n'
            emit += self.emitter.initmacro_start('%stests' % macro_prefix, True)
            emit += self.emitter.shellvars_init(True, testsbase)
            # Define a tests witness macro.
            emit += '  %stests_WITNESS=IN_GNULIB_TESTS\n' % macro_prefix
            emit += '  AC_SUBST([%stests_WITNESS])\n' % macro_prefix
            emit += '  gl_module_indicator_condition=$%stests_WITNESS\n' % macro_prefix
            emit += '  m4_pushdef([gl_MODULE_INDICATOR_CONDITION], '
            emit += '[$gl_module_indicator_condition])\n'
            snippets = self.emitter.autoconfSnippets(tests_modules, main_modules + tests_modules,
                                                     moduletable, lambda module: True,
                                                     True, False, False, replace_auxdir)
            emit += snippets
            emit += '  m4_popdef([gl_MODULE_INDICATOR_CONDITION])\n'
            emit += self.emitter.initmacro_end('%stests' % macro_prefix, True)
        # _LIBDEPS and _LTLIBDEPS variables are not needed if this library is
        # created using libtool, because libtool already handles the dependencies.
        if not libtool:
            libname_upper = libname.upper().replace('-', '_')
            emit += '  %s_LIBDEPS="$gl_libdeps"\n' % libname_upper
            emit += '  AC_SUBST([%s_LIBDEPS])\n' % libname_upper
            emit += '  %s_LTLIBDEPS="$gl_ltlibdeps"\n' % libname_upper
            emit += '  AC_SUBST([%s_LTLIBDEPS])\n' % libname_upper
        if single_configure and libtests:
            emit += '  LIBTESTS_LIBDEPS="$gltests_libdeps"\n'
            emit += '  AC_SUBST([LIBTESTS_LIBDEPS])\n'
        emit += '])\n'
        emit += self.emitter.initmacro_done(macro_prefix, sourcebase)
        if single_configure:
            emit += self.emitter.initmacro_done('%stests' % macro_prefix, testsbase)
        emit += '\ngl_INIT\n\n'
        if subdirs_with_configure_ac:
            emit += 'AC_CONFIG_SUBDIRS([%s])\n' % ' '.join(subdirs_with_configure_ac)
        makefiles = ['Makefile']
        for directory in subdirs:
            # For subdirs that have a configure.ac by their own, it's the subdir's
            # configure.ac which creates the subdir's Makefile.am, not this one.
            if not directory in subdirs_with_configure_ac:
                makefiles.append(joinpath(directory, 'Makefile'))
        emit += 'AC_CONFIG_FILES([%s])\n' % ' '.join(makefiles)
        emit += 'AC_OUTPUT\n'
        path = joinpath(self.testdir, 'configure.ac')
        with open(path, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        # Create autogenerated files.
        # Do not use "${AUTORECONF} --force --install", because it may invoke
        # autopoint, which brings in older versions of some of our .m4 files.
        force_output()
        os.chdir(self.testdir)
        # gettext
        if os.path.isfile(joinpath(m4base, 'gettext.m4')):
            args = [UTILS['autopoint'], '--force']
            execute(args, verbose)
            for src in os.listdir(m4base):
                src = joinpath(m4base, src)
                if src.endswith('.m4~'):
                    dest = src[:-1]
                    if os.path.isfile(dest):
                        os.remove(dest)
                    movefile(src, dest)
        # libtoolize
        if libtool:
            args = [UTILS['libtoolize'], '--copy']
            execute(args, verbose)
        # aclocal
        args = [UTILS['aclocal'], '-I', m4base]
        execute(args, verbose)
        if not os.path.isdir('build-aux'):
            print('executing mkdir build-aux')
            os.mkdir('build-aux')
        # autoconf
        args = [UTILS['autoconf']]
        execute(args, verbose)
        # autoheader
        args = [UTILS['autoheader']]
        execute(args, verbose)
        # Explicit 'touch config.h.in': see <https://savannah.gnu.org/support/index.php?109406>.
        print('executing touch config.h.in')
        Path('config.h.in').touch()
        # automake
        args = [UTILS['automake'], '--add-missing', '--copy']
        execute(args, verbose)
        rmtree('autom4te.cache')
        os.chdir(DIRS['cwd'])
        if inctests and not single_configure:
            # Do not use "${AUTORECONF} --force --install", because it may invoke
            # autopoint, which brings in older versions of some of our .m4 files.
            os.chdir(joinpath(self.testdir, testsbase))
            # gettext
            if os.path.isfile(joinpath(m4base, 'gettext.m4')):
                args = [UTILS['autopoint'], '--force']
                execute(args, verbose)
                for src in os.listdir(m4base):
                    src = joinpath(m4base, src)
                    if src.endswith('.m4~'):
                        dest = src[:-1]
                        if os.path.isfile(dest):
                            os.remove(dest)
                        movefile(src, dest)
            # aclocal
            args = [UTILS['aclocal'], '-I', joinpath('..', m4base)]
            execute(args, verbose)
            if not os.path.isdir(joinpath('../build-aux')):
                print('executing mkdir ../build-aux')
                os.mkdir('../build-aux')
            # autoconf
            args = [UTILS['autoconf']]
            execute(args, verbose)
            # autoheader
            args = [UTILS['autoheader']]
            execute(args, verbose)
            # Explicit 'touch config.h.in': see <https://savannah.gnu.org/support/index.php?109406>.
            print('executing touch config.h.in')
            Path('config.h.in').touch()
            # automake
            args = [UTILS['automake'], '--add-missing', '--copy']
            execute(args, verbose)
            rmtree('autom4te.cache')
            os.chdir(DIRS['cwd'])

        # Need to run configure and make once, to create built files that are to be
        # distributed (such as parse-datetime.c).
        path = joinpath(self.testdir, sourcebase, 'Makefile.am')
        with open(path, mode='r', newline='\n', encoding='utf-8') as file:
            snippet = file.read()
        snippet = combine_lines(snippet)

        # Extract the value of "CLEANFILES += ..." and "MOSTLYCLEANFILES += ...".
        regex_find = []
        pattern = re.compile(r'^CLEANFILES[\t ]*\+=(.*)$', re.M)
        regex_find += pattern.findall(snippet)
        pattern = re.compile(r'^MOSTLYCLEANFILES[\t ]*\+=(.*)$', re.M)
        regex_find += pattern.findall(snippet)
        regex_find = [ line.strip()
                       for line in regex_find
                       if line.strip() ]
        cleaned_files = []
        for part in regex_find:
            cleaned_files += \
                [ line.strip()
                  for line in part.split(' ')
                  if line.strip() ]

        # Extract the value of "BUILT_SOURCES += ...". Remove variable references
        # such $(FOO_H) because they don't refer to distributed files.
        regex_find = []
        pattern = re.compile(r'^BUILT_SOURCES[\t ]*\+=(.*)$', re.M)
        regex_find += pattern.findall(snippet)
        regex_find = [ line.strip()
                       for line in regex_find
                       if line.strip()]
        built_sources = []
        for part in regex_find:
            built_sources += \
                [ line.strip()
                  for line in part.split(' ')
                  if line.strip()]
        built_sources = [ line
                          for line in built_sources
                          if not bool(re.compile(r'[$]\([A-Za-z0-9_]*\)$').findall(line)) ]
        distributed_built_sources = [ file
                                      for file in built_sources
                                      if file not in cleaned_files ]

        tests_distributed_built_sources = []
        if inctests:
            # Likewise for built files in the $testsbase directory.
            path = joinpath(self.testdir, testsbase, 'Makefile.am')
            with open(path, mode='r', newline='\n', encoding='utf-8') as file:
                snippet = file.read()
            snippet = combine_lines(snippet)

            # Extract the value of "CLEANFILES += ..." and "MOSTLYCLEANFILES += ...".
            regex_find = []
            pattern = re.compile(r'^CLEANFILES[\t ]*\+=(.*)$', re.M)
            regex_find += pattern.findall(snippet)
            pattern = re.compile(r'^MOSTLYCLEANFILES[\t ]*\+=(.*)$', re.M)
            regex_find += pattern.findall(snippet)
            regex_find = [ line.strip()
                           for line in regex_find
                           if line.strip() ]
            tests_cleaned_files = []
            for part in regex_find:
                tests_cleaned_files += \
                    [ line.strip()
                      for line in part.split(' ')
                      if line.strip() ]

            # Extract the value of "BUILT_SOURCES += ...". Remove variable references
            # such $(FOO_H) because they don't refer to distributed files.
            regex_find = []
            pattern = re.compile(r'^BUILT_SOURCES[\t ]*\+=(.*)$', re.M)
            regex_find += pattern.findall(snippet)
            regex_find = [ line.strip()
                           for line in regex_find
                           if line.strip() ]
            tests_built_sources = []
            for part in regex_find:
                tests_built_sources += \
                    [ line.strip()
                      for line in part.split(' ')
                      if line.strip() ]
            tests_built_sources = [ line
                                    for line in tests_built_sources
                                    if not bool(re.compile(r'[$]\([A-Za-z0-9_]*\)$').findall(line)) ]
            tests_distributed_built_sources = [ file
                                                for file in tests_built_sources
                                                if file not in tests_cleaned_files]

        os.chdir(self.testdir)
        if distributed_built_sources or tests_distributed_built_sources:
            force_output()
            sp.call('./configure')
            if distributed_built_sources:
                os.chdir(sourcebase)
                with open('Makefile', mode='a', newline='\n', encoding='utf-8') as file:
                    file.write('built_sources: $(BUILT_SOURCES)\n')
                args = [UTILS['make'],
                        'AUTOCONF=%s' % UTILS['autoconf'],
                        'AUTOHEADER=%s' % UTILS['autoheader'],
                        'ACLOCAL=%s' % UTILS['aclocal'],
                        'AUTOMAKE=%s' % UTILS['automake'],
                        'AUTORECONF=%s' % UTILS['autoreconf'],
                        'built_sources']
                sp.call(args)
                os.chdir('..')
            if tests_distributed_built_sources:
                os.chdir(testsbase)
                with open('Makefile', mode='a', newline='\n', encoding='utf-8') as file:
                    file.write('built_sources: $(BUILT_SOURCES)\n')
                args = [UTILS['make'],
                        'AUTOCONF=%s' % UTILS['autoconf'],
                        'AUTOHEADER=%s' % UTILS['autoheader'],
                        'ACLOCAL=%s' % UTILS['aclocal'],
                        'AUTOMAKE=%s' % UTILS['automake'],
                        'AUTORECONF=%s' % UTILS['autoreconf'],
                        'built_sources']
                sp.call(args)
                os.chdir('..')
            args = [UTILS['make'],
                    'AUTOCONF=%s' % UTILS['autoconf'],
                    'AUTOHEADER=%s' % UTILS['autoheader'],
                    'ACLOCAL=%s' % UTILS['aclocal'],
                    'AUTOMAKE=%s' % UTILS['automake'],
                    'AUTORECONF=%s' % UTILS['autoreconf'],
                    'AUTOPOINT=%s' % UTILS['autopoint'],
                    'LIBTOOLIZE=%s' % UTILS['libtoolize'],
                    'distclean']
            sp.call(args)
        if os.path.isfile(joinpath('build-aux', 'test-driver')):
            _patch_test_driver()
        os.chdir(DIRS['cwd'])


#===============================================================================
# Define GLMegaTestDir class
#===============================================================================
class GLMegaTestDir:
    '''GLMegaTestDir class is used to create a mega scratch package with the
    given modules one by one and all together.'''

    config: GLConfig
    megatestdir: str
    modulesystem: GLModuleSystem

    def __init__(self, config: GLConfig, megatestdir: str) -> None:
        '''Create new GLTestDir instance.'''
        if type(config) is not GLConfig:
            raise TypeError('config must be a GLConfig, not %s'
                            % type(config).__name__)
        if type(megatestdir) is not str:
            raise TypeError('megatestdir must be a string, not %s'
                            % type(megatestdir).__name__)
        self.config = config
        self.megatestdir = os.path.normpath(megatestdir)
        # Don't overwrite the directory.
        if os.path.exists(self.megatestdir):
            raise GLError(22, self.megatestdir)
        # Try to create directory.
        try:
            os.mkdir(self.megatestdir)
        except Exception as exc:
            raise GLError(19, self.megatestdir) from exc
        self.modulesystem = GLModuleSystem(self.config)

    def execute(self) -> None:
        '''Create a mega scratch package with the given modules one by one
        and all together.'''
        auxdir = self.config['auxdir']
        verbose = self.config['verbosity']

        megasubdirs = []
        modules = [ self.modulesystem.find(m)
                    for m in self.config['modules'] ]
        if not modules:
            modules = self.modulesystem.list()
            modules = [ self.modulesystem.find(m)
                        for m in modules ]
        # Preserve ordering from the command-line, but remove duplicates.
        # This allows control over the SUBDIRS variable in the top-level Makefile.am.
        module_set = set(modules)
        modules = [ module
                    for module in modules
                    if module in module_set ]

        # First, all modules one by one.
        for module in modules:
            self.config.setModules([module.name])
            GLTestDir(self.config, joinpath(self.megatestdir, module.name)).execute()
            megasubdirs.append(module.name)

        # Then, all modules all together.
        # Except config-h, which breaks all modules which use HAVE_CONFIG_H.
        modules = [ module
                    for module in modules
                    if module.name != 'config-h' ]
        self.config.setModules([ module.name
                                 for module in modules ])
        GLTestDir(self.config, joinpath(self.megatestdir, 'ALL')).execute()
        megasubdirs.append('ALL')

        # Create autobuild.
        emit = ''
        repdict = dict()
        repdict['Jan'] = repdict['January'] = '01'
        repdict['Feb'] = repdict['February'] = '02'
        repdict['Mar'] = repdict['March'] = '03'
        repdict['Apr'] = repdict['April'] = '04'
        repdict['May'] = repdict['May'] = '05'
        repdict['Jun'] = repdict['June'] = '06'
        repdict['Jul'] = repdict['July'] = '07'
        repdict['Aug'] = repdict['August'] = '08'
        repdict['Sep'] = repdict['September'] = '09'
        repdict['Oct'] = repdict['October'] = '10'
        repdict['Nov'] = repdict['November'] = '11'
        repdict['Dec'] = repdict['December'] = '12'
        vc_witness = joinpath(DIRS['root'], '.git', 'refs', 'heads', 'master')
        if not os.path.isfile(vc_witness):
            vc_witness = joinpath(DIRS['root'], 'ChangeLog')
        mdate_sh = joinpath(DIRS['root'], 'build-aux', 'mdate-sh')
        args = ['sh', mdate_sh, vc_witness]
        cvsdate = sp.check_output(args).decode('UTF-8').strip()
        for key in repdict:
            if len(key) > 3:
                cvsdate = cvsdate.replace(key, repdict[key])
        for key in repdict:
            cvsdate = cvsdate.replace(key, repdict[key])
        cvsdate = ''.join([ date
                            for date in cvsdate.split(' ')
                            if date.strip() ])
        cvsdate = '%s%s%s' % (cvsdate[4:], cvsdate[2:4], cvsdate[:2])
        emit += '#!/bin/sh\n'
        emit += 'CVSDATE=%s\n' % cvsdate
        emit += ': ${MAKE=make}\n'
        emit += 'test -d logs || mkdir logs\n'
        emit += 'for module in %s; do\n' % ' '.join(megasubdirs)
        emit += '  echo "Working on module $module..."\n'
        emit += '  safemodule=`echo $module | sed -e \'s|/|-|g\'`\n'
        emit += '  (echo "To: gnulib@autobuild.josefsson.org"\n'
        emit += '   echo\n'
        emit += '   set -x\n'
        emit += '   : autobuild project... $module\n'
        emit += '   : autobuild revision... cvs-$CVSDATE-000000\n'
        emit += '   : autobuild timestamp... `date "+%Y%m%d-%H%M%S"`\n'
        emit += '   : autobuild hostname... `hostname`\n'
        emit += '   cd $module && ./configure $CONFIGURE_OPTIONS && $MAKE'
        emit += ' && $MAKE check && $MAKE distclean\n'
        emit += '   echo rc=$?\n'
        emit += '  ) 2>&1 | { if test -n "$AUTOBUILD_SUBST"; then '
        emit += 'sed -e "$AUTOBUILD_SUBST"; else cat; fi; } > logs/$safemodule\n'
        emit += 'done\n'
        path = joinpath(self.megatestdir, 'do-autobuild')
        with open(path, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        # Create Makefile.am.
        emit = '## Process this file with automake to produce Makefile.in.\n\n'
        emit += 'AUTOMAKE_OPTIONS = 1.14 foreign\n\n'
        emit += 'SUBDIRS = %s\n\n' % ' '.join(megasubdirs)
        emit += 'EXTRA_DIST = do-autobuild\n'
        path = joinpath(self.megatestdir, 'Makefile.am')
        with open(path, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        emit = '# Process this file with autoconf '
        emit += 'to produce a configure script.\n'
        emit += 'AC_INIT([dummy], [0])\n'
        if auxdir != '.':
            emit += 'AC_CONFIG_AUX_DIR([%s])\n' % auxdir
        emit += 'AM_INIT_AUTOMAKE\n\n'
        emit += 'AC_PROG_MAKE_SET\n\n'
        emit += 'AC_CONFIG_SUBDIRS([%s])\n' % ' '.join(megasubdirs)
        emit += 'AC_CONFIG_FILES([Makefile])\n'
        emit += 'AC_OUTPUT\n'
        path = joinpath(self.megatestdir, 'configure.ac')
        with open(path, mode='w', newline='\n', encoding='utf-8') as file:
            file.write(emit)

        # Create autogenerated files.
        force_output()
        os.chdir(self.megatestdir)
        args = [UTILS['aclocal']]
        execute(args, verbose)
        try:  # Try to make a directory
            if not os.path.isdir('build-aux'):
                print('executing mkdir build-aux')
                os.mkdir('build-aux')
        except Exception:
            pass
        args = [UTILS['autoconf']]
        execute(args, verbose)
        args = [UTILS['automake'], '--add-missing', '--copy']
        execute(args, verbose)
        rmtree('autom4te.cache')
        if os.path.isfile(joinpath('build-aux', 'test-driver')):
            _patch_test_driver()
        os.chdir(DIRS['cwd'])
