#convertFlac
###Covert flac files inelegantly to mp3 using flac and lame

####Features:
*   automatically copies flac metadata to id3 tags
*   accepts list of files or directories
*   semi-intelegent output directory parsing
*   optional recursion
*   folder cloning (for copying over .cue, cover.jpg, etc and maintaing folder structure)
*   quick encoding options

####Installation:
*   Install [flac](https://xiph.org/flac/download.html)
*   Install lame (binaries [here](http://lame.sourceforge.net/links.php#Binaries))
*   Make sure both executables are in your path
*   type `python setup.py install`

*(For OS X I recomend using [Homebrew](http://brew.sh) to install lame and flac)*

Thats it!


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
    
      Custom Lame Settings:
        Options for customizing the settings lame will use to convert the flac
        files. Defaults to V0.
    
        -V n, --VBR n           Quick VBR setting (0-9), defaults to highest quality: 0
    
        -b n, --bitrate n       Quick bitrate setting in kbps (up to 320).
    
        --lameargs="[options]"  Options that will be passed through to the lame
                                encoder. Type "lame -h" to see lame options. Overides
                                other lame settings. Be sure to encapsulate options
                                with quotes ex:"-p -V2 -a"

