____author__ = 'Lunchbox'

from mutagen.easyid3 import EasyID3
import os


def setTags(filePath):
    try:
        meta = EasyID3(filePath)
    except:
        import mutagen

        meta = mutagen.File(filePath, easy=True)
        meta.add_tags()

    meta['title'] = filePath.split(' - ')[1][:-4]
    meta['artist'] = 'F-777'
    meta['album'] = 'Chinese Dance Machine'
    meta['tracknumber'] = filePath[:2]

    print meta
    meta.save()


def main():
    os.chdir('F:\\Waste\\what.cd\\Chinese Dance Machine [V0]')
    files = [x for x in os.listdir(os.getcwd()) if x.endswith('.mp3')]
    print files
    for file in files:
        setTags(file)
    return


if __name__ == '__main__':
    main()