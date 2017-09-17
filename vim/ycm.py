import os
import ycm_core

FLAGS = [
    '-Wall',
    '-Wextra',
    '-Werror',
    '-Wno-long-long',
    '-Wno-variadic-macros',
    '-fexceptions',
    '-ferror-limit=10000',
    '-DNDEBUG',
    '-std=c++1z',
    '-xc++',
    '-I/usr/lib/',
    '-I/usr/include/'
]

database = None

SOURCE_EXTENSIONS = ['.cxx', '.cpp', '.cc', '.c', '.mm', '.m']
HEADER_EXTENSIONS = ['.hxx', '.hpp', '.hh', '.h']


def IsHeaderFile(filename):
  extension = os.path.splitext(filename)[1]
  return extension in HEADER_EXTENSIONS


def DirectoryOfThisScript():
  return os.path.dirname(os.path.abspath(__file__))


def MakeRelativePathsInFlagsAbsolute(FLAGS, working_directory):
  if not working_directory:
    return list(FLAGS)
  new_flags = []
  make_next_absolute = False
  path_flags = ['-isystem', '-I', '-iquote', '--sysroot=']
  for flag in FLAGS:
    new_flag = flag

    if make_next_absolute:
      make_next_absolute = False
      if not flag.startswith('/'):
        new_flag = os.path.join(working_directory, flag)

    for path_flag in path_flags:
      if flag == path_flag:
        make_next_absolute = True
        break

      if flag.startswith(path_flag):
        path = flag[len(path_flag):]
        new_flag = path_flag + os.path.join(working_directory, path)
        break

    if new_flag:
      new_flags.append(new_flag)
  return new_flags


def GetCompilationInfoForFile(filename):
  # The compilation_commands.json file generated by CMake does not have entries
  # for header files. So we do our best by asking the db for FLAGS for a
  # corresponding source file, if any. If one exists, the FLAGS for that file
  # should be good enough.
  if IsHeaderFile(filename):
    basename = os.path.splitext(filename)[0]
    for extension in SOURCE_EXTENSIONS:
      replacement_file = basename + extension
      if os.path.exists(replacement_file):
        compilation_info = database.GetCompilationInfoForFile(
            replacement_file)
        if compilation_info.compiler_flags_:
          return compilation_info
    return None
  return database.GetCompilationInfoForFile(filename)


def FlagsForFile(filename, **kwargs):
  if database:
    # Bear in mind that compilation_info.compiler_flags_ does NOT return a
    # python list, but a "list-like" StringVec object
    compilation_info = GetCompilationInfoForFile(filename)
    if not compilation_info:
      return None

    final_flags = MakeRelativePathsInFlagsAbsolute(
        compilation_info.compiler_flags_,
        compilation_info.compiler_working_dir_)

  else:
    relative_to = DirectoryOfThisScript()
    final_flags = MakeRelativePathsInFlagsAbsolute(FLAGS, relative_to)

  return {
      'flags': final_flags,
      'do_cache': True
  }
