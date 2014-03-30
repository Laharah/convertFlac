____author__ = 'Lunchbox'

from mutagen import File as mutagenFile
from mutagen.flac import FLAC
from mutagen.easyid3 import EasyID3
from mutagen.easyid3 import EasyID3KeyError
import subprocess
import os


class convertFlac:
    def __init__(self, targets, newFolder=False, recursive=False):

        #targets must be a flac file, a list of flac files, or a single directory (files must have '.flac' extention)
        self.targetIsDir = False
        if type(targets) != list:
            targets = [targets]
        if self.confirmTargetsValid(targets):
            self.targets = targets

        #TODO:find flac files in directory, pay attention to recursive
        self.flacFiles = targets

        self.newFiles = {}
        self.newFolder = newFolder
        if newFolder == True and self.targetIsDir:
            self.newFolder = self.targets[0] + ' [V0]'

        self.doConvert()
        self.copyTags()

    def confirmTargetsValid(self, targets):
        if len(targets) == 1:
            if os.path.isdir(targets[0]):
                self.targetIsDir = True
                return True
        for target in targets:
            if not os.path.isfile(target) or not target.endswith('.flac'):
                raise NameError(target + 'is not a valid conversion target')

    def doConvert(self):
        if self.newFolder == False:
            newPath = ''
        else:
            newPath = self.newFolder

        print self.flacFiles

        for target in self.flacFiles:
            newFile = os.path.join(newPath, target.replace('.flac', '.mp3'))
            self.newFiles[target] = newFile
            print 'working on: ', target
            psFlac = subprocess.Popen(('flac', '-d', '-c', target), stdout=subprocess.PIPE)
            psLame = subprocess.call(
                ('lame', '-V', '0', '-', newFile), stdin=psFlac.stdout)
            print 'Flac Done.'
            psFlac.wait()
            print 'Lame Done.'
        return

    def copyTags(self):
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
                if key.startswith('replay'):
                    print 'skipping key:', key
                else:
                    try:
                        mp3Meta[key] = flacMeta[key]
                    except EasyID3KeyError:
                        print 'could not add key: ', key
                        print 'skipping'
            mp3Meta.save()


def main():
    #TODO: Make dynamic and accept arguments
    os.chdir('F:\\Waste\\what.cd\\Chinese Dance Machine')
    newFolder = 'temp [V0]'
    try:
        os.mkdir(newFolder)
    except:
        pass
    flacFiles = [x for x in os.listdir(os.getcwd()) if x.endswith('.flac')]
    print flacFiles

    temp = convertFlac(flacFiles, newFolder=newFolder)
    return


if __name__ == '__main__':
    main()
