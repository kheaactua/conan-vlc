#!/usr/bin/env python
# -*- coding: future_fstrings -*-
# -*- coding: utf-8 -*-

import os, shutil, glob, re
from conans import ConanFile, tools, AutoToolsBuildEnvironment
from conans.errors import ConanException
from zipfile import BadZipfile

def merge_two_dicts(x, y):
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z

class VlcConan(ConanFile):
    name            = 'vlc'
    version         = '3.0.4'
    license         = 'MIT'
    url             = 'https://github.com/kheaactua/conan-vlc'
    description     = 'VLC Video player'
    options         = {'shared': [True, False]}
    default_options = 'shared=False'
    generators      = 'cmake'
    exports         = 'md5sums/*', '*.patch'

    requires        = (
        'helpers/[>=0.3]@ntc/stable',
    )

    settings        = {
        'os':       ['Linux', 'Windows'],
        'compiler': {
            'gcc': {'version': ['4.9', '5.4', '6', '6.1', '6.2', '6.3', '6.4', '6', '6.1', '6.2', '6.3', '6.4']},
            'Visual Studio': None,
        },
        'arch':     ['x86_64'],
    }

    # system reqs:
    # wayland-protocols protobuf-compiler

    @property
    def just_downloading(self):
        return 'gcc' != self.settings.compiler and tools.os_info.is_windows

    def config_options(self):
        if self.just_downloading:
            self.options.remove('shared')

    def build_requirements(self):
        self.build_requires('pkg-config/0.29.2@ntc/stable')
        if tools.os_info.is_windows:
            self.build_requires('7z_installer/1.0@conan/stable')

        pack_names = []
        if tools.os_info.linux_distro == 'ubuntu' or tools.os_info.linux_distro == 'debian':
            pack_names = ['autopoint', 'libtool', 'automake']

        if pack_names:
            installer = tools.SystemPackageTool()
            try:
                installer.update() # Update the package database
                installer.install(' '.join(pack_names)) # Install the package
            except ConanException:
                self.output.warn('Could not run build requirements installer.  Requisite packages might be missing.')

    def system_requirements(self):
        pack_names = []
        if tools.os_info.linux_distro == 'ubuntu' or tools.os_info.linux_distro == 'debian':
            pack_names = ['flex', 'bison', 'gettext']

        if pack_names:
            installer = tools.SystemPackageTool()
            try:
                installer.update() # Update the package database
                installer.install(' '.join(pack_names)) # Install the package
            except ConanException:
                self.output.warn('Could not run system requirements installer.  Requisite packages might be missing.')

    def requirements(self):
        if not self.just_downloading:
            # If we're actually building VLC, we'll need some requirements
            self.requires('qt/[>=5.9.0]@ntc/stable')
            self.requires('ffmpeg/3.4@ntc/stable')

    def source(self):
        if tools.os_info.is_linux:
            archive = 'vlc-%s.tar.xz'%self.version
            url     = f'http://download.videolan.org/pub/videolan/vlc/{self.version}/{archive}'
        else:
            archive = 'vlc-%s-win64.7z'%self.version
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
            if tools.os_info.is_linux:
                # no idea why I have to do this
                self.run(f'tar -xavf {archive}')
            elif tools.os_info.is_windows:
                self.run(f'7z x {archive}')
            else:
                self.output.warn('Do not know how to extract %s'%archive)

        shutil.move(f'vlc-{self.version}', self.name)

        if tools.os_info.is_windows:
            # Apply a patch for the poll symbol
            b = os.path.join(self.name, 'include')
            f = os.path.join(b, 'vlc_threads.h')
            if os.path.exists(f): tools.patch(base_path=b, patch_file='poll.patch')

            b = os.path.join(self.name, 'sdk', 'include', 'vlc', 'plugins')
            f = os.path.join(b, 'vlc_threads.h')
            if os.path.exists(f): tools.patch(base_path=b, patch_file='poll.patch')

            # Now, patch for the undefined libvlc_media_read_cb symbol.  Even
            # though it appears that ssize_t is defined, this still fails.
            # Note:  If we were installing VLC for our own direct use, libvlcpp
            # would be the proper way to go
            tools.replace_in_file(
                file_name=os.path.join(self.name, 'sdk', 'include', 'vlc', 'libvlc_media.h'),
                search ='typedef ssize_t (*libvlc_media_read_cb)(void *opaque, unsigned char *buf',
                replace='typedef     int (*libvlc_media_read_cb)(void *opaque, unsigned char *buf',
            )

    def build(self):
        if self.just_downloading:
            self.output.warn('Skipping build on os=%s and compiler=%s'%(self.settings.os, self.settings.compiler))

        if tools.os_info.is_linux:
            self._build_linux()
        else:
            self.output.warn('Unsure how to proceed on %s'%self.settings.os)

    def _build_linux(self):
        with tools.chdir(self.name):
            autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_linux)

            env_vars = {}
            args = []

            if 'gcc' == self.settings.compiler and tools.os_info.is_windows:
                args.append('--prefix=%s'%tools.unix_path(self.package_folder))
            else:
                args.append('--prefix=%s'%self.package_folder)

            if tools.os_info.is_linux or tools.os_info.is_macos:
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
        if self.just_downloading:
            if tools.os_info.is_windows:
                self._package_windows()
            else:
                self.output.warn('Unsure how to proceed with os=%s and compiler=%s'%(self.settings.os, self.settings.compiler))
        else:
            if 'gcc' == self.settings.compiler:
                self._package_gcc()
            else:
                self.output.warn('Unsure how to proceed with os=%s and compiler=%s'%(self.settings.os, self.settings.compiler))

    def _package_gcc(self):
        with tools.chdir(self.name):
            autotools = AutoToolsBuildEnvironment(self, win_bash=tools.os_info.is_windows)
            autotools.make(args=['install'])

    def _package_windows(self):
        """ Copy the assets out of the VLC SDK """

        self.copy(pattern='*.dll', dst='bin', src=self.name)
        self.copy(pattern='*.lib', dst='lib', src=os.path.join(self.name, 'sdk', 'lib'))
        self.copy(pattern='*.pc',  dst='lib/pkgconfig', src=os.path.join(self.name, 'sdk', 'lib', 'pkgconfig'))
        self.copy(pattern='*',     dst='include', src=os.path.join(self.name, 'sdk', 'include'))

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)

        # Populate the pkg-config environment variables
        with tools.pythonpath(self):
            from platform_helpers import adjustPath, appendPkgConfigPath

            pkg_config_path = os.path.join(self.package_folder, 'lib', 'pkgconfig')
            appendPkgConfigPath(adjustPath(pkg_config_path), self.env_info)

            pc_files = glob.glob(adjustPath(os.path.join(pkg_config_path, '*.pc')))
            for f in pc_files:
                p_name = re.sub(r'\.pc$', '', os.path.basename(f))
                p_name = re.sub(r'\W', '_', p_name.upper())
                setattr(self.env_info, f'PKG_CONFIG_{p_name}_PREFIX', adjustPath(self.package_folder))

            appendPkgConfigPath(adjustPath(pkg_config_path), self.env_info)

# vim: ts=4 sw=4 expandtab ffs=unix ft=python foldmethod=marker :
