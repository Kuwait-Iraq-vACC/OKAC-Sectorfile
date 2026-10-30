import os
import shutil

# ============================================================
# OKAC TopSky Data File Compiler
# Compiles shared data files into each TopSky plugin variant
# ============================================================
#
# Three plugin variants share most of the same data:
#   - TopSky            : full compile, Realistic colours
#   - TopSky - Light     : full compile, Light colours
#   - TopSky Aerodrome  : maps only, built from its own separate
#                         Maps/Aerodrome/ dataset
#
# COLOURS:
# Maps/.Index lists "!Colours/" as a plain folder entry, and that
# folder contains both Realistic.txt and Light.txt. Left alone, the
# compiler would pull in every .txt file under a listed folder — i.e.
# BOTH colour files — stacking two (sometimes conflicting) sets of
# COLORDEFs into the output. Instead, whenever the compiler hits a
# folder named "!Colours" it hardcodes which single file to use, based
# on the variant's 'colour' setting below ('Realistic' or 'Light').
# Everything else in that folder is ignored.
#
# NOTE ON AERODROME:
# Currently assumed to only need the Maps step (built from
# Maps/Aerodrome/.Index rather than the normal Maps/.Index) plus the
# single-file ICAO data copies. Add step names to its 'steps' list
# below if it also needs Areas/Airspace/CPDLC/MSAW/Radars/SSRcodes/
# Settings.
# ============================================================

SHARED = '.data/TopSky Shared/'
INDEX  = '.Index'

# The folder name (as it appears in .Index) whose contents should be
# hardcoded to a single file rather than expanded in full.
COLOURS_FOLDER_NAME = '!Colours'

# Folder names that live inside a compiled tree but must NEVER be pulled
# in automatically (via remainder/auto-discovery) — only ever touched
# when explicitly targeted (e.g. Aerodrome's own 'maps_source' step).
# Without this, an unlisted folder like "Aerodrome" sitting inside
# Maps/ gets silently swept into the normal TopSky/TopSky - Light Maps
# build too, which is how its Colour Definitions.txt ended up
# overwriting the correct Realistic/Light colours.
EXCLUDED_FOLDER_NAMES = {'Aerodrome'}

# Each variant defines:
#   name          - label used in log output
#   output        - destination plugin folder
#   steps         - which compile steps to run for this variant
#   colour        - 'Realistic' or 'Light' — picks which file inside
#                   any "!Colours/" folder gets used. Omit/None for
#                   variants that don't touch that folder.
#   <step>_source - (optional) override the source folder used for that
#                   step, relative to SHARED. Defaults to the folder in
#                   STEP_SOURCE_FOLDERS below.
VARIANTS = [
    {
        'name': 'TopSky',
        'output': 'OKAC/Plugins/TopSky/',
        'steps': ['areas', 'airspace', 'cpdlc', 'maps', 'msaw', 'radars', 'ssr_codes', 'settings'],
        'colour': 'Realistic',
    },
    {
        'name': 'TopSky - Light',
        'output': 'OKAC/Plugins/TopSky - Light/',
        'steps': ['areas', 'airspace', 'cpdlc', 'maps', 'msaw', 'radars', 'ssr_codes', 'settings'],
        'colour': 'Light',
    },
    {
        'name': 'TopSky Aerodrome',
        'output': 'OKAC/Plugins/TopSky Aerodrome/',
        'steps': ['maps'],
        'maps_source': 'Maps/Aerodrome/',
    },
]

STEP_OUTPUT_NAMES = {
    'areas':     'TopSkyAreas.txt',
    'airspace':  'TopSkyAirspace.txt',
    'cpdlc':     'TopSkyCPDLC.txt',
    'maps':      'TopSkyMaps.txt',
    'msaw':      'TopSkyMSAW.txt',
    'radars':    'TopSkyRadars.txt',
    'ssr_codes': 'TopSkySSRcodes.txt',
    'settings':  'TopSkySettings.txt',
}

STEP_SOURCE_FOLDERS = {
    'areas':     'Areas/',
    'airspace':  'Airspace/',
    'cpdlc':     'CPDLC/',
    'maps':      'Maps/',
    'msaw':      'MSAW/',
    'radars':    'Radars/',
    'ssr_codes': 'SSRcodes/',
    'settings':  'Settings/',
}


def main():
    for variant in VARIANTS:
        print(f"\n=== Building {variant['name']} -> {variant['output']} ===")
        copy_single_files(variant)
        for step in variant['steps']:
            folder = variant.get(f'{step}_source', STEP_SOURCE_FOLDERS[step])
            build(variant, folder, STEP_OUTPUT_NAMES[step])


# ============================================================
# Single-file copies (no compilation needed)
# ============================================================

def copy_single_files(variant):
    singles = {
        'DataFiles/ICAO_Aircraft.json':  'ICAO_Aircraft.json',
        'DataFiles/ICAO_Aircraft.txt':   'ICAO_Aircraft.txt',
        'DataFiles/ICAO_Airlines.txt':   'ICAO_Airlines.txt',
        'DataFiles/ICAO_Airports.txt':   'ICAO_Airports.txt',
    }
    for src, dst in singles.items():
        copy_file(SHARED + src, variant['output'] + dst)


# ============================================================
# Core build logic
# ============================================================

def build(variant, folder, output_name):
    """
    Compiles all .txt files in a shared folder into a single output
    file for this variant.
    """
    src_folder = SHARED + folder
    colour = variant.get('colour')

    files = get_file_list(src_folder, colour)
    if not files:
        print(f'[SKIP] No files found for {output_name} ({folder})')
        return

    deduped = list(dict.fromkeys(files))
    if len(deduped) != len(files):
        print(f'[INFO] Removed {len(files) - len(deduped)} duplicate file reference(s)')
    files = deduped

    dst = variant['output'] + output_name
    os.makedirs(variant['output'], exist_ok=True)

    written = 0
    with open(dst, 'wb') as out:
        for relative_path in files:
            full_path = src_folder + relative_path
            if not os.path.exists(full_path):
                print(f'[WARN] Missing: {full_path}')
                continue
            with open(full_path, 'rb') as f:
                shutil.copyfileobj(f, out)
                out.write(b'\n\n')
            written += 1

    missing = len(files) - written
    print(f'[OK]   Built {dst} from {written} file(s)'
          + (f' ({missing} missing)' if missing else ''))


# ============================================================
# File ordering
#
# Same logic as the ORBB compiler (.Index at any depth is honored,
# with alphabetical auto-discovery filling in anything not listed),
# plus a hardcoded special case: a folder named "!Colours" is never
# expanded in full — only <colour>.txt from it is used.
# ============================================================

def get_file_list(folder_path, colour):
    return collect_txt_files(folder_path, prefix='', colour=colour)


def collect_txt_files(folder_path, prefix='', colour=None):
    index_path = os.path.join(folder_path, INDEX)

    if os.path.exists(index_path):
        return read_index_with_remainder(folder_path, prefix, index_path, colour)

    return auto_discover(folder_path, prefix=prefix, colour=colour)


def read_index_with_remainder(folder_path, prefix, index_path, colour):
    files = []
    covered = set()
    label = prefix.rstrip('/') or '(root)'

    # utf-8-sig so a BOM (added by some Windows editors) doesn't get
    # glued onto the first entry and make it unresolvable
    with open(index_path, 'r', encoding='utf-8-sig') as f:
        for raw_line in f:
            line = raw_line.split('//')[0].strip()
            if not line:
                continue

            if line.endswith('/'):
                sub_name = line.rstrip('/')

                if sub_name in EXCLUDED_FOLDER_NAMES:
                    print(f'[WARN] "{line}" in {index_path} points at an excluded folder — skipping')
                    covered.add(sub_name.split('/')[0])
                    continue

                if sub_name == COLOURS_FOLDER_NAME:
                    add_colour_file(files, folder_path, prefix, sub_name, colour)
                    covered.add(sub_name.split('/')[0])
                    continue

                sub_path = os.path.join(folder_path, sub_name)
                if not os.path.exists(sub_path):
                    print(f'[WARN] Subfolder not found: {sub_path}')
                    continue
                sub_files = collect_txt_files(sub_path, prefix=prefix + sub_name + '/', colour=colour)
                files.extend(sub_files)
                # Only the top-level segment matters here — collect_remainder()
                # checks entry.name (immediate child of folder_path) against this
                # set, so a nested entry like "SID_STAR/33Config" must still mark
                # "SID_STAR" as covered, or the remainder scan will recurse into
                # it again and duplicate everything already pulled in above.
                covered.add(sub_name.split('/')[0])
                print(f'[INFO] {prefix}{line} expanded to {len(sub_files)} file(s)')

            elif '.' in line:
                files.append(prefix + line)
                top = line.split('/')[0]
                covered.add(top)

            else:
                print(f'[WARN] Skipped index entry (no extension or /): "{line}" in {index_path}')

    print(f'[INFO] {label} index supplied {len(files)} entry/entries')

    remainder = collect_remainder(folder_path, covered, prefix, colour)
    if remainder:
        print(f'[INFO] {label} appending {len(remainder)} unlisted file(s) alphabetically')
        files.extend(remainder)

    print(f'[INFO] {label} total: {len(files)} file(s)')
    return files


def collect_remainder(folder_path, covered, prefix, colour):
    files = []
    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: e.name)
    except FileNotFoundError:
        return files

    for entry in entries:
        if entry.is_dir() and not entry.name.startswith('.'):
            if entry.name in covered:
                continue
            if entry.name in EXCLUDED_FOLDER_NAMES:
                print(f'[INFO] {prefix}{entry.name}/ skipped (excluded folder)')
                continue
            if entry.name == COLOURS_FOLDER_NAME:
                add_colour_file(files, folder_path, prefix, entry.name, colour)
                continue
            sub_files = collect_txt_files(entry.path, prefix=prefix + entry.name + '/', colour=colour)
            files.extend(sub_files)

    for entry in entries:
        if entry.is_file() and entry.name.endswith('.txt') and not entry.name.startswith('.'):
            if entry.name not in covered:
                files.append(prefix + entry.name)

    return files


def auto_discover(folder_path, prefix='', colour=None):
    files = []
    try:
        entries = sorted(os.scandir(folder_path), key=lambda e: e.name)
    except FileNotFoundError:
        print(f'[WARN] Folder not found: {folder_path}')
        return files

    for entry in entries:
        if entry.is_dir() and not entry.name.startswith('.'):
            if entry.name in EXCLUDED_FOLDER_NAMES:
                print(f'[INFO] {prefix}{entry.name}/ skipped (excluded folder)')
                continue
            if entry.name == COLOURS_FOLDER_NAME:
                add_colour_file(files, folder_path, prefix, entry.name, colour)
                continue
            files.extend(collect_txt_files(entry.path, prefix=prefix + entry.name + '/', colour=colour))

    for entry in entries:
        if entry.is_file() and entry.name.endswith('.txt') and not entry.name.startswith('.'):
            files.append(prefix + entry.name)

    return files


def add_colour_file(files, folder_path, prefix, folder_name, colour):
    """
    Hardcoded handling for the "!Colours" folder: pick exactly one file
    (Realistic.txt or Light.txt) instead of including everything inside it.
    """
    if not colour:
        print(f'[WARN] Hit "{folder_name}/" but this variant has no colour set — skipping')
        return

    filename = f'{colour}.txt'
    full_path = os.path.join(folder_path, folder_name, filename)
    if not os.path.exists(full_path):
        print(f'[WARN] Colour file not found: {full_path}')
        return

    files.append(f'{prefix}{folder_name}/{filename}')
    print(f'[INFO] {prefix}{folder_name}/ -> using {filename} only')


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