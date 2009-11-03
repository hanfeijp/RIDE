#  Copyright 2008-2009 Nokia Siemens Networks Oyj
#  
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  
#      http://www.apache.org/licenses/LICENSE-2.0
#  
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import os
import shutil

from configobj import ConfigObj, Section, UnreprError


if os.name == 'nt':
    SETTINGS_DIRECTORY = os.path.join(os.environ['APPDATA'], 'RobotFramework')
else:
    SETTINGS_DIRECTORY = os.path.expanduser('~/.robotframework')
if not os.path.exists(SETTINGS_DIRECTORY):
    os.mkdir(SETTINGS_DIRECTORY)


def initialize_settings(tool_name, source_path, dest_file_name=None):
    """ Creates settings directory and copies or merges the source to there.
    
    In case source already exists, merge is done.
    Destination file name is the source_path's file name unless dest_file_name
    is given.
    """
    settings_dir = os.path.join(SETTINGS_DIRECTORY, tool_name)
    if not os.path.exists(settings_dir):
        os.mkdir(settings_dir)
    if not dest_file_name:
        dest_file_name = os.path.basename(source_path)
    settings_path = os.path.join(settings_dir, dest_file_name)
    if not os.path.exists(settings_path):
        shutil.copy(source_path, settings_path)
    else:
        _merge_settings(source_path, settings_path)
    return os.path.abspath(settings_path)


def _merge_settings(default_path, user_path):
    settings = ConfigObj(default_path, unrepr=True)
    try:
        settings.merge(ConfigObj(user_path, unrepr=True))
    except UnreprError, err:
        raise ConfigurationError("Invalid config file '%s': %s" % (user_path, err))
    try:
        f = open(user_path, 'w')
        settings.write(f)
    finally:
        f.close()


class SectionError(Exception):
    """Used when section is tried to replace with normal value or vice versa."""


class ConfigurationError(Exception):
    """Used when settings file is invalid"""


class _Section:
    
    def __init__(self, section, parent):
        self._config_obj = section
        self._parent = parent
        
    def save(self):
        self._parent.save()

    def __setitem__(self, name, value):
        self.set(name, value)

    def __getitem__(self, name):
        value = self._config_obj[name]
        if isinstance(value, Section):
            return _Section(value, self)
        return value

    def get(self, name, default):
        """Returns specified setting or (automatically set) default."""
        try:
            return self[name]
        except KeyError:
            self.set(name, default)
            return default

    def set(self, name, value, autosave=True, override=True):
        """Sets setting 'name' value to 'value'.
        
        'autosave' can be used to define whether to save or not after values are
        changed. 'override' can be used to specify whether to override existing 
        value or not. Setting which does not exist is anyway always created.
        """
        if self._is_section(name) and not isinstance(value, _Section):
            raise SectionError("Cannot override section with value.")
        if isinstance(value, _Section):
            if override:
                self._config_obj[name] = {}
            for key, _value in value._config_obj.items():
                self[name].set(key, _value, autosave, override)
        elif name not in self._config_obj or override:
            self._config_obj[name] = value
            if autosave:
                self.save()

    def set_values(self, settings, autosave=True, override=True):
        """Set values from settings. 'settings' needs to be a dictionary.
        
        See method set for more info about 'autosave' and 'override'.
        """
        if settings:
            for key, value in settings.items():
                self.set(key, value, autosave=False, override=override)
            if autosave:
                self.save()
        return self

    def set_defaults(self, **settings):
        """Sets default values"""
        return self.set_values(settings, override=False)

    def add_section(self, name, **defaults):
        """Creates section or updates existing section with defaults."""
        if name in self._config_obj and not isinstance(self._config_obj[name], Section):
            raise SectionError("Cannot override value with section.")
        if name not in self._config_obj:
            self._config_obj[name] = {}
        return self[name].set_defaults(**defaults)

    def _is_section(self, name):
        return self._config_obj.has_key(name) and \
               isinstance(self._config_obj[name], Section)


class Settings(_Section):

    def __init__(self, user_path):
        try:
            self._config_obj = ConfigObj(user_path, unrepr=True)
        except UnreprError, error:
            raise ConfigurationError(error)

    def save(self):
        self._config_obj.write()


# TODO: This works, but needs to be refactored away from inheritance solution?
class PersistentAttributes(object):
    persistent_attributes = {}

    def __init__(self, settings):
        self._settings = settings
        self._settings.set_defaults(**self.persistent_attributes)

    def __setattr__(self, name, value):
        if name in self.persistent_attributes.keys():
            self._settings.set(name, value)
        else:
            object.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name in self.persistent_attributes.keys():
            return self._settings[name]
        return object.__getattribute__(self, name)
