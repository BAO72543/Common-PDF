#!/usr/bin/env python3
"""
Common App PDF Compressor
-------------------------
Compresses heavy PDF documents into a single file <= 2000 KB for Common App upload slots.
- Maximum Resolution Retention: Uses a micro-stepped DPI ladder to retain the highest possible sharpness.
- Lossless When Possible: If already <= 2000 KB, preserves 100% original quality.
- Clean Output: Generates '<filename>_compressed.pdf' ready for direct upload.
"""

import os
import sys
import shutil
import argparse
import subprocess
import tempfile
from pathlib import Path
import pikepdf

# Common App strict limit is 2000 KB.
# Default target is 1980 KB to guarantee a 20 KB safety margin.
DEFAULT_TARGET_KB = 1980

# Micro-stepped DPI ladder (from highest native quality down with fine-grained steps)
# This retains maximum visual sharpness by finding the exact threshold where files fit <= 2000 KB.
QUALITY_PROFILES = [
    {"name": "Original (100% Lossless Quality)", "type": "none", "gs_setting": None, "dpi": None},
    {"name": "Prepress (300 DPI)", "type": "gs", "gs_setting": "/prepress", "dpi": 300},
    {"name": "Ultra High (280 DPI)", "type": "gs", "gs_setting": "/prepress", "dpi": 280},
    {"name": "Ultra High (260 DPI)", "type": "gs", "gs_setting": "/prepress", "dpi": 260},
    {"name": "High Quality (240 DPI)", "type": "gs", "gs_setting": "/printer", "dpi": 240},
    {"name": "High Quality (220 DPI)", "type": "gs", "gs_setting": "/printer", "dpi": 220},
    {"name": "High Quality (210 DPI)", "type": "gs", "gs_setting": "/printer", "dpi": 210},
    {"name": "High Quality (205 DPI)", "type": "gs", "gs_setting": "/printer", "dpi": 205},
    {"name": "High Quality (200 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 200},
    {"name": "Near-Native (195 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 195},
    {"name": "Near-Native (190 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 190},
    {"name": "Medium High (185 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 185},
    {"name": "Medium High (180 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 180},
    {"name": "Medium High (175 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 175},
    {"name": "Medium High (170 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 170},
    {"name": "Medium High (165 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 165},
    {"name": "Medium (160 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 160},
    {"name": "Medium (155 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 155},
    {"name": "Balanced eBook (150 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 150},
    {"name": "Balanced (140 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 140},
    {"name": "Good (130 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 130},
    {"name": "Good Screen (120 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 120},
    {"name": "Moderate (110 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 110},
    {"name": "Moderate (100 DPI)", "type": "gs", "gs_setting": "/ebook", "dpi": 100},
    {"name": "Standard Screen (96 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 96},
    {"name": "Compact (85 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 85},
    {"name": "Compact (72 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 72},
    {"name": "Heavy (60 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 60},
    {"name": "Heavy Compression (50 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 50},
    {"name": "Maximum Compression (36 DPI)", "type": "gs", "gs_setting": "/screen", "dpi": 36},
]


def format_size(bytes_size: int) -> str:
    """Format bytes into readable string with both KB and MB."""
    kb = bytes_size / 1024
    mb = bytes_size / (1024 * 1024)
    return f"{kb:,.0f} KB ({mb:.2f} MB)"


def check_ghostscript() -> bool:
    """Check if Ghostscript ('gs') is installed."""
    return shutil.which("gs") is not None


def compress_pdf_with_gs(input_path: Path, output_path: Path, setting: str, dpi: int) -> bool:
    """Run Ghostscript to compress a PDF with specified quality settings."""
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
    """Find candidate PDF files in search_dir, ignoring previously compressed outputs."""
    pdfs = []
    for file in sorted(search_dir.glob("*.pdf")):
        if "_compressed" in file.stem or file.stem.isdigit():
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


def compress_single_pdf(
    input_path: Path,
    output_path: Path,
    target_kb: int,
    verbose: bool = False
):
    """
    Compresses a single PDF to <= target_kb while preserving maximum DPI quality.
    """
    target_bytes = target_kb * 1024
    orig_bytes = input_path.stat().st_size

    try:
        with pikepdf.Pdf.open(input_path) as pdf:
            total_pages = len(pdf.pages)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        sys.exit(1)

    print("-" * 64)
    print(f"Document: {input_path.name}")
    print(f"Size:     {format_size(orig_bytes)} ({total_pages} pages)")
    print(f"Limit:    <= 2000 KB (Target: {target_kb:,} KB)")

    # Check if already under target
    if orig_bytes <= target_bytes:
        print("Quality:  Original (Already <= 2000 KB, no compression needed)")
        shutil.copy2(input_path, output_path)
        final_size = output_path.stat().st_size
        print(f"Output:   {output_path.name}")
        print(f"Result:   {format_size(final_size)} [OK <= 2000 KB]")
        print("-" * 64)
        print("Done: Ready for Common App upload.")
        return

    if not check_ghostscript():
        print("Error: Ghostscript ('gs') command not found.")
        print("Compression requires Ghostscript. Please install it (e.g., sudo apt/dnf install ghostscript).")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as td:
        tpath = Path(td)
        chosen_profile = None
        best_file = None

        tested_profiles = [p for p in QUALITY_PROFILES if p["type"] == "gs"]
        for profile in tested_profiles:
            p_name = profile["name"]
            setting = profile["gs_setting"]
            dpi = profile["dpi"]

            trial_file = tpath / f"trial_{dpi}dpi.pdf"
            if not compress_pdf_with_gs(input_path, trial_file, setting, dpi):
                continue

            sz = trial_file.stat().st_size
            passed = sz <= target_bytes

            if verbose:
                status = "PASS" if passed else "FAIL"
                print(f"  [{dpi:3d} DPI] {p_name:<28} -> {format_size(sz):<18} [{status}]")

            if passed:
                chosen_profile = profile
                best_file = trial_file
                break

        if not chosen_profile:
            # Fallback to the most compressed profile
            chosen_profile = tested_profiles[-1]
            best_file = tpath / f"trial_{chosen_profile['dpi']}dpi.pdf"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best_file, output_path)
        final_size = output_path.stat().st_size
        is_under = final_size <= (2000 * 1024)
        status_tag = "OK <= 2000 KB" if is_under else "OVER 2000 KB"

        print(f"Quality:  {chosen_profile['name']}")
        print(f"Output:   {output_path.name}")
        print(f"Result:   {format_size(final_size)} [{status_tag}]")
        print("-" * 64)

        if is_under:
            print("Done: 1 single file under 2000 KB. Ready for Common App upload.")
        else:
            print("Notice: Document is extremely dense. Review size above.")


def main():
    parser = argparse.ArgumentParser(
        description="Compress a heavy PDF into 1 single file (<= 2000 KB) for Common App."
    )
    parser.add_argument(
        "input_pdf",
        nargs="?",
        help="Path to the PDF file to compress. If omitted, prompts or auto-detects in current directory."
    )
    parser.add_argument(
        "--target-kb",
        type=int,
        default=DEFAULT_TARGET_KB,
        help=f"Target maximum file size in KB (default: {DEFAULT_TARGET_KB} KB, safely under 2000 KB)."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output file path (default: '<filename>_compressed.pdf' next to input)."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed diagnostic search logs during execution."
    )

    args = parser.parse_args()

    input_file = resolve_input_file(args.input_pdf)
    output_file = Path(args.output).resolve() if args.output else (input_file.parent / f"{input_file.stem}_compressed.pdf")

    compress_single_pdf(
        input_path=input_file,
        output_path=output_file,
        target_kb=args.target_kb,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
