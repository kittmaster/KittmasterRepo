"""
    Put this script in the root folder of your repo and it will
    zip up all addon folders, create a new zip in your zips folder
    and then update the md5 and addons.xml file
"""

import hashlib
import os
import shutil
import sys
import zipfile

from xml.etree import ElementTree

SCRIPT_VERSION = 7

# If adding a new "root" folder, add to this list so that it will get compiled.
KODI_VERSIONS_FOLDER_ROOTS = ["krypton", "leia", "matrix", "nexus", "omega", "piers", "repo", "skin", "scripts-addons"]
IGNORE = [
    ".git",
    ".github",
    ".gitignore",
    ".DS_Store",
    "thumbs.db",
    ".idea",
    "venv",
]
_COLOR_ESCAPE = "\x1b[{}m"
_COLORS = {
    "black": "30",
    "red": "31",
    "green": "4;32",
    "yellow": "3;33",
    "blue": "34",
    "magenta": "35",
    "cyan": "1;36",
    "grey": "37",
    "endc": "0",
}


def _setup_colors():
    """
    Return True if the running system's terminal supports color,
    and False otherwise.
    """
    def vt_codes_enabled_in_windows_registry():
        """
        Check the Windows registry to see if VT code handling has been enabled by default.
        This function will attempt to enable it if it's not present.
        """
        try:
            import winreg
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Console", access=winreg.KEY_ALL_ACCESS)
            try:
                reg_key_value, _ = winreg.QueryValueEx(reg_key, "VirtualTerminalLevel")
                return reg_key_value == 1
            except FileNotFoundError:
                try:
                    winreg.SetValueEx(reg_key, "VirtualTerminalLevel", 0, winreg.REG_DWORD, 1)
                    return True
                except Exception:
                    return False
        except (ImportError, FileNotFoundError):
            return False

    def is_a_tty():
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

    def legacy_support():
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            return kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7) != 0
        except Exception:
            return False

    return any([
        is_a_tty(),
        sys.platform != "win32",
        "ANSICON" in os.environ,
        "WT_SESSION" in os.environ,
        os.environ.get("TERM_PROGRAM") == "vscode",
        vt_codes_enabled_in_windows_registry(),
        legacy_support(),
    ])

_SUPPORTS_COLOR = _setup_colors()


def color_text(text, color):
    """
    Return an ANSI-colored string, if supported.
    """
    if _SUPPORTS_COLOR:
        return f"{_COLOR_ESCAPE.format(_COLORS[color])}{text}{_COLOR_ESCAPE.format(_COLORS['endc'])}"
    return text


def convert_bytes(num):
    """
    this function will convert bytes to MB.... GB... etc
    """
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return f"{num:3.1f} {x}"
        num /= 1024.0
    return f"{num:.2f} {x}"


class Generator:
    """
    Generates a new addons.xml file from each addons addon.xml file
    and a new addons.xml.md5 hash file. Must be run from the root of
    the checked-out repo.
    """

    def __init__(self, release, build_mode):
        self.release_path = release
        self.zips_path = os.path.join(self.release_path, "zips")
        self.build_mode = build_mode
        addons_xml_path = os.path.join(self.zips_path, "addons.xml")
        md5_path = os.path.join(self.zips_path, "addons.xml.md5")

        if not os.path.exists(self.zips_path):
            os.makedirs(self.zips_path)

        self._remove_binaries()

        if self._generate_addons_file(addons_xml_path):
            print(f"Successfully generated {color_text(addons_xml_path, 'yellow')}")
            if self._generate_md5_file(addons_xml_path, md5_path):
                print(f"Successfully generated {color_text(md5_path, 'yellow')}")

    def _remove_binaries(self):
        """
        Removes any and all compiled Python files before operations.
        """
        for parent, dirnames, filenames in os.walk(self.release_path):
            for fn in filenames:
                if fn.lower().endswith(("pyo", "pyc")):
                    compiled = os.path.join(parent, fn)
                    try:
                        os.remove(compiled)
                        print(f"Removed compiled python file: {color_text(compiled, 'green')}")
                    except Exception as e:
                        print(f"Failed to remove compiled python file: {color_text(compiled, 'red')} - {e}")
            dirnames[:] = [d for d in dirnames if "__pycache__" not in d.lower()]

    def _calculate_file_hash(self, filepath):
        """Calculates MD5 hash of a given file, reading in chunks."""
        hasher = hashlib.md5()
        try:
            with open(filepath, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"Could not calculate hash for {color_text(filepath, 'red')}: {e}")
            return None

    def _create_zip(self, folder, addon_id, version):
        """
        Creates a zip file and its corresponding .md5 hash file.
        Deletes old versions of the zip and md5 if they exist.
        """
        addon_folder = os.path.join(self.release_path, folder)
        zip_folder = os.path.join(self.zips_path, addon_id)
        os.makedirs(zip_folder, exist_ok=True)

        # Clean up any old zip/md5 files for this addon ID to prevent orphans
        for item in os.listdir(zip_folder):
            if item.startswith(addon_id) and (item.endswith('.zip') or item.endswith('.zip.md5')):
                 os.remove(os.path.join(zip_folder, item))

        final_zip_path = os.path.join(zip_folder, f"{addon_id}-{version}.zip")

        try:
            with zipfile.ZipFile(final_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
                root_len = len(os.path.dirname(os.path.abspath(addon_folder)))
                for root, dirs, files in os.walk(addon_folder):
                    dirs[:] = [d for d in dirs if d not in IGNORE]
                    files[:] = [f for f in files if not any(f.startswith(i) for i in IGNORE)]

                    archive_root = os.path.abspath(root)[root_len:].strip(os.sep)
                    for f in files:
                        fullpath = os.path.join(root, f)
                        archive_name = os.path.join(archive_root, f)
                        zip_file.write(fullpath, archive_name, zipfile.ZIP_DEFLATED)

            size = convert_bytes(os.path.getsize(final_zip_path))
            print(f"Zip created for {color_text(addon_id, 'cyan')} ({color_text(version, 'green')}) - {color_text(size, 'yellow')}")
            
            # ** NEW STEP: Create the individual MD5 hash for the new zip **
            if (zip_hash := self._calculate_file_hash(final_zip_path)) is not None:
                self._save_file(zip_hash, file=f"{final_zip_path}.md5")
                print(f"  -- MD5 hash created for {color_text(os.path.basename(final_zip_path), 'cyan')}")

        except Exception as e:
            print(f"Failed to create zip for {color_text(addon_id, 'red')}: {e}")


    def _copy_meta_files(self, addon_name, addon_folder):
        """
        Copy the addon.xml and relevant art files into the relevant folders in the repository.
        """
        try:
            tree = ElementTree.parse(os.path.join(self.release_path, addon_name, "addon.xml"))
            root = tree.getroot()
            copyfiles = ["addon.xml"]
            for ext in root.findall("extension"):
                if ext.get("point") in ["xbmc.addon.metadata", "kodi.addon.metadata"]:
                    if (assets := ext.find("assets")) is not None:
                        for art in [a for a in assets if a.text]:
                            copyfiles.append(os.path.normpath(art.text))

            src_folder = os.path.join(self.release_path, addon_name)
            for file in copyfiles:
                src_path = os.path.join(src_folder, file)
                if not os.path.exists(src_path): continue
                dest_path = os.path.join(addon_folder, file)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(src_path, dest_path)
        except Exception as e:
            print(f"Error copying meta files for {color_text(addon_name, 'red')}: {e}")

    def _generate_addons_file(self, addons_xml_path):
        """
        Generates zips for new or updated addons and regenerates the master addons.xml file from scratch.
        """
        old_addons = {}
        if os.path.exists(addons_xml_path):
            try:
                old_addons_xml = ElementTree.parse(addons_xml_path)
                for addon in old_addons_xml.getroot().findall("addon"):
                    old_addons[addon.get("id")] = addon.get("version")
            except ElementTree.ParseError as e:
                print(f"Warning: Could not parse existing {addons_xml_path}. Treating all as new. Error: {e}")

        folders = [
            i for i in os.listdir(self.release_path)
            if os.path.isdir(os.path.join(self.release_path, i)) and i != "zips" and not i.startswith(".")
            and os.path.exists(os.path.join(self.release_path, i, "addon.xml"))
        ]

        new_addons_root = ElementTree.Element('addons')
        has_changes = False

        for addon_name in folders:
            try:
                addon_xml_path = os.path.join(self.release_path, addon_name, "addon.xml")
                addon_root = ElementTree.parse(addon_xml_path).getroot()
                addon_id = addon_root.get('id')
                addon_version = addon_root.get('version')

                build_zip = False
                if self.build_mode == 'all':
                    build_zip = True
                elif addon_id not in old_addons:
                    print(f"Found new addon: {color_text(addon_id, 'cyan')}")
                    build_zip = True
                elif old_addons[addon_id] != addon_version:
                    print(f"Found updated addon: {color_text(addon_id, 'cyan')} ({color_text(old_addons[addon_id], 'yellow')} -> {color_text(addon_version, 'green')})")
                    build_zip = True

                if build_zip:
                    has_changes = True
                    self._create_zip(addon_name, addon_id, addon_version)
                    self._copy_meta_files(addon_name, os.path.join(self.zips_path, addon_id))

                new_addons_root.append(addon_root)

            except Exception as e:
                print(f"Excluding {color_text(addon_name, 'yellow')}: {color_text(str(e), 'red')}")

        # Only write the file if it's a full build or if changes were detected
        if self.build_mode == 'all' or has_changes:
            new_addons_root[:] = sorted(new_addons_root, key=lambda addon: addon.get('id'))
            try:
                tree = ElementTree.ElementTree(new_addons_root)
                tree.write(addons_xml_path, encoding="utf-8", xml_declaration=True)
                return True # Signal that md5 needs to be regenerated
            except Exception as e:
                print(f"An error occurred writing {color_text(addons_xml_path, 'red')}:\n{e}")
                return False
        
        print("\nNo addon changes detected. Master files are up to date.")
        return False # No changes, no need to regenerate md5

    def _generate_md5_file(self, addons_xml_path, md5_path):
        """
        Generates a new addons.xml.md5 file.
        """
        if (master_hash := self._calculate_file_hash(addons_xml_path)) is not None:
             self._save_file(master_hash, file=md5_path)
             return True
        return False

    def _save_file(self, data, file):
        """
        Saves a file.
        """
        try:
            with open(file, "w", encoding="utf-8") as f:
                f.write(data)
        except Exception as e:
            print(f"An error occurred saving {color_text(file, 'red')}:\n{e}")


if __name__ == "__main__":
    print(color_text("----------------------------------------", 'cyan'))
    print(color_text(" Addon Repository Generator", 'cyan'))
    print(color_text("----------------------------------------", 'cyan'))

    build_mode = None
    while build_mode not in ('all', 'changed'):
        response = input(color_text("Choose build mode (all/changed, a/c): ", 'yellow')).lower().strip()
        if response in ('all', 'a'):
            build_mode = 'all'
            print(color_text("Building all zips (existing zips will be overwritten).", 'blue'))
        elif response in ('changed', 'c'):
            build_mode = 'changed'
            print(color_text("Building only new or updated zips.", 'blue'))
        else:
            print(color_text("Invalid input. Please enter 'all' or 'changed'.", 'red'))

    for release in [r for r in KODI_VERSIONS_FOLDER_ROOTS if os.path.exists(r)]:
        print(color_text(f"\nProcessing release folder: {release}", 'magenta'))
        Generator(release, build_mode)
    
    print("\n\nProcessing complete.")
    input("Press Enter to Exit...")