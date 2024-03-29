#!/usr/bin/python
"""
Usage: convertFlac [options] [-o PATH] <SOURCES> ...

accepts flac files or directories, creating VO mp3 files from each flac.

Options:
  -h, --help             show this help message and exit

  --version              Display version info

  -o, --output=PATH      defines an output directory. If none is specified, mp3s will be
                         placed next to the original flacs

  --num-cores=N          defines the number of processing cores to use for concurrent
                         conversions. Defaults to using half of available cores. Also
                         accepts 'MAX' as an argument to use all availabe cores.

  --nice=N               Set process nice level for encoding/decoding [default: 10].

  Directory Options:
    These options are used for determining behavior when being passed a
    directory

    -c, --clone         makes a clone of given directories, copying non-flac
                        files and placing converted files in their correct
                        place. if no output path is defined, 'SOURCEPATH [MP3]'
                        will be used. Output directory must not already
                        exist. DOES NOT IMPLY '-r'.

    -r, --recursive     recurses through a directory looking for flac files to
                        convert. Often used in conjunction with '-c' to maintain
                        directory structure for converted files

    --folder-suffix SF  A suffix to append to cloned folders. ex " [V0]"

    --replace PAT       A sed type regex substitution string to be run on each
                        directory and file name (remember to escape regex control chars.)

    --delete-flacs      delete input flacs after transcode. Cleans up empty directories
                        as well. (use without "-c" or "-o" to simulate an inplace
                        transcode).

    -f, --overwrite     forces overwriting if files already exist.

  Custom Lame Settings:
    Options for customizing the settings lame will use to convert the flac
    files. Defaults to V0.

    -V n, --VBR n            Quick VBR setting (0-9), defaults to highest quality: 0

    -b n, --bitrate n        Quick constant bitrate setting in kbps (up to 320).

    --lame-args="[options]"  Options that will be passed through to the lame
                             encoder. Type "lame -h" to see lame options. Overrides
                             other lame settings. Be sure to encapsulate options
                             with quotes ex: "-p -V2 -a"
"""
from __future__ import unicode_literals, print_function

__author__ = 'Laharah'

from concurrent.futures import ThreadPoolExecutor
import contextlib
import functools
import os
from multiprocessing import cpu_count
import re
import sys
import shutil
import subprocess
import tempfile
import threading
import warnings
import queue

from mutagen import MutagenError
from mutagen import File as mutagenFile
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError


def convert(targets,
            output=None,
            recursive=False,
            clone=False,
            folder_suffix=None,
            vbr_level=0,
            cbr=None,
            lame_args=None,
            overwrite=False,
            delete_flacs=False,
            num_cores=None,
            nice_val=10,
            replacement=None,
            verbose=False):
    """
    Convert given target files/folders into mp3 using flac and lame
    :param targets: list of files or folders containing .flac files
    :param output: folder to place outputs. If none is given, mp3s will be placeed
    next to original flac files. (cloned folders without output will be placed next to
    original folder with folder_suffix appended)
    :param recursive: search folders recursively for .flac files.
    :param clone: "clone" input folders, copying any additional files to output
    :param folder_suffix: suffix to add to cloned folders
    :param vbr_level: vbr level to pass to lame. Defaults to highest (0).
    :param cbr: constant bitrate to use for mp3 encoding (overrides vbr_level)
    :param lame_args: custom lame args to pass for encoding. (Overrides all other
    lame args).
    :param overwrite: Overwrite existing files.
    :param delete_flacs: delete original flac files after conversion.
    :return: None
    """

    output = output.decode('utf8') if isinstance(output, bytes) else output

    if iter(targets) is iter(targets):
        targets = (t.decode('utf8') if isinstance(t, bytes) else t for t in targets)
    else:
        targets = {t.decode('utf8') if isinstance(t, bytes) else t for t in targets}

    if replacement:
        if not replacement.startswith('s'):
            raise ValueError('replacement string must start with "s[SEPERATOR_CHAR]"')
        sep = replacement[1]
        if replacement.count(sep) != 3:
            raise ValueError("replacement string must be in sed format. eg:'s/pat/repl/"
                             " (no flags)'")
        replacement = tuple(replacement.split(sep)[1:3])

    folders_to_clone, target_files = generate_outputs(targets,
                                                      output,
                                                      clone=clone,
                                                      recursive=recursive,
                                                      folder_suffix=folder_suffix,
                                                      sub=replacement)

    print('Cloning folders...')
    for source, dest in folders_to_clone:
        clone_folder(source, dest, recursive=recursive)

    # lame_args need to be in tuple format for subprocess call
    lame_args = tuple(lame_args.split()) if lame_args else None
    print_queue = queue.Queue()

    def print_manager():
        while True:
            job = print_queue.get()
            print(job)
            print_queue.task_done()

    t = threading.Thread(target=print_manager)
    t.daemon=True
    t.start()
    del t

    def conversion_callback(future):
        old, new = future.result()
        if not new:
            warnings.warn('error converting {}'.format(old))
            return
        if verbose:
            try:
                print_queue.put('Conversion done for {}\nCopying tags...'.format(old))
            except UnicodeEncodeError:
                print_queue.put('Conversion Done for {}\nCopying tags...'.format(
                    old.encode('mbcs', 'replace')))

        copy_tags(old, new, verbose=True, print_queue=print_queue)
        if verbose:
            print_queue.put('Done!\n')

        if delete_flacs:
            os.remove(old)
            try:
                os.rmdir(os.path.dirname(source))
            except OSError:
                pass

    num_cores = 0 if not num_cores else int(num_cores)

    if not num_cores:
        num_cores = cpu_count() // 2

    kwargs = {
        'vbr': vbr_level,
        'cbr': cbr,
        'lame_args': lame_args,
        'overwrite': overwrite,
        'nice_val': nice_val,
    }

    with ThreadPoolExecutor(max_workers=num_cores) as pool:
        print('Beginning conversion for {} files.'.format(len(target_files)))
        for source, dest in target_files:
            if not target_is_valid(source):
                warnings.warn(
                    ('The target "{}" could not be found or is not a ".flac" file. '
                     'Skipping...').format(source))
            pool.submit(_do_convert, source, dest,
                        **kwargs).add_done_callback(conversion_callback)
    print_queue.join()


def generate_outputs(targets,
                     output,
                     clone=False,
                     recursive=False,
                     folder_suffix=None,
                     sub=None):
    """
    Takes in a list of targets and generates tuples containing the apropriate
    source/destination for each folder to be cloned and flac file to be converted.
    :param targets: list of files and folders to search for flac files
    :param output: the output folder to aim for. Special behavior if there is only a
    single folder to target, uses output the name for the new folder
    :param clone: whether or not to clone the extra files in the source directories
    and maintain file structure
    :param recursive: Whether or not to search directories recursivly
    :return:tuple in format ([(folder_source, folder_dest)...], [(flac_source, dest)])
    """
    is_iter = True if iter(targets) is iter(targets) else False
    folders = []
    files = []
    for target in targets:
        if os.path.isdir(target):
            if clone:
                folders.append(os.path.abspath(target))
            else:
                files += find_flacs(target, recursive=recursive)
        else:
            files.append(os.path.abspath(target))

    output = os.path.abspath(output) if output else None

    if output:
        files = [(f, get_output_path(output, f, sub=sub)) for f in files]
    else:
        files = [(f, get_output_path(None, f, sub=sub)) for f in files]

    folder_suffix = folder_suffix if folder_suffix else ''
    folder_targets = []
    for folder in folders:
        if output:
            if not is_iter and len(targets) > 1:
                output_folder = os.path.join(output, os.path.basename(folder))
            else:
                output_folder = output
            if sub:
                pat, repl = sub
                output_folder = re.sub(pat, repl, output_folder)
            if folder_suffix:
                output_folder += folder_suffix
        else:
            folder_name_modified = False
            if sub:
                pat, repl = sub
                output_folder = re.sub(pat, repl, folder)
                if output_folder != folder:
                    folder_name_modified = True
            else:
                output_folder = folder

            if folder_suffix:
                output_folder = '{}{}'.format(output_folder, folder_suffix)
                folder_name_modified = True

            if not folder_name_modified:  # output folder must not be same as folder
                output_folder = '{} [MP3]'.format(folder)

        folder_targets.append((folder, output_folder))
        additional_files = find_flacs(folder, recursive=recursive)
        preserve_from = None if not recursive else folder
        files += [(f, get_output_path(output_folder, f, preserve_from, sub))
                  for f in additional_files]

    return folder_targets, files


def get_output_path(output, file_path, preserve_from=None, sub=None):
    """helper function to convert a target filepath into the correct output"""
    output = output if output else os.path.dirname(file_path)
    f_name, _, _ = file_path.rpartition('.flac')
    if preserve_from is not None and preserve_from not in file_path:
        raise ValueError('"{}" is not in the file path "{}". Cannot preserve recursive '
                         'folder structure'.format(preserve_from, file_path))
    new_base = preserve_from if preserve_from else os.path.dirname(file_path)
    f_name = f_name.replace(new_base, output)
    if sub:
        pat, repl = sub
        f_name = os.path.join(os.path.dirname(f_name),
                              re.sub(pat, repl, os.path.basename(f_name)))
    return '{}.mp3'.format(f_name)


def target_is_valid(target):
    """checks if a file exists and has '.flac' extension"""
    if not os.path.exists(target):
        return False
    if os.path.isfile(target):
        return target.endswith('.flac')
    else:
        return False


def find_flacs(folder, recursive):
    if recursive:
        all_files = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                all_files.append(os.path.join(root, f))

        flacs = [os.path.abspath(f) for f in all_files if f.endswith('.flac')]
        return flacs
    else:
        return [
            os.path.abspath(os.path.join(folder, f)) for f in os.listdir(folder)
            if f.endswith('.flac')
        ]


@contextlib.contextmanager
def non_uni_files(source, dest):
    """context manager to copy files into non-unicode namespace, copy the new dest to
    the correct place and cleanup afterward"""
    tempdir = tempfile.mkdtemp()
    temp_source = os.path.join(tempdir, '{}.flac'.format(hash(source)))
    temp_dest = os.path.join(tempdir, '{}.mp3'.format(hash(dest)))
    shutil.copy2(source, temp_source)
    try:
        yield (temp_source, temp_dest)
    except:
        raise
    else:
        if os.path.exists(temp_dest):
            shutil.copy2(temp_dest, dest)
    finally:
        shutil.rmtree(tempdir)


def win_popen_workaround(conversion):
    """
    decorator for special handling of un-decodeable utf-8 strings for py2 on windows
    machines.

    This decorator workaround is necessary because of a bug in the subprocess module
    in python 2 on windows machines.
    """

    if sys.version_info.major == 3 or sys.platform != 'win32':
        return conversion

    @functools.wraps(conversion)
    def win_convert(input, output, **kwargs):
        try:
            if any(isinstance(arg, unicode) for arg in (input, output)):
                [x.decode('mbcs') for x in (input, output)]
        except UnicodeEncodeError:
            with non_uni_files(input, output) as (source, dest):
                old, new = conversion(source, dest, **kwargs)
            return input, output if new else None
        else:
            return conversion(input, output, **kwargs)

    return win_convert


@win_popen_workaround
def _do_convert(source,
                dest,
                vbr=0,
                cbr=None,
                lame_args=None,
                overwrite=False,
                nice_val=10):
    """Convert flacs to mp3 V0 using lame and Copies tags from flac to new MP3."""
    new_path = os.path.dirname(dest)
    if not os.path.exists(new_path):
        os.makedirs(new_path)

    if os.path.exists(dest) and not overwrite:
        warnings.warn('"{}" already exists! skipping...'.format(dest))
        return source, None

    # print('\nConverting: ', source, ' : ', dest)

    # uses flac to decode and pipe it's output into lame with the correct
    # arguments.
    if sys.platform == 'win32':  # preexe/nice is not supported on windows
        set_nice = None
    else:
        def set_nice():
            os.nice(nice_val)

    flac_args = ('flac', '-d', '-c', '-s')
    try:
        ps_flac = subprocess.Popen(flac_args + (source, ),
                                   preexec_fn=set_nice,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
    except OSError:
        raise OSError("FLAC executible is not installed or not in path!")


# lame arguments hierarchy goes lameargs > CBR > VBR.

    if lame_args is None:
        if cbr is None:
            args = ['lame', '-', dest, '-V', str(vbr), '--silent']
            ps_lame = subprocess.call(args,
                                      preexec_fn=set_nice,
                                      stdin=ps_flac.stdout,
                                      stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        else:
            ps_lame = subprocess.call(('lame', '-', dest) + ('-b', str(cbr), '--silent'),
                                      preexec_fn=set_nice,
                                      stdin=ps_flac.stdout,
                                      stderr=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL)
    else:
        ps_lame = subprocess.call(('lame', '-', dest, '--silent') + lame_args,
                                  preexec_fn=set_nice,
                                  stdin=ps_flac.stdout,
                                  stderr=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL)
    ps_flac.wait()
    return source, dest


def copy_tags(source, target, verbose=False, print_queue=None):
    """Uses mutagen to duplicate valid tags from flac to MP3"""
    if print_queue is None:
        print_queue = queue.Queue()
    try:
        flac_meta = FLAC(source)
    except MutagenError:
        warnings.warn('Bad metadata on "{}", skipping metadata copy...'.format(source))
        return

    try:
        mp3_meta = EasyID3(target)
    except MutagenError:
        if verbose:
            print_queue.put('adding id3 header to mp3...')
        mp3_meta = mutagenFile(target, easy=True)
        mp3_meta.add_tags()

    for key in flac_meta.keys():
        # leveling tags causes errors (too quiet on random tracks) so they are omitted
        if key.startswith('replay'):
            if verbose:
                print_queue.put('skipping leveling key:', key)
        else:
            try:
                mp3_meta[key] = flac_meta[key]
            except EasyID3KeyError:
                if verbose:
                    print_queue.put('could not add key: ', key)
    mp3_meta.save()


def clone_folder(source, dest, recursive=False):
    """Handles The copying of additional non-flac files (ex: cover.jpg etc) from
    input to output folder."""
    if recursive:
        if os.path.exists(dest):
            raise IOError('destination folder "{}" already exists, cannot copy '
                          'recursivly'.format(dest))

        shutil.copytree(source, dest, ignore=shutil.ignore_patterns('*.flac'))
        return
    else:
        if not os.path.exists(dest):
            os.mkdir(dest)
        files = [
            os.path.join(source, f) for f in os.listdir(source)
            if os.path.isfile(os.path.join(source, f))
        ]
        to_copy = []
        for f in files:
            if f.endswith('.flac'):
                pass
            else:
                to_copy.append(f)

        for f in to_copy:
            shutil.copy(f, dest)
        return to_copy


def main():
    import docopt

    arguments = docopt.docopt(__doc__, version='1.05.03')

    try:
        ps = subprocess.call(('flac', '--version'),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except OSError:
        print('Could not find flac.exe! please ensure it is installed and in your path.')
        exit(1)
    try:
        ps = subprocess.call(('lame', '--version'),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    except OSError:
        print('Could not find lame.exe! please ensure it is installed and in your path.')
        exit(1)

    if arguments['--num-cores'] is not None:
        if arguments['--num-cores'].lower() == 'max':
            arguments['--num-cores'] = cpu_count()

    if arguments['--VBR'] is None:
        arguments['--VBR'] = 0

    targets = arguments['<SOURCES>']
    if len(targets) == 1 and targets[0] == '-':
        t = sys.stdin.read().strip().split("\n")
        arguments['<SOURCES>'] = t

    convert(arguments['<SOURCES>'],
            output=arguments['--output'],
            clone=arguments['--clone'],
            recursive=arguments['--recursive'],
            folder_suffix=arguments['--folder-suffix'],
            vbr_level=arguments['--VBR'],
            cbr=arguments['--bitrate'],
            lame_args=arguments['--lame-args'],
            overwrite=arguments['--overwrite'],
            delete_flacs=arguments['--delete-flacs'],
            num_cores=arguments['--num-cores'],
            nice_val=int(arguments['--nice']),
            replacement=arguments['--replace'],
            verbose=True)

    return


if __name__ == '__main__':
    main()
