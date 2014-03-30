____author__ = 'Lunchbox'

from mutagen import File as mutagenFile
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError
import shutil
import subprocess
import os


class convertFlac:
    def __init__(self, targets, newFolder='', recursive=False, clone=False):

        self.recursive = recursive
        self.clone = clone
        self.flacFiles = []
        self.targetIsDir = False
        if type(targets) != list:
            targets = [targets]

        #targets must be a flac file, a list of flac files, or a single directory (files must have '.flac' extention)
        if not self.confirmTargetsValid(targets):
            raise IOError("One or more of your arguments is not a valid flac file")

        self.newFiles = {}

        self.newFolder = newFolder

        #if cloning is requested without a destination, program defaults to cloning the folder side by side with the
        #affix ' [MP3]'
        if newFolder == '' and self.clone == True:
            self.newFolder = os.path.join(os.path.dirname(targets[0]), targets[0] + ' [MP3]')

        if self.targetIsDir and self.clone == True:
            self.cloneFolder(targets[0], self.newFolder)

        if self.newFolder == '' and self.targetIsDir:
            self.newFolder = self.rootDir

        self.doConvert()
        self.copyTags()


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

    #Finds all flacs to convert, optionaly recursivly using os.path.walk
    def findFlacs(self, dir):
        if self.recursive == True:
            allFiles = []
            for root, dirs, files in os.walk(dir):
                for file in files:
                    allFiles.append(os.path.join(root, file))

            flacs = [f for f in allFiles if f.endswith('.flac')]
            return flacs
        else:
            return [os.path.join(dir, f) for f in os.listdir(dir) if f.endswith('.flac')]

    def doConvert(self):
        newPath = self.newFolder
        if not os.path.exists(newPath):
            os.mkdir(newPath)
        for target in self.flacFiles:
            #Forms file destination arguments
            newFile = os.path.join(newPath, os.path.basename(target.replace('.flac', '.mp3')))

            if self.recursive:
            #special handeling for destination arguments to maintain folder structure during recursive runs
                if not os.path.exists(os.path.join(newPath, os.path.dirname(os.path.relpath(target, self.rootDir)))):
                    os.mkdir(os.path.join(newPath, os.path.dirname(os.path.relpath(target, self.rootDir))))
                newFile = os.path.join(newPath, os.path.relpath(target.replace('.flac', '.mp3'), self.rootDir))

            self.newFiles[target] = newFile
            print 'working on: ', target, ' : ', newFile
            #uses flac to decode and pipe it's output into Lame
            #TODO: allow for custom lame arguments
            psFlac = subprocess.Popen(('flac', '-d', '-c', target), stdout=subprocess.PIPE)
            psLame = subprocess.call(
                ('lame', '-V', '0', '-', newFile), stdin=psFlac.stdout)
            print 'Flac Done.'
            psFlac.wait()
            print 'Lame Done.'
        return

    def copyTags(self):
    #uses mutagen to duplicate valid tags from flac to MP3
        for flacFile in self.flacFiles:
            flacMeta = FLAC(flacFile)
            try:
                mp3Meta = EasyID3(self.newFiles[flacFile])
                print mp3Meta
            except:
                print 'adding id3 header to', self.newFiles[flacFile]
                mp3Meta = mutagenFile(self.newFiles[flacFile], easy=True)
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
                        print 'skipping'
            mp3Meta.save()

    def cloneFolder(self, source, dest):
        if self.recursive:
            if os.path.exists(dest):
                raise IOError('destination folder already exists, cannot copy recursivly')
            shutil.copytree(source, dest, ignore=shutil.ignore_patterns('*.flac'))
            return
        else:
            if not os.path.exists(dest):
                os.mkdir(dest)
                #list interpretation, simply compiles a list of all valid files in source directory
            files = [os.path.join(source, f) for f in os.listdir(source) if os.path.isfile(os.path.join(source, f))]
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
    #TODO: Make dynamic and accept arguments
    args = 'F:\\Waste\\what.cd\\Chinese Dance Machine'
    destFolder = 'F:\\temp [V0]'

    flacFiles = [x for x in os.listdir(os.getcwd()) if x.endswith('.flac')]
    print flacFiles

    temp = convertFlac(args, clone=True, recursive=True)
    return


if __name__ == '__main__':
    main()
