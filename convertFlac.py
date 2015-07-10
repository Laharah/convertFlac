#!/usr/bin/python

____author__ = 'Lunchbox'

from mutagen import File as mutagenFile
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError
from optparse import OptionParser
from optparse import OptionGroup
import shutil
import subprocess
import os


class convertFlac:
    def __init__(self, targets,
                 newFolder=None,
                 recursive=False,
                 clone=False,
                 vbrlevel=0,
                 cbr=None,
                 lameargs=None):
        self.recursive = recursive
        self.clone = clone
        self.vbrlevel = vbrlevel
        self.cbr = cbr
        self.flacFiles = []
        self.targetIsDir = False
        if type(targets) != list:
            targets = [targets]
        # lameargs need to be in tupple format for subprocess call
        if lameargs is not None:
            self.lameargs = tuple(lameargs.split(' '))
        else:
            self.lameargs = None

        # targets must be a flac file, a list of flac files,
        # or a single directory (files must have '.flac' extention)
        if not self.confirmTargetsValid(targets):
            raise IOError("One or more of your arguments is not a valid flac file")

        self.newFiles = {}

        self.newFolder = newFolder
        if self.newFolder == None:
            self.newFolder = ''
            # if cloning is requested without a destination, program defaults to cloning
            # the folder side by side with the affix ' [MP3]'
        if self.newFolder == '' and self.clone == True:
            self.newFolder = os.path.join(os.path.dirname(targets[0]),
                                          targets[0] + ' [MP3]')

        if self.targetIsDir and self.clone == True:
            self.cloneFolder(targets[0], self.newFolder)

        if self.newFolder == '' and self.targetIsDir:
            self.newFolder = self.rootDir

        self.doConvert()
        # tags will be copied directly after conversion incase operation is aborted

    def confirmTargetsValid(self, targets):
        if len(targets) == 1:
            if os.path.isdir(targets[0]):
                self.targetIsDir = True
                self.rootDir = targets[0]
                self.flacFiles = self.findFlacs(targets[0])
                return True
        for target in targets:
            if not os.path.isfile(target) or not target.endswith('.flac'):
                return False
            self.flacFiles.append(target)
        return True

    # Finds all flacs to convert, optionaly recursivly using os.path.walk
    def findFlacs(self, dir):
        if self.recursive == True:
            allFiles = []
            for root, dirs, files in os.walk(dir):
                for file in files:
                    allFiles.append(os.path.join(root, file))

            flacs = [f for f in allFiles if f.endswith('.flac')]
            return flacs
        else:
            return [os.path.join(dir, f) for f in os.listdir(unicode(dir))
                    if f.endswith('.flac')]

    def doConvert(self):
        """Convert flacs to mp3 V0 using lame and Copies tags from flac to new MP3."""
        newPath = self.newFolder
        if not os.path.exists(newPath):
            os.mkdir(newPath)

        for target in self.flacFiles:
            #Forms file destination arguments.
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
            self.copyTags(target)
        return

    def copyTags(self, target):
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
            #leveling tags cause errors on MP3 tags (too quiet on random tracks) so they are omited
            if key.startswith('replay'):
                print 'skipping key:', key
            else:
                try:
                    mp3Meta[key] = flacMeta[key]
                except EasyID3KeyError:
                    print 'could not add key: ', key
        mp3Meta.save()

    def cloneFolder(self, source, dest):
        """Handles The copying of additional non-flac files (ex: cover.jpg etc) from
        input to output folder."""
        if self.recursive:
            if os.path.exists(dest):
                raise IOError('destination folder already exists, cannot copy recursivly')
            shutil.copytree(source, dest, ignore=shutil.ignore_patterns('*.flac'))
            return
        else:
            if not os.path.exists(dest):
                os.mkdir(dest)
            #list interpretation, simply compiles a list of all valid files in source directory.
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

    usage = 'usage: "%prog [options[--output=PATH]] SOURCE"'
    progDescription = 'accepts flec files or directorys, creating VO mp3 files from each flac'
    parser = OptionParser(usage, description=progDescription)
    parser.add_option('-o', '--output',
                      dest='output',
                      metavar='PATH',
                      action='store',
                      help="defines an output directory or file")

    group = OptionGroup(
        parser, 'Directory Options',
        'These options are used for determining behavior when being passed a directory ')
    group.add_option(
        '-c', '--clone',
        dest="clone",
        action='store_true',
        default=False,
        help=
        "makes a clone of given directory, copying non-flac files and placing converted "
        "files in their correct place. if no output path is defined, 'SOURCEPATH [MP3]' will be used."
        " Output directory must not already exsist. DOES NOT IMPLY '-r'.")
    group.add_option(
        '-r', '--recursive',
        dest='recursive',
        action='store_true',
        default=False,
        help=
        "recurses through a directory looking for flac files to convert, often used in conjuntion"
        " with '-c'. Maintains directory structure for converted files")
    parser.add_option_group(group)

    group = OptionGroup(
        parser, 'Custom Lame Settings',
        "Options for customizing the settings lame will use to convert the flac files. "
        "Defaults to V0.")
    group.add_option('-V',
                     dest='VBRLevel',
                     metavar='n',
                     action='store',
                     type='int',
                     help="Quick VBR setting (0-9), defaults to highest \"0\"")
    group.add_option('-b',
                     dest='CBR',
                     metavar="bitrate",
                     action='store',
                     type='int',
                     help="Quick bitrate setting in kbps (up to 320)")
    group.add_option(
        '--lameargs',
        dest='lameargs',
        metavar='\"[options]\"',
        action='store',
        help=
        "Options that will be passed through to the lame encoder. Type \"lame -h\" to see lame options. "
        "Overides other lame settings. Be sure to encapsulate options with quotes ex:\"-p -V2 -a\"")
    parser.add_option_group(group)

    (options, args) = parser.parse_args()
    if len(args) < 1:
        parser.error("You must specify a path where '.flac' files can be found")

    # TODO: add support for multiple directories
    # TODO: add delete flacs option

    convertFlac(args,
                newFolder=options.output,
                clone=options.clone,
                recursive=options.recursive,
                vbrlevel=options.VBRLevel,
                cbr=options.CBR,
                lameargs=options.lameargs)

    return


if __name__ == '__main__':
    main()
