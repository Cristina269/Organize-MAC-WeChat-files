import argparse
import hashlib
import logging
import os
import shutil
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Set


# Legacy config values. You can still fill these in, but passing command line
# arguments is safer because it keeps local paths out of source control.
root_dir = ""
target_path2 = ""

# Deprecated: files are now copied directly to their final destination.
transit_path = ""

WECHAT_DIR_NAMES = {"File", "OpenData"}
CHUNK_SIZE = 1024 * 1024
DEFAULT_STABLE_SECONDS = 5


def timestamp_to_month(timestamp: float) -> str:
    return time.strftime("%Y-%m", time.localtime(timestamp))


def archive_month(file_path: Path) -> str:
    stat_result = file_path.stat()
    timestamp = getattr(stat_result, "st_birthtime", None)
    if timestamp is None:
        timestamp = stat_result.st_mtime
    return timestamp_to_month(timestamp)


def compute_md5(file_path: Path) -> str:
    digest = hashlib.md5()
    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_month_dir(target_root: Path, month: str) -> Path:
    target_dir = target_root / month
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def get_wechat_file_paths(source_root: Path) -> List[Path]:
    wechat_paths: List[Path] = []
    for current_path, dir_names, _ in os.walk(str(source_root)):
        current = Path(current_path)
        if current.name in WECHAT_DIR_NAMES:
            wechat_paths.append(current)
            dir_names[:] = []
    return wechat_paths


def iter_source_files(source_roots: Iterable[Path]) -> Iterable[Path]:
    seen: Set[Path] = set()
    for source_root in source_roots:
        for file_path in source_root.rglob("*"):
            if not file_path.is_file():
                continue

            resolved = safe_resolve(file_path)
            if resolved in seen:
                continue

            seen.add(resolved)
            yield file_path


def build_md5_index(
    target_root: Path, exclude_paths: Optional[Set[Path]] = None
) -> DefaultDict[str, List[Path]]:
    md5_index: DefaultDict[str, List[Path]] = defaultdict(list)
    exclude_paths = exclude_paths or set()

    if not target_root.exists():
        return md5_index

    for file_path in target_root.rglob("*"):
        if not file_path.is_file():
            continue

        if safe_resolve(file_path) in exclude_paths:
            continue

        try:
            md5_index[compute_md5(file_path)].append(file_path)
        except OSError as exc:
            logging.warning("Could not index target file %s: %s", file_path, exc)

    return md5_index


def is_file_stable(file_path: Path, stable_seconds: float) -> bool:
    if stable_seconds <= 0:
        return True

    try:
        stat_result = file_path.stat()
    except OSError as exc:
        logging.warning("Could not stat source file %s: %s", file_path, exc)
        return False

    return (time.time() - stat_result.st_mtime) >= stable_seconds


def unique_destination(
    target_dir: Path,
    source_name: str,
    file_md5: str,
    reserved_paths: Optional[Set[Path]] = None,
) -> Path:
    reserved_paths = reserved_paths or set()
    source_path = Path(source_name)
    suffix = source_path.suffix
    stem = source_path.stem
    if not stem:
        stem = source_path.name

    base_name = f"{stem}_{file_md5[:12]}"
    candidate = target_dir / f"{base_name}{suffix}"
    counter = 1
    while candidate.exists() or safe_resolve(candidate) in reserved_paths:
        candidate = target_dir / f"{base_name}_{counter}{suffix}"
        counter += 1
    return candidate


def copy_file(source_file: Path, destination: Path, dry_run: bool) -> None:
    if dry_run:
        logging.info("[dry-run] copy %s -> %s", source_file, destination)
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, destination)


def archive_files(
    source_root: Path,
    target_root: Path,
    dry_run: bool = False,
    stable_seconds: float = DEFAULT_STABLE_SECONDS,
    exclude_paths: Optional[Set[Path]] = None,
) -> Dict[str, int]:
    source_root = safe_resolve(source_root)
    target_root = safe_resolve(target_root)

    if not source_root.exists():
        raise FileNotFoundError(f"source root does not exist: {source_root}")

    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)

    exclude_paths = {safe_resolve(path) for path in (exclude_paths or set())}
    exclude_paths.add(safe_resolve(target_root / "archive_wechat_file.log"))
    md5_index = build_md5_index(target_root, exclude_paths=exclude_paths)
    wechat_paths = get_wechat_file_paths(source_root)
    target_root_resolved = safe_resolve(target_root)

    if not wechat_paths:
        logging.warning("No File/OpenData directories found under %s", source_root)

    summary = {
        "copied": 0,
        "renamed": 0,
        "skipped_duplicate": 0,
        "skipped_unstable": 0,
        "skipped_target": 0,
        "failed": 0,
    }
    planned_destinations: Set[Path] = set()

    for source_file in iter_source_files(wechat_paths):
        source_resolved = safe_resolve(source_file)
        if is_relative_to(source_resolved, target_root_resolved):
            summary["skipped_target"] += 1
            logging.info("Skip target file found during source scan: %s", source_file)
            continue

        if not is_file_stable(source_file, stable_seconds):
            summary["skipped_unstable"] += 1
            logging.info("Skip unstable source file: %s", source_file)
            continue

        try:
            source_md5 = compute_md5(source_file)
            if source_md5 in md5_index:
                summary["skipped_duplicate"] += 1
                logging.info(
                    "Skip duplicate content: %s already exists at %s",
                    source_file,
                    md5_index[source_md5][0],
                )
                continue

            month = archive_month(source_file)
            if dry_run:
                target_dir = target_root / month
            else:
                target_dir = ensure_month_dir(target_root, month)
            destination = target_dir / source_file.name
            renamed = False

            if destination.exists() or safe_resolve(destination) in planned_destinations:
                destination = unique_destination(
                    target_dir, source_file.name, source_md5, planned_destinations
                )
                renamed = True

            copy_file(source_file, destination, dry_run)
            md5_index[source_md5].append(destination)
            planned_destinations.add(safe_resolve(destination))

            if renamed:
                summary["renamed"] += 1
                logging.info("Copied with new name: %s -> %s", source_file, destination)
            else:
                summary["copied"] += 1
                logging.info("Copied: %s -> %s", source_file, destination)

        except OSError as exc:
            summary["failed"] += 1
            logging.error("Failed to archive %s: %s", source_file, exc)

    return summary


def configure_logging(log_file: Optional[Path]) -> None:
    handlers: List[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive Mac WeChat files by month with content de-duplication."
    )
    parser.add_argument("--root-dir", default=root_dir, help="WeChat data root path.")
    parser.add_argument(
        "--target-dir", default=target_path2, help="Archive destination root path."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned copies without writing files.",
    )
    parser.add_argument(
        "--stable-seconds",
        type=float,
        default=DEFAULT_STABLE_SECONDS,
        help="Skip source files modified within this many seconds.",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="Optional log file path. Defaults to <target-dir>/archive_wechat_file.log.",
    )
    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_path_arg(parser: argparse.ArgumentParser, value: str, name: str) -> Path:
    if not value:
        parser.error(
            f"{name} is required. Pass it as an argument or set it in the file."
        )
    return Path(value).expanduser()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    source_root = validate_path_arg(parser, args.root_dir, "--root-dir")
    target_root = validate_path_arg(parser, args.target_dir, "--target-dir")

    if args.log_file:
        log_file = Path(args.log_file).expanduser()
    elif args.dry_run:
        log_file = None
    else:
        log_file = target_root / "archive_wechat_file.log"
    configure_logging(log_file)

    try:
        summary = archive_files(
            source_root=source_root,
            target_root=target_root,
            dry_run=args.dry_run,
            stable_seconds=args.stable_seconds,
            exclude_paths={safe_resolve(log_file)} if log_file else None,
        )
    except Exception as exc:
        logging.error("Archive failed: %s", exc)
        return 1

    logging.info("Summary: %s", summary)
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
