from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))
exec(open(path.join(here, 'raybot', 'version.py')).read())

hoh_path = 'git+git://github.com/Zverik/humanized_opening_hours.git#egg=osm-humanized-opening-hours'
setup(
    name='raybot',
    version=__version__,  # noqa
    author='Ilya Zverev',
    author_email='ilya@zverev.info',
    packages=['raybot'],
    package_data={'raybot': ['raybot.config', 'raybot.util', 'raybot.model']},
    python_requires='~=3.8',
    install_requires=[
        'aiogram',
        'aiosqlite',
        'pyyaml',
        'pillow',
        'astral==1.10.1',
        'lark-parser',
        'babel',
        'osm-humanized-opening-hours @ ' + hoh_path,
    ],
    url='https://github.com/Zverik/bot_na_rayone',
    license='ISC License',
    description='Telegram bot for searching for addresses and amenities in your city block',
    long_description=open(path.join(here, 'README.md')).read(),
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Framework :: AsyncIO',
        'Intended Audience :: Information Technology',
        'Intended Audience :: Customer Service',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Natural Language :: Russian',
        'Operating System :: OS Independent',
        'Topic :: Communications :: Chat',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
    ],
    entry_points={
        'console_scripts': ['raybot = raybot.__main__:main']
    },
)
