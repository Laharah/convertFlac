from setuptools import setup

setup(
    name='convertFlac',
    version='1.0',
    packages=[''],
    url='https://github.com/Laharah/convertFlac',
    license='GNU',
    author='Laharah',
    author_email='',
    description='uses flac and lame to convert flac files and transfer tags to mp3',
    long_description='A simple script and class that uses subprocess to call flac and lame to convert flac files to mp3 and transfer tags',
    install_requires=[
        'mutagen',
    ],
)
