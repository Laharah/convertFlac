#!/usr/bin/python
"""
Usage: convertFlac [options] [-o PATH] <SOURCES> ...

accepts flac files or directories, creating VO mp3 files from each flac.

Options:
  -h, --help             show this help message and exit

  -o, --output=PATH      defines an output directory. If none is specified, mp3s will be
                         placed next to the original flacs

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
____author__ = 'Laharah'

import shutil
import subprocess
import os
import warnings

import docopt
from mutagen import MutagenError
from mutagen import File as mutagenFile
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError


def convert(targets,
            output=None,
            recursive=False,
            clone=False,
            vbrlevel=0,
            cbr=None,
            lame_args=None,
            overwrite=False,
            delete_flacs=False):

    # lameargs need to be in tupple format for subprocess call
    lame_args = tuple(lame_args.split()) if lame_args else None

    folders_to_clone, target_files = generate_outputs(
        targets, output,
        clone=clone,
        recursive=recursive)

    for source, dest in folders_to_clone:
        clone_folder(source, dest, recursive=recursive)

    for source, dest in target_files:
        if target_is_valid(source):
            new = _do_convert(source, dest,
                              vbr=vbrlevel,
                              cbr=cbr,
                              lame_args=lame_args,
                              overwrite=overwrite)
            if new:
                copy_tags(source, new)
            if delete_flacs:
                os.remove(source)
                try:
                    os.rmdir(os.path.dirname(source))
                except OSError:
                    pass

        else:
            warnings.warn('The target "{}" could not be found. '
                          'Skipping...'.format(source))


def generate_outputs(targets, output, clone=False, recursive=False):
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
        files = [(f, get_output_path(output, f)) for f in files]
    else:
        files = [(f, get_output_path(None, f)) for f in files]

    folder_targets = []
    for folder in folders:
        if output:
            if not is_iter and len(targets) > 1:
                output_folder = os.path.join(output, os.path.basename(folder))
            else:
                output_folder = output
        else:
            output_folder = '{} [MP3]'.format(folder)
        folder_targets.append((folder, output_folder))
        additional_files = find_flacs(folder, recursive=recursive)
        preserve_from = None if not recursive else folder
        files += [(f, get_output_path(output_folder, f, preserve_from))
                  for f in additional_files]

    return folder_targets, files


def get_output_path(output, file_path, preserve_from=None):
    """helper function to convert a target filepath into the correct output"""
    output = output if output else os.path.dirname(file_path)
    f_name, _, _ = file_path.rpartition('.flac')
    if preserve_from is not None and preserve_from not in file_path:
        raise ValueError('"{}" is not in the file path "{}". Cannot preserve recursive '
                         'folder structure'.format(preserve_from, file_path))
    new_base = preserve_from if preserve_from else os.path.dirname(file_path)
    f_name = f_name.replace(new_base, output)
    return '{}.mp3'.format(f_name)


def target_is_valid(target):
    if not os.path.exists(target):
        return False
    if os.path.isfile(target):
        return target.endswith('.flac')


def find_flacs(folder, recursive):
    if recursive:
        all_files = []
        for root, dirs, files in os.walk(folder):
            for f in files:
                all_files.append(os.path.join(root, f))

        flacs = [os.path.abspath(f) for f in all_files if f.endswith('.flac')]
        return flacs
    else:
        return [os.path.abspath(os.path.join(folder, f))
                for f in os.listdir(unicode(folder)) if f.endswith('.flac')]


def _do_convert(source, dest, vbr=0, cbr=None, lame_args=None, overwrite=False):
    """Convert flacs to mp3 V0 using lame and Copies tags from flac to new MP3."""
    new_path = os.path.dirname(dest)
    if not os.path.exists(new_path):
        os.makedirs(new_path)

    if os.path.exists(dest) and not overwrite:
        warnings.warn('"{}" already exists! skipping...'.format(dest))
        return None

    print '\nConverting: ', source, ' : ', dest

    # uses flac to decode and pipe it's output into lame with the correct
    # arguments.
    flac_args = ('flac', '-d', '-c')
    try:
        ps_flac = subprocess.Popen(flac_args + (source, ), stdout=subprocess.PIPE)
    except OSError:
        raise OSError("FLAC executible is not installed or not in path!")
    # lame arguments heirarchy goes lame arguments passthrough > CBR > VBR.
    if lame_args is None:
        if cbr is None:
            ps_lame = subprocess.call(
                ('lame', '-', dest) + ('-V', str(vbr)),
                stdin=ps_flac.stdout)
        else:
            ps_lame = subprocess.call(
                ('lame', '-', dest) + ('-b', str(cbr)),
                stdin=ps_flac.stdout)
    else:
        ps_lame = subprocess.call(('lame', '-', dest) + lame_args, stdin=ps_flac.stdout)
    ps_flac.wait()
    return dest


def copy_tags(source, target):
    """Uses mutagen to duplicate valid tags from flac to MP3"""
    try:
        flac_meta = FLAC(source)
    except MutagenError:
        warnings.warn('Bad metadata on "{}", skipping metadata copy...'.format(source))
        return

    try:
        mp3_meta = EasyID3(target)
        print mp3_meta
    except MutagenError:
        print 'adding id3 header to', target
        mp3_meta = mutagenFile(target, easy=True)
        mp3_meta.add_tags()

    for key in flac_meta.keys():
        # leveling tags causes errors (too quiet on random tracks) so they are omitted
        if key.startswith('replay'):
            print 'skipping key:', key
        else:
            try:
                mp3_meta[key] = flac_meta[key]
            except EasyID3KeyError:
                print 'could not add key: ', key
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
        files = [os.path.join(source, f) for f in os.listdir(source)
                 if os.path.isfile(os.path.join(source, f))]
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
    arguments = docopt.docopt(__doc__)

    try:
        ps = subprocess.call(('flac', '--version'))
    except OSError:
        print 'Could not find flac.exe! please ensure it is installed and in your path.'
        exit(1)
    try:
        ps = subprocess.call(('lame', '--version'))
    except OSError:
        print 'Could not find lame.exe! please ensure it is installed and in your path.'
        exit(1)

    print arguments

    convert(arguments['<SOURCES>'],
            output=arguments['--output'],
            clone=arguments['--clone'],
            recursive=arguments['--recursive'],
            vbrlevel=arguments['--VBR'],
            cbr=arguments['--bitrate'],
            lame_args=arguments['--lame-args'],
            overwrite=arguments['--overwrite'],
            delete_flacs=arguments['--delete-flacs'])

    return


if __name__ == '__main__':
    main()
