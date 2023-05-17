import sys

from pathlib import Path
from dataclasses import dataclass, field
from subprocess import run, CalledProcessError
from typing import List


@dataclass
class ModInfo:
    name: str
    description: str
    firmware: List[Path] = field(default_factory=list)

    def __str__(self):
        s = f'       name: {self.name}\n'
        s += f'description: {self.description}\n'

        for fw_file in self.firmware:
            s += f'   firmware: {fw_file}\n'

        return s.removesuffix('\n')


def sound_modules() -> List[Path]:
    """
    Get a list of all sound loadable kernel modules
    """
    modules = Path('/usr/lib/modules')
    subdirs = [p for p in modules.iterdir() if p.is_dir()]

    if len(subdirs) == 1:
        kernel_ver_dir = subdirs[0]
    else:
        proc_version = Path('/proc/version')

        with proc_version.open() as f:
            version = f.read()

        kernel_ver = version.split(maxsplit=3)[2]
        kernel_ver_dir = modules / kernel_ver

    sound = kernel_ver_dir / 'kernel' / 'sound'
    pathlist = Path(sound).rglob('*')

    return [p for p in pathlist if p.is_file()]


def firmware_files(package: str) -> List[Path]:
    """
    Get a list of all firmware files provided by a package
    """
    pkg_contents = run(['pacman', '-Flq', package],
                       capture_output=True, check=True,
                       encoding='UTF-8').stdout

    fw_files = []
    firmware = 'usr/lib/firmware'

    for path in pkg_contents.splitlines():
        # Skip a path if it is to a directory
        if (not path.endswith('/')
                and (p := Path(path)).is_relative_to(firmware)):
            fw_files.append(p.relative_to(firmware))

    return fw_files


def modules_requiring_firmware(modules: List[Path],
                               firmware_files: List[Path]) -> List[ModInfo]:
    """
    Get data on the modules that list any of the firmware files
    """
    data = []

    for module in modules:
        try:
            info = run(['modinfo', module],
                       capture_output=True, check=True,
                       encoding='UTF-8').stdout
        # Skip a module if it is not found
        except CalledProcessError:
            continue

        firmware_list = []

        for line in info.splitlines():
            if line.startswith('description:'):
                description = line.split(maxsplit=1)[1]
            elif (line.startswith('firmware:')
                    and (firmware := Path(line.split()[1])) in firmware_files):
                firmware_list.append(firmware)
            elif line.startswith('name:'):
                name = line.split()[1]

        if len(firmware_list):
            modinfo = ModInfo(name, description, firmware_list)
            data.append(modinfo)

    return sorted(data, key=lambda module: module.name)


def main() -> None:
    """
    Determine which sound loadable kernel modules require firmware
    provided by the alsa-firmware package
    """
    package = 'alsa-firmware'

    try:
        modules = sound_modules()
        firmware = firmware_files(package)
    # Database files do not exist or package was not found
    except CalledProcessError as error:
        print(error.stderr, end='', file=sys.stderr)
        sys.exit(1)

    data = modules_requiring_firmware(modules, firmware)

    print(f'Sound LKMs with firmware provided by the `{package}` package: ',
          end='\n\n')

    indent = '\t'
    tuple_str = 'modules = (\n'

    for module_data in data:
        tuple_str += f"{indent}'{module_data.name}',\n"

        print(module_data, end='\n\n')

        for fw_file in module_data.firmware:
            if fw_file in firmware:
                firmware.remove(fw_file)

    tuple_str = tuple_str.removesuffix(',\n') + '\n)'

    print('Firmware files without a match to a sound LKM:')

    for entry in firmware:
        print(entry)

    print('\nModules tuple:\n' + tuple_str)


if __name__ == '__main__':
    main()
