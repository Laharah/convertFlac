#convertFlac
###Covert flac files intelligently to mp3 using FLAC and LAME
*python 2.7*

####Features:
*   automatically copies flac metadata to id3 tags
*   accepts list of files or directories
*   semi-intelligent output directory parsing
*   optional recursion
*   folder cloning (for copying over .cue, cover.jpg, etc and maintaing folder structure)
*   quick encoding options
*   options for inplace transcoding

####Installation:
*   Install [flac](https://xiph.org/flac/download.html)
*   Install lame (binaries [here](http://lame.sourceforge.net/links.php#Binaries))
*   Make sure both executables are in your path (eg: typing `flac --version` works)
*   type `python setup.py install` 
*   or if you have pip: type `pip install git+git://github.com/laharah/convertFlac`

*(For OS X I recommend using [Homebrew](http://brew.sh) to install LAME and FLAC)*

Thats it!


    Usage: convertFlac [options] [-o PATH] SOURCE ...
    
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
