#!/usr/bin/env python3
"""
Common App PDF Splitter & Universal Compressor
----------------------------------------------
Divides a heavy PDF for Common App upload slots (limit: <= 2.0 MB per slot).
- Priority 1: Original Quality First (uses 2 parts if <= 2MB, or 3 parts if needed to stay lossless).
- Priority 2: Higher Quality Maximization (if compression is required, chooses 3 parts to maximize DPI).
- Universal Quality: Identical DPI and compression setting applied across all parts.
- Dedicated Folders: Outputs into '<filename>_output/' as 1.pdf, 2.pdf, etc.
"""

import os
import sys
import shutil
import argparse
import subprocess
import tempfile
from pathlib import Path
import pikepdf

# Default safe target size in MB (1.95 MB ensures it never exceeds Common App's strict 2.0 MB limit)
DEFAULT_TARGET_MB = 1.95

# Universal compression ladder (ordered from highest quality to lowest)
QUALITY_PROFILES = [
    {
        "name": "Original (100% Lossless Quality)",
        "type": "none",
        "gs_setting": None,
        "dpi": None,
    },
    {
        "name": "Ultra High (Prepress 300 DPI)",
        "type": "gs",
        "gs_setting": "/prepress",
        "dpi": 300,
    },
    {
        "name": "High Quality (Printer 220 DPI)",
        "type": "gs",
        "gs_setting": "/printer",
        "dpi": 220,
    },
    {
        "name": "Medium High (180 DPI)",
        "type": "gs",
        "gs_setting": "/ebook",
        "dpi": 180,
    },
    {
        "name": "Balanced eBook (150 DPI)",
        "type": "gs",
        "gs_setting": "/ebook",
        "dpi": 150,
    },
    {
        "name": "Good Screen (120 DPI)",
        "type": "gs",
        "gs_setting": "/ebook",
        "dpi": 120,
    },
    {
        "name": "Standard Screen (96 DPI)",
        "type": "gs",
        "gs_setting": "/screen",
        "dpi": 96,
    },
    {
        "name": "Compact (72 DPI)",
        "type": "gs",
        "gs_setting": "/screen",
        "dpi": 72,
    },
    {
        "name": "Heavy Compression (50 DPI)",
        "type": "gs",
        "gs_setting": "/screen",
        "dpi": 50,
    },
    {
        "name": "Maximum Compression (36 DPI)",
        "type": "gs",
        "gs_setting": "/screen",
        "dpi": 36,
    },
]


def format_size(bytes_size: int) -> str:
    """Format bytes into readable string (MB and KB)."""
    mb = bytes_size / (1024 * 1024)
    kb = bytes_size / 1024
    if mb >= 1.0:
        return f"{mb:.2f} MB ({kb:.0f} KB)"
    return f"{kb:.1f} KB"


def check_ghostscript() -> bool:
    """Check if Ghostscript ('gs') is installed."""
    return shutil.which("gs") is not None


def get_page_sizes(input_pdf_path: Path) -> list[int]:
    """Measure the byte size of each individual page in the PDF."""
    sizes = []
    with pikepdf.Pdf.open(input_pdf_path) as pdf:
        for page in pdf.pages:
            single = pikepdf.Pdf.new()
            single.pages.append(page)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_name = tmp.name
            single.save(tmp_name)
            sizes.append(os.path.getsize(tmp_name))
            os.remove(tmp_name)
    return sizes


def split_pdf_pages_smart(page_sizes: list[int], num_parts: int, target_bytes: int):
    """
    Intelligently partitions pages into num_parts chunks based on actual page weights.
    Balances uneven scans to ensure all parts fit <= target_bytes whenever possible.
    Returns: list of (start_page_0_indexed, end_page_0_indexed).
    """
    n = len(page_sizes)
    if num_parts <= 1 or n <= 1:
        return [(0, n)]
    if num_parts >= n:
        return [(i, i + 1) for i in range(n)]

    if num_parts == 2:
        valid_cuts = []
        for c in range(1, n):
            s1 = sum(page_sizes[:c])
            s2 = sum(page_sizes[c:])
            max_s = max(s1, s2)
            spread = abs(s1 - s2)
            if max_s <= target_bytes:
                valid_cuts.append((spread, c))
        if valid_cuts:
            valid_cuts.sort()
            best_c = valid_cuts[0][1]
            return [(0, best_c), (best_c, n)]
        all_cuts = [(abs(sum(page_sizes[:c]) - sum(page_sizes[c:])), c) for c in range(1, n)]
        all_cuts.sort()
        best_c = all_cuts[0][1]
        return [(0, best_c), (best_c, n)]

    if num_parts == 3:
        valid_cuts = []
        for c1 in range(1, n - 1):
            s1 = sum(page_sizes[:c1])
            for c2 in range(c1 + 1, n):
                s2 = sum(page_sizes[c1:c2])
                s3 = sum(page_sizes[c2:])
                max_s = max(s1, s2, s3)
                spread = max_s - min(s1, s2, s3)
                if max_s <= target_bytes:
                    valid_cuts.append((spread, c1, c2))
        if valid_cuts:
            valid_cuts.sort()
            _, best_c1, best_c2 = valid_cuts[0]
            return [(0, best_c1), (best_c1, best_c2), (best_c2, n)]
        all_cuts = []
        for c1 in range(1, n - 1):
            s1 = sum(page_sizes[:c1])
            for c2 in range(c1 + 1, n):
                s2 = sum(page_sizes[c1:c2])
                s3 = sum(page_sizes[c2:])
                all_cuts.append((max(s1, s2, s3), max(s1, s2, s3) - min(s1, s2, s3), c1, c2))
        all_cuts.sort()
        best_c1, best_c2 = all_cuts[0][2], all_cuts[0][3]
        return [(0, best_c1), (best_c1, best_c2), (best_c2, n)]

    base = n // num_parts
    rem = n % num_parts
    chunks = []
    start = 0
    for i in range(num_parts):
        count = base + (1 if i < rem else 0)
        chunks.append((start, start + count))
        start += count
    return chunks


def extract_chunk_to_pdf(input_pdf_path: Path, output_pdf_path: Path, start_page: int, end_page: int):
    """Extract a slice of pages from input_pdf to output_pdf with stream compression."""
    with pikepdf.Pdf.open(input_pdf_path) as src_pdf:
        dst_pdf = pikepdf.Pdf.new()
        for idx in range(start_page, end_page):
            dst_pdf.pages.append(src_pdf.pages[idx])
        dst_pdf.save(
            output_pdf_path,
            compress_streams=True,
            linearize=True,
            object_stream_mode=pikepdf.ObjectStreamMode.generate
        )


def compress_pdf_with_gs(input_path: Path, output_path: Path, setting: str, dpi: int) -> bool:
    """Run Ghostscript to compress a PDF with universal quality settings."""
    cmd = [
        "gs",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-dPDFSETTINGS={setting}",
        "-dDownsampleColorImages=true",
        f"-dColorImageResolution={dpi}",
        "-dColorImageDownsampleThreshold=1.0",
        "-dColorImageDownsampleType=/Bicubic",
        "-dDownsampleGrayImages=true",
        f"-dGrayImageResolution={dpi}",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dDownsampleMonoImages=true",
        f"-dMonoImageResolution={dpi}",
        "-dMonoImageDownsampleThreshold=1.0",
        "-dMonoImageDownsampleType=/Bicubic",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return res.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Warning: Ghostscript error: {e.stderr.strip()}", file=sys.stderr)
        return False


def find_candidate_pdfs(search_dir: Path):
    """Find candidate PDF files in search_dir, ignoring previously generated parts."""
    pdfs = []
    for file in sorted(search_dir.glob("*.pdf")):
        if "_part" in file.stem or file.stem.isdigit():
            continue
        pdfs.append(file)
    return pdfs


def resolve_input_file(arg_file: str | None) -> Path:
    """Resolve input file from arguments, current directory scan, or interactive prompt."""
    if arg_file:
        path = Path(arg_file.strip().strip("'\"")).resolve()
        if not path.is_file():
            print(f"Error: File '{path}' does not exist.")
            sys.exit(1)
        return path

    cwd = Path.cwd()
    candidates = find_candidate_pdfs(cwd)

    if len(candidates) == 1:
        chosen = candidates[0]
        print(f"Found PDF: {chosen.name}")
        try:
            resp = input("Process this file? [Y/n]: ").strip().lower()
            if resp in ("", "y", "yes"):
                return chosen
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

    elif len(candidates) > 1:
        print("Multiple PDF files found in folder:")
        for idx, file in enumerate(candidates, 1):
            sz = format_size(file.stat().st_size)
            print(f"  [{idx}] {file.name} ({sz})")
        try:
            choice = input(f"Select a file [1-{len(candidates)}] or type path: ").strip()
            if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                return candidates[int(choice) - 1]
            if choice:
                p = Path(choice.strip("'\"")).resolve()
                if p.is_file():
                    return p
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)

    try:
        user_input = input("Enter path to your PDF: ").strip().strip("'\"")
        p = Path(user_input).resolve()
        if not p.is_file():
            print(f"Error: File '{p}' does not exist.")
            sys.exit(1)
        return p
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        sys.exit(0)


def test_split_configuration(
    input_path: Path,
    page_chunks: list,
    target_bytes: int,
    gs_available: bool,
    temp_dir: Path,
    prefix: str,
    verbose: bool = False
):
    """
    Evaluates whether page_chunks can fit under target_bytes.
    Checks uncompressed first, then scans universal quality profiles.
    Returns: (success: bool, chosen_profile: dict, part_paths: list[Path])
    """
    num_parts = len(page_chunks)
    raw_parts = []
    for i, (start_p, end_p) in enumerate(page_chunks, 1):
        raw_file = temp_dir / f"{prefix}_raw_part_{i}.pdf"
        extract_chunk_to_pdf(input_path, raw_file, start_p, end_p)
        raw_parts.append(raw_file)

    raw_sizes = [f.stat().st_size for f in raw_parts]
    max_raw_size = max(raw_sizes)

    if max_raw_size <= target_bytes:
        if verbose:
            print(f"  -> {num_parts} parts fit under 2MB natively with original quality.")
        return True, QUALITY_PROFILES[0], raw_parts

    if not gs_available:
        return False, None, raw_parts

    tested_profiles = [p for p in QUALITY_PROFILES if p["type"] == "gs"]
    for profile in tested_profiles:
        p_name = profile["name"]
        setting = profile["gs_setting"]
        dpi = profile["dpi"]

        trial_files = []
        trial_sizes = []
        success = True

        for i, raw_f in enumerate(raw_parts, 1):
            trial_f = temp_dir / f"{prefix}_trial_{dpi}dpi_part_{i}.pdf"
            if not compress_pdf_with_gs(raw_f, trial_f, setting, dpi):
                success = False
                break
            sz = trial_f.stat().st_size
            trial_files.append(trial_f)
            trial_sizes.append(sz)

        if not success:
            continue

        max_trial_size = max(trial_sizes)
        passed = max_trial_size <= target_bytes

        if verbose:
            symbol = "PASS" if passed else "FAIL"
            sizes_str = ", ".join(f"P{idx}:{format_size(s)}" for idx, s in enumerate(trial_sizes, 1))
            print(f"  [{num_parts}-Part] {p_name:<28} max: {format_size(max_trial_size):<12} [{symbol}] ({sizes_str})")

        if passed:
            return True, profile, trial_files

    last_files = [
        temp_dir / f"{prefix}_trial_{tested_profiles[-1]['dpi']}dpi_part_{i}.pdf"
        for i in range(1, num_parts + 1)
    ]
    return False, tested_profiles[-1], last_files


def choose_optimal_configuration(
    input_path: Path,
    target_bytes: int,
    parts_arg: str,
    gs_available: bool,
    temp_dir: Path,
    verbose: bool = False
):
    """
    Selects optimal split & compression configuration.
    Priority 1: Original Lossless Quality (2 parts if fits, otherwise 3 parts if fits).
    Priority 2: Higher DPI Quality (when compression required, choose 3 parts).
    """
    page_sizes = get_page_sizes(input_path)
    total_pages = len(page_sizes)

    if parts_arg != "auto":
        requested_k = min(int(parts_arg), total_pages)
        chunks = split_pdf_pages_smart(page_sizes, requested_k, target_bytes)
        passed, profile, paths = test_split_configuration(
            input_path, chunks, target_bytes, gs_available, temp_dir, f"forced_k{requested_k}", verbose=verbose
        )
        return requested_k, chunks, profile, paths

    candidate_ks = [k for k in [2, 3] if k <= total_pages]
    if not candidate_ks:
        candidate_ks = [1]

    # --- Phase 1: Original Quality Check ---
    uncompressed_data = {}
    for k in candidate_ks:
        chunks = split_pdf_pages_smart(page_sizes, k, target_bytes)
        raw_parts = []
        for i, (sp, ep) in enumerate(chunks, 1):
            raw_f = temp_dir / f"p1_k{k}_raw_part_{i}.pdf"
            extract_chunk_to_pdf(input_path, raw_f, sp, ep)
            raw_parts.append(raw_f)
        sizes = [f.stat().st_size for f in raw_parts]
        max_sz = max(sizes)
        fits = max_sz <= target_bytes
        uncompressed_data[k] = {
            "chunks": chunks,
            "paths": raw_parts,
            "sizes": sizes,
            "max_size": max_sz,
            "fits": fits
        }
        if verbose:
            sizes_str = ", ".join(f"P{idx}:{format_size(s)}" for idx, s in enumerate(sizes, 1))
            status_label = "FITS" if fits else "EXCEEDS"
            print(f"  {k}-Part Uncompressed: max={format_size(max_sz):<12} [{status_label}] ({sizes_str})")

    # If 2 parts fits uncompressed -> use 2 parts (100% original quality)
    if 2 in uncompressed_data and uncompressed_data[2]["fits"]:
        res = uncompressed_data[2]
        return 2, res["chunks"], QUALITY_PROFILES[0], res["paths"]

    # If 3 parts fits uncompressed -> use 3 parts (100% original quality)
    if 3 in uncompressed_data and uncompressed_data[3]["fits"]:
        res = uncompressed_data[3]
        return 3, res["chunks"], QUALITY_PROFILES[0], res["paths"]

    # --- Phase 2: Compression Required -> Choose 3 parts to maximize DPI ---
    if 3 in candidate_ks:
        chunks_3 = uncompressed_data[3]["chunks"]
        passed_3, profile_3, paths_3 = test_split_configuration(
            input_path, chunks_3, target_bytes, gs_available, temp_dir, "p2_comp_k3", verbose=verbose
        )
        return 3, chunks_3, profile_3, paths_3

    if 2 in candidate_ks:
        chunks_2 = uncompressed_data[2]["chunks"]
        passed_2, profile_2, paths_2 = test_split_configuration(
            input_path, chunks_2, target_bytes, gs_available, temp_dir, "p2_comp_k2", verbose=verbose
        )
        return 2, chunks_2, profile_2, paths_2

    k = candidate_ks[0]
    return k, uncompressed_data[k]["chunks"], QUALITY_PROFILES[0], uncompressed_data[k]["paths"]


def process_pdf(input_path: Path, output_dir: Path, target_mb: float, parts_arg: str, verbose: bool = False):
    target_bytes = int(target_mb * 1024 * 1024)
    gs_available = check_ghostscript()

    try:
        with pikepdf.Pdf.open(input_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)

    if total_pages == 0:
        print("Error: The PDF has 0 pages.")
        sys.exit(1)

    print("-" * 60)
    print(f"Document: {input_path.name}")
    print(f"Size:     {format_size(input_path.stat().st_size)} ({total_pages} pages)")
    print(f"Limit:    <= {target_mb:.2f} MB per slot")

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        chosen_k, selected_chunks, selected_profile, selected_part_paths = choose_optimal_configuration(
            input_path=input_path,
            target_bytes=target_bytes,
            parts_arg=parts_arg,
            gs_available=gs_available,
            temp_dir=temp_dir,
            verbose=verbose
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Strategy: {chosen_k} slots @ {selected_profile['name']}")
        print(f"Folder:   {output_dir.name}/")
        print("-" * 60)

        all_under_target = True
        for i, (start_p, end_p) in enumerate(selected_chunks, 1):
            src_f = selected_part_paths[i - 1]
            dest_name = f"{i}.pdf"
            dest_path = output_dir / dest_name
            shutil.copy2(src_f, dest_path)

            file_sz = dest_path.stat().st_size
            is_under = file_sz <= target_bytes
            if not is_under:
                all_under_target = False

            status_tag = "OK" if is_under else "OVER LIMIT"
            print(f"  Slot {i}: {dest_name:<6} (Pages {start_p + 1:2d}-{end_p:2d}) -> {format_size(file_sz):<16} [{status_tag}]")

        print("-" * 60)
        if all_under_target:
            print("Done: All files are ready for Common App upload.")
        else:
            print("Notice: Some files exceed target limit. Check sizes above.")


def main():
    parser = argparse.ArgumentParser(
        description="Split a heavy PDF for Common App (< 2MB per slot)."
    )
    parser.add_argument(
        "input_pdf",
        nargs="?",
        help="Path to the PDF file to split. If omitted, prompts or auto-detects in current directory."
    )
    parser.add_argument(
        "--target-mb",
        type=float,
        default=DEFAULT_TARGET_MB,
        help=f"Target maximum file size in MB for each slot (default: {DEFAULT_TARGET_MB} MB)."
    )
    parser.add_argument(
        "--parts",
        type=str,
        default="auto",
        help="Number of parts / slots: 'auto' (optimal quality), or force '2' or '3'."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save output files (default: folder '<filename>_output' next to the input PDF)."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed diagnostic search logs during execution."
    )

    args = parser.parse_args()

    input_file = resolve_input_file(args.input_pdf)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else (input_file.parent / f"{input_file.stem}_output")

    process_pdf(
        input_path=input_file,
        output_dir=output_dir,
        target_mb=args.target_mb,
        parts_arg=args.parts,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
