"""Package a release: tag the version, build a deterministic ZIP, draft notes.

Given a version that exists as a section in CHANGELOG.md, this script:

  * creates the annotated git tag ``v<version>`` at the current HEAD
    (only with --tag; refuses if the tag already exists),
  * builds ``autoproteus-v<version>.zip`` from the tracked tree at that
    ref — byte-for-byte reproducible: sorted paths, fixed timestamps,
    fixed permissions, so two runs on two machines produce one hash,
  * drafts the GitHub release notes from that version's CHANGELOG section.

It never pushes, uploads or publishes anything. Tags and artifacts stay
local until a human pushes the tag and creates the release. Standard
library only.
"""
import argparse
import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXED_DATE = (1980, 1, 1, 0, 0, 0)  # zip epoch; the reproducibility anchor


def changelog_section(text, version):
    """Return the CHANGELOG body under ``## <version>``, exactly.

    Version matching is exact: asking for 0.14.1 must not return 0.14.10.
    Raises ValueError when the version has no section — release notes are
    never invented.
    """
    pattern = re.compile(r'^## ' + re.escape(version) + r'[ \t]*$', re.MULTILINE)
    match = pattern.search(text)
    if not match:
        raise ValueError(f'CHANGELOG.md has no section for version {version}')
    body = text[match.end():]
    next_heading = re.search(r'^## ', body, re.MULTILINE)
    if next_heading:
        body = body[:next_heading.start()]
    return body.strip('\n').strip()


def draft_notes(version, section):
    return (f'# AutoProteus v{version}\n\n{section}\n\n'
            f'---\nFull notes for every version: see `CHANGELOG.md` in this '
            f'repository. This ZIP is a pinned, reproducible build of the '
            f'`v{version}` tag.\n')


def _git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True,
                          check=True).stdout


def tracked_paths(root, ref):
    out = _git(root, 'ls-tree', '-r', '--name-only', ref).decode('utf-8')
    return sorted(path for path in out.splitlines() if path)


def build_release_zip(root, ref):
    """Build the release ZIP bytes for a git ref, deterministically."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in tracked_paths(root, ref):
            data = _git(root, 'show', f'{ref}:{path}')
            info = zipfile.ZipInfo(path, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            archive.writestr(info, data)
    return buffer.getvalue()


def tag_exists(root, tag):
    result = subprocess.run(['git', 'rev-parse', '--verify', '--quiet',
                             f'refs/tags/{tag}'], cwd=root, capture_output=True)
    return result.returncode == 0


def create_tag(root, version, ref='HEAD'):
    """Create the annotated tag; fail closed if it already exists."""
    tag = 'v' + version
    if tag_exists(root, tag):
        raise ValueError(f'Tag {tag} already exists; refusing to move it.')
    _git(root, 'tag', '-a', tag, '-m', f'AutoProteus {tag}', ref)
    return tag


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version', help='Version with a CHANGELOG section, e.g. 0.14.1')
    parser.add_argument('--tag', action='store_true',
                        help='Create the annotated git tag at HEAD (default: no tag)')
    parser.add_argument('--ref', default='HEAD',
                        help='Git ref to package (default: HEAD; the new tag when --tag)')
    parser.add_argument('--out', help='Output directory (default: .data/releases/v<version>)')
    args = parser.parse_args(argv)

    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    section = changelog_section(changelog, args.version)  # raises if absent
    ref = args.ref
    if args.tag:
        ref = create_tag(ROOT, args.version)
        print(f'Tagged {ref} at HEAD (local only; nothing pushed).')
    out_dir = Path(args.out) if args.out else ROOT / '.data' / 'releases' / ('v' + args.version)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_bytes = build_release_zip(ROOT, ref)
    zip_path = out_dir / f'autoproteus-v{args.version}.zip'
    zip_path.write_bytes(zip_bytes)
    notes_path = out_dir / f'release-notes-v{args.version}.md'
    notes_path.write_text(draft_notes(args.version, section), encoding='utf-8')
    import hashlib
    print(f'ZIP:   {zip_path} ({len(zip_bytes)} bytes, '
          f'sha256 {hashlib.sha256(zip_bytes).hexdigest()})')
    print(f'Notes: {notes_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
