import sys
from setuptools import setup

requirements = ['mutagen >= 1.0', 'docopt >= 0.6']

if sys.version_info.major == 2:
    requirements.append('futures >= 2.2')

setup(
    name='convertFlac',
    version='1.05.01',
    packages=[''],
    url='https://github.com/Laharah/convertFlac',
    license='GNU',
    author='Laharah',
    author_email='',
    description=
    'script to use flac and lame to convert flac files and transfer tags to mp3',
    long_description=
    'A script that uses subprocess to call flac and lame to convert flac files to mp3 '
    'and transfer tags asynchronously',
    py_modules=['convertFlac'],
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'convertFlac = convertFlac:main'
        ]
    })
