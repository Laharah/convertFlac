#!/usr/bin/python

"""
Usage: convertFlac [options] [-o PATH] SOURCE ...

accepts flec files or directorys, creating VO mp3 files from each flac.

Options:
  -h, --help             show this help message and exit

  -o PATH, --output=PATH defines an output directory or file

  Directory Options:
    These options are used for determining behavior when being passed a
    directory

    -c, --clone         makes a clone of given directory, copying non-flac
                        files and placing converted files in their correct
                        place. if no output path is defined, 'SOURCEPATH
                        [MP3]' will be used. Output directory must not already
                        exsist. DOES NOT IMPLY '-r'.

    -r, --recursive     recurses through a directory looking for flac files to
                        convert, often used in conjuntion with '-c'. Maintains
                        directory structure for converted files

    -f, --overwrite     forces overwriting if files already exsist. Affects cloning as
                        well.

  Custom Lame Settings:
    Options for customizing the settings lame will use to convert the flac
    files. Defaults to V0.

    -V n, --VBR n           Quick VBR setting (0-9), defaults to highest quality: 0

    -b n, --bitrate n       Quick bitrate setting in kbps (up to 320).

    --lameargs="[options]"  Options that will be passed through to the lame
                            encoder. Type "lame -h" to see lame options. Overides
                            other lame settings. Be sure to encapsulate options
                            with quotes ex:"-p -V2 -a"
"""
____author__ = 'Laharah'

import shutil
import subprocess
import os
import warnings

import docopt
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
            lame_args=None):
    # lameargs need to be in tupple format for subprocess call
    lame_args = tuple(lame_args.split()) if lame_args else None

    folders_to_clone, target_files = generate_outputs(
        targets, output, clone=clone, recursive=recursive)

    for source, dest in folders_to_clone:
        clone_folder(source, dest)

    for source, dest in target_files:
        if target_is_valid(source):
            doConvert(source, dest, vbr=vbrlevel, cbr=cbr, lame_args=lame_args)
            copy_tags(source, dest)
        else:
            warnings.warn('The target "{}" could not be found. '
                          'Skipping...'.format(source))


def generate_outputs(targets, output, clone=False, recursive=False):
    '''
    Takes in a list of targets and generates tuples containing the apropriate
    source/destination for each folder to be cloned and flac file to be converted.
    :param targets: list of files and folders to search for flac files
    :param output: the output folder to aim for. Special behavior if there is only a
    single folder to target, uses output the name for the new folder
    :param clone: whether or not to clone the extra files in the source directories
    and maintain file structure
    :param recursive: Whether or not to search directories recursivly
    :return:tuple in format ([(folder_source, folder_dest)...], [(flac_source, dest)])
    '''

    is_iter = True if iter(targets) is iter(targets) else False
    folders = []
    files = []
    for target in targets:
        if os.path.isdir(target):
            if clone:
                folders.append(os.path.abspath(target))
            else:
                files += findFlacs(target, recursive=recursive)
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
        additional_files = findFlacs(folder, recursive=recursive)
        preserve_from = None if not recursive else folder
        files += [(f, get_output_path(output_folder, f, preserve_from)) for f in additional_files]

    return folder_targets, files


def get_output_path(output, file_path, preserve_from=None):
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


# Finds all flacs to convert, optionaly recursivly using os.path.walk
def findFlacs(dir, recursive):
    if recursive == True:
        allFiles = []
        for root, dirs, files in os.walk(dir):
            for file in files:
                allFiles.append(os.path.join(root, file))

        flacs = [os.path.abspath(f) for f in allFiles if f.endswith('.flac')]
        return flacs
    else:
        return [os.path.abspath(os.path.join(dir, f)) for f in os.listdir(unicode(dir))
                if f.endswith('.flac')]


def doConvert(self):
    """Convert flacs to mp3 V0 using lame and Copies tags from flac to new MP3."""
    newPath = self.newFolder
    if not os.path.exists(newPath):
        os.mkdir(newPath)

    for target in self.flacFiles:
        # Forms file destination arguments.
        newFile = os.path.join(newPath, os.path.basename(target.replace('.flac',
                                                                        '.mp3')))

        if self.recursive:
            # special handeling for destination arguments to maintain folder
            # structure during recursive runs
            if not os.path.exists(os.path.join(
                    newPath, os.path.dirname(os.path.relpath(target, self.rootDir)))):
                os.mkdir(os.path.join(
                    newPath, os.path.dirname(os.path.relpath(target, self.rootDir))))
            newFile = os.path.join(newPath, os.path.relpath(
                target.replace('.flac', '.mp3'), self.rootDir))

        self.newFiles[target] = newFile
        print '\nConverting: ', target, ' : ', newFile

        # uses flac to decode and pipe it's output into lame with the correct
        # arguments.
        psFlac = subprocess.Popen(('flac', '-d', '-c', target),
                                  stdout=subprocess.PIPE)
        # lame arguments heirarchy goes lame arguments passthrough > CBR > VBR.
        if self.lameargs == None:
            if self.cbr == None:
                psLame = subprocess.call(
                    ('lame', '-', newFile) + ('-V', str(self.vbrlevel)),
                    stdin=psFlac.stdout)
            else:
                psLame = subprocess.call(
                    ('lame', '-', newFile) + ('-b', str(self.cbr)),
                    stdin=psFlac.stdout)
        else:
            psLame = subprocess.call(('lame', '-', newFile) + self.lameargs,
                                     stdin=psFlac.stdout)
        psFlac.wait()
    return


def copy_tags(self, target):
    """Uses mutagen to duplicate valid tags from flac to MP3"""
    flacMeta = FLAC(target)
    try:
        mp3Meta = EasyID3(self.newFiles[target])
        print mp3Meta
    except:
        print 'adding id3 header to', self.newFiles[target]
        mp3Meta = mutagenFile(self.newFiles[target], easy=True)
        mp3Meta.add_tags()

    for key in flacMeta.keys():
        # leveling tags cause errors on MP3 tags (too quiet on random tracks) so they are omited
        if key.startswith('replay'):
            print 'skipping key:', key
        else:
            try:
                mp3Meta[key] = flacMeta[key]
            except EasyID3KeyError:
                print 'could not add key: ', key
    mp3Meta.save()


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
        # list interpretation, simply compiles a list of all valid files in source directory.
        files = [os.path.join(source, f) for f in os.listdir(source)
                 if os.path.isfile(os.path.join(source, f))]
        toBeCopied = []
        for file in files:
            if file.endswith('.flac'):
                pass
            else:
                toBeCopied.append(file)

        for file in toBeCopied:
            shutil.copy(file, dest)
        return toBeCopied


def main():
    arguments = docopt.docopt(__doc__)

    # TODO: add support for multiple directories
    # TODO: add delete flacs option

    convertFlac(arguments['SOURCE'],
                newFolder=arguments['--output'],
                clone=arguments['--clone'],
                recursive=arguments['--recursive'],
                vbrlevel=arguments['--VBR'],
                cbr=arguments['--bitrate'],
                lameargs=arguments['--lameargs'])

    return


if __name__ == '__main__':
    main()
