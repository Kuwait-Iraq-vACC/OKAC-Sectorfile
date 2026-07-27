import os
import shutil

# ============================================================
# OKAC GRplugin Data File Compiler
# Compiles shared data files into the GRplugin directory
# ============================================================

OUTPUTS = [
    'OKAC/Plugins/GRplugin/',
    # 'OKAC/Plugins/GRplugin2/',  # Add more output paths here
]
SHARED    = '.data/GRplugin Shared/'
DATAFILES = '.data/DataFiles/'
INDEX     = '.Index'


def main():
    copy_single_files()
    compile_aircraft_info()
    compile_cargo_callsigns()
    compile_operator_info()
    compile_maps()
    compile_settings()
    compile_settings_local()
    compile_stands()


# ============================================================
# Single-file copies (no compilation needed)
# ============================================================

def copy_single_files():
    singles = {
        DATAFILES + 'ICAO_Aircraft.json': 'ICAO_Aircraft.json',
    }
    for src, dst in singles.items():
        for output in OUTPUTS:
            copy_file(src, output + dst)


# ============================================================
# Compiled outputs
# ============================================================

def compile_aircraft_info():
    build_single(DATAFILES + 'Aircraft Info.txt', 'GRpluginAircraftInfo.txt')

def compile_cargo_callsigns():
    build_single(DATAFILES + 'Cargo Callsigns.txt', 'GRpluginCargoCallsigns.txt')

def compile_operator_info():
    build_single(DATAFILES + 'Operator Info.txt', 'GRpluginOperatorInfo.txt')

def compile_maps():
    build('Maps/', 'GRpluginMaps.txt')

def compile_settings():
    build('Settings/', 'GRpluginSettings.txt')

def compile_settings_local():
    build('Local Settings/', 'GRpluginSettingsLocal.txt')

def compile_stands():
    build('Stands/', 'GRpluginStands.txt')


# ============================================================
# Core build logic
# ============================================================

def build(folder, output_name):
    """
    Compiles all .txt files in a shared folder into a single output file,
    then copies the result to all output directories.

    Ordering:
      1. Entries listed in .Index.txt, in order (files and/or subfolders)
      2. Any remaining .txt files or subfolders not already included,
         discovered alphabetically (subdirs first, then loose root files)
    """
    src_folder = SHARED + folder

    files = get_file_list(src_folder, folder)
    if not files:
        print(f'[SKIP] No files found for {output_name}')
        return

    primary = OUTPUTS[0] + output_name
    os.makedirs(OUTPUTS[0], exist_ok=True)

    with open(primary, 'wb') as out:
        for relative_path in files:
            full_path = src_folder + relative_path
            if not os.path.exists(full_path):
                print(f'[WARN] Missing: {full_path}')
                continue
            with open(full_path, 'rb') as f:
                shutil.copyfileobj(f, out)
                out.write(b'\n\n')

    print(f'[OK]   Built {primary} from {len(files)} file(s)')

    for output in OUTPUTS[1:]:
        os.makedirs(output, exist_ok=True)
        dst = output + output_name
        shutil.copy(primary, dst)
        print(f'[OK]   Copied to {dst}')


def build_single(src, output_name):
    """
    Copies a single source file directly to all output directories.
    Used for DataFiles that are already complete (no concatenation needed).
    """
    if not os.path.exists(src):
        print(f'[WARN] Missing source: {src}')
        return

    for output in OUTPUTS:
        os.makedirs(output, exist_ok=True)
        dst = output + output_name
        shutil.copy(src, dst)
        print(f'[OK]   Copied {src} -> {dst}')


# ============================================================
# File ordering
# ============================================================

def get_file_list(folder_path, folder_label):
    """
    Returns an ordered list of relative file paths to compile.

    If .Index.txt exists:
      - Process all index entries first (in listed order)
        Supports:
          - Specific files:   SubFolder/File.txt
          - Whole subfolders: SubFolder/
        Files within a subfolder entry are sorted alphabetically,
        including files in any nested subdirectories.
      - Then append any .txt files or subdirectories not already
        covered by the index, in alphabetical order.

    If no .Index.txt:
      - Auto-discover everything alphabetically (subdirs first,
        then loose root .txt files).
    """
    index_path = folder_path + INDEX

    if os.path.exists(index_path):
        return read_index_with_remainder(index_path, folder_label, folder_path)

    return auto_discover(folder_path)


def read_index_with_remainder(index_path, folder_label, folder_path):
    """
    Reads .Index.txt entries first, then appends any files/folders
    not already covered, discovered alphabetically.
    """
    files = []
    # Track which top-level names (files or folder prefixes) are already
    # covered so we can skip them in the remainder pass.
    covered = set()

    with open(index_path, 'r') as f:
        for raw_line in f:
            line = raw_line.split('//')[0].strip()  # strip comments
            if not line:
                continue

            if line.endswith('/'):
                # Whole subfolder — discover all .txt files recursively,
                # sorted alphabetically at each level
                sub_path = folder_path + line
                if not os.path.exists(sub_path):
                    print(f'[WARN] Subfolder not found: {sub_path}')
                    continue
                sub_files = collect_txt_files(sub_path, prefix=line)
                files.extend(sub_files)
                # Mark the top-level subfolder name as covered
                covered.add(line.rstrip('/'))
                print(f'[INFO] {line} expanded to {len(sub_files)} file(s) (recursive)')

            elif '.' in line:
                # Specific file
                files.append(line)
                # Mark the top-level component as covered (could be
                # "SubFolder/file.txt" → covers "SubFolder" prefix, or
                # a loose "file.txt" at the root)
                top = line.split('/')[0]
                covered.add(top)

            else:
                print(f'[WARN] Skipped index entry (no extension or /): "{line}" in {index_path}')

    print(f'[INFO] {folder_label} index supplied {len(files)} entry/entries')

    # ----------------------------------------------------------
    # Remainder pass: pick up anything not already covered
    # ----------------------------------------------------------
    remainder = collect_remainder(folder_path, covered)
    if remainder:
        print(f'[INFO] {folder_label} appending {len(remainder)} unlisted file(s) alphabetically')
        files.extend(remainder)

    print(f'[INFO] {folder_label} total: {len(files)} file(s)')
    return files


def collect_txt_files(folder_path, prefix=''):
    """
    Recursively collects all .txt files under folder_path,
    sorted alphabetically at each directory level.
    Returns paths relative to the parent of folder_path,
    prefixed with `prefix`.

    Order: subdirectories (depth-first, sorted) then loose files (sorted).
    """
    files = []

    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: e.name)
    except FileNotFoundError:
        print(f'[WARN] Folder not found: {folder_path}')
        return files

    # Subdirs first (depth-first)
    for entry in entries:
        if entry.is_dir() and not entry.name.startswith('.'):
            sub_prefix = prefix + entry.name + '/'
            files.extend(collect_txt_files(entry.path, prefix=sub_prefix))

    # Then loose .txt files (skip dotfiles like .Index.txt)
    for entry in entries:
        if entry.is_file() and entry.name.endswith('.txt') and not entry.name.startswith('.'):
            files.append(prefix + entry.name)

    return files


def collect_remainder(folder_path, covered):
    """
    Returns all .txt files (recursively) under folder_path that are NOT
    already covered by the index, in alphabetical order.

    A path is considered covered if its top-level component (file or
    folder name) appears in the `covered` set.
    """
    files = []

    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: e.name)
    except FileNotFoundError:
        return files

    # Subdirs not covered
    for entry in entries:
        if entry.is_dir() and not entry.name.startswith('.'):
            if entry.name not in covered:
                sub_files = collect_txt_files(entry.path, prefix=entry.name + '/')
                files.extend(sub_files)

    # Loose root .txt files not covered (skip dotfiles like .Index.txt)
    for entry in entries:
        if entry.is_file() and entry.name.endswith('.txt') and not entry.name.startswith('.'):
            if entry.name not in covered:
                files.append(entry.name)

    return files


def auto_discover(folder_path):
    """
    Walks the folder structure when no .Index.txt exists:
      - Subdirectories first, sorted alphabetically (recursed)
      - .txt files within each level, sorted alphabetically
      - Then any loose .txt files at the root, sorted alphabetically
    """
    return collect_txt_files(folder_path, prefix='')


# ============================================================
# File utilities
# ============================================================

def copy_file(src, dst):
    if not os.path.exists(src):
        print(f'[WARN] Missing source: {src}')
        return
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    shutil.copy(src, dst)
    print(f'[OK]   Copied {src} -> {dst}')


if __name__ == '__main__':
    main()