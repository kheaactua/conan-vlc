#!/usr/bin/env python
# -*- coding: future_fstrings -*-
# -*- coding: utf-8 -*-

import os, shutil, glob, re
from conans import ConanFile, tools, AutoToolsBuildEnvironment
from zipfile import BadZipfile

def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z

class VlcConan(ConanFile):
    name            = 'vlc'
    version         = '3.0.3'
    license         = ''
    url             = ''
    description     = 'VLC Video player'
    options         = {'shared': [True, False]}
    default_options = 'shared=False'
    generators      = 'cmake'
    exports         = 'md5sums/*'

    requires        = (
        'helpers/[>=0.3]@ntc/stable',
        'qt/[>=5.9.0]@ntc/stable',
        'ffmpeg/3.4@ntc/stable',
    )

    build_requires  = (
        'pkg-config/0.29.2@ntc/stable'
    )

    settings        = {
        'os':       ['Linux', 'Windows'],
        'compiler': ['gcc', 'Visual Studio'],
        'arch':     ['x86_64'],
    }

    # system reqs:
    # wayland-protocols protobuf-compiler

    def source(self):
        if 'Linux' == self.settings.os:
            archive = 'vlc-%s.tar.xz'%self.version
            url     = f'http://download.videolan.org/pub/videolan/vlc/{self.version}/{archive}'
        else:
            archive = 'vlc-%s-win64.zip'%self.version
            url     = f'http://download.videolan.org/pub/videolan/vlc/{self.version}/win64/{archive}'

        self.output.info(f'Downloading file {url}')
        tools.download(
            url=url,
            filename=archive
        )

        from platform_helpers import check_hash
        # For some reason, the md5 files put a * in front of the file names
        check_hash(
            file_path=r'%s'%archive,
            hash_file=os.path.join('md5sums', f'{archive}.md5'),
            fnc=tools.check_md5
        )

        self.output.info('Extracting %s'%archive)
        try:
            tools.unzip(archive)
        except BadZipfile:
            if 'Linux' == self.settings.os:
                # no idea why I have to do this
                self.run(f'tar -xavf {archive}')
        shutil.move(f'vlc-{self.version}', self.name)

    def build(self):
        if 'Linux' == self.settings.os:
            self._build_linux()

    def _build_linux(self):
        with tools.chdir(self.name):
            autotools = AutoToolsBuildEnvironment(self, win_bash=('Windows' == self.settings.os))

            env_vars = {}
            args = []

            # env_vars['PKG

            if 'gcc' == self.settings.compiler and 'Windows' == self.settings.os:
                args.append('--prefix=%s'%tools.unix_path(self.package_folder))
            else:
                args.append('--prefix=%s'%self.package_folder)

            if str(self.settings.os) in ['Linux', 'Macos']:
                autotools.fpic = True
                # if self.settings.arch == 'x86':
                #     env_vars['ABI'] = '32'
                #     autotools.cxx_flags.append('-m32')

            # Debug
            s = '\nPkg-Config Vars in Environment:\n'
            full_env = merge_two_dicts(os.environ, env_vars)
            for k,v in full_env.items():
                if re.match('PKG_CONFIG.*', k):
                    s += ' - %s=%s\n'%(k, v)
            self.output.info(s)
            self.output.info('Configure arguments: %s'%' '.join(args))

            # Set up our build environment
            with tools.environment_append(env_vars):
                self.run('./bootstrap')
                autotools.configure(args=args)
                autotools.make()
                autotools.make(args=['install'])

    def _build_windows(self):
        pass

    def _build_mingw(self):
        pass

    def package(self):

        if 'gcc' == self.settings.compiler:
            with tools.chdir(self.name):
                autotools = AutoToolsBuildEnvironment(self, win_bash=('Windows' == self.settings.os))
                autotools.make(args=['install'])

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)

# vim: ts=4 sw=4 expandtab ffs=unix ft=python foldmethod=marker :
