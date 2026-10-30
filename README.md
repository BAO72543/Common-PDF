# Common App PDF Splitter & Universal Compressor

> A lightweight, student-first Python CLI tool to split and universally compress heavy PDF documents for **Common App's upload slots (<= 2.0 MB each)** without sacrificing visual consistency.

---

## The Problem

When submitting portfolios, school profiles, academic transcripts, or additional information to the **Common App**, applicants are given **up to 3 upload slots**, each strictly limited to **<= 2.0 MB**.

Traditional tools and online converters often cause issues:

1. **Unnecessary Quality Loss**: Many tools degrade quality to compress a file into 2 parts, even when using 3 parts would preserve 100% native uncompressed quality or achieve much higher resolution.
2. **Inconsistent Quality Across Pages**: Naive scripts compress only the parts that exceed 2 MB. As a result, Part 1 might look ultra-crisp while Part 2 or 3 looks blurry and pixelated.
3. **File Overwrites**: Tools that dump generic file names in the root folder force you to delete or move previous files before processing a new document.
4. **File Size Rejection**: Files hovering right around 2,000 KB frequently get rejected by Common App's strict byte validator.
5. **Privacy Concerns**: Uploading confidential academic records or personal portfolios to online web converters is risky.

---

## Core Decision Hierarchy

The tool is built around maximizing document quality for college admissions officers:

### Priority 1: Original Quality First (Lossless)
- If dividing into 2 parts keeps both files under 2 MB without compression, it uses **2 parts at 100% original quality**.
- If 2 parts exceeds 2 MB uncompressed, but dividing into 3 parts stays under 2 MB uncompressed, it chooses **3 parts at 100% original quality**.
- **Rule**: Never degrade image or text quality just to force a 2-file split if 3 lossless slots can preserve native clarity.

### Priority 2: Higher Quality Maximization (When Compression is Required)
- **If neither 2 parts nor 3 parts can fit uncompressed under 2 MB**, compression is required.
- In this case, the tool **chooses 3 parts**. Distributing pages across 3 parts allows each file to maintain a **higher DPI and sharper visual quality** (e.g., 180 DPI instead of 150 DPI) while staying strictly under 2.0 MB.

### Universal Quality Guarantee
- Whenever compression is applied, the tool enforces the **exact same DPI and compression profile across all parts**.
- Admissions officers see a completely uniform document with consistent resolution and clarity from the first page to the last.

---

## Features

- **Quality-First Optimization**: Preserves 100% original lossless quality whenever possible. When compression is needed, chooses 3 parts to maximize resolution and sharpness.
- **Smart Size-Aware Partitioning**: Instead of blindly dividing by page count (e.g. 5/5), analyzes actual byte weights per page so heavy image scans are balanced across files, avoiding unnecessary extra splits.
- **Dedicated Output Folders**: Each document is placed into its own folder (`<filename>_output/`), allowing you to process multiple documents back-to-back without file collisions or overwriting old files.
- **Uniform Output Naming**: Outputs clean `1.pdf`, `2.pdf`, and `3.pdf`, directly matching Common App upload slots.
- **Safe Margin (1.95 MB)**: Targets 1.95 MB (~2,044 KB) by default to prevent upload failures caused by MB vs. MiB rounding differences.
- **100% Local & Private**: Runs entirely on your machine via Ghostscript and PikePDF. No documents leave your computer.
- **Smart Auto-Detection**: Drop your PDF in the folder and run `python3 run.py` -- it detects and processes your document automatically.

---

## Requirements

- **Python 3.8+**
- **Ghostscript** (Standard PDF rendering and compression engine)
- **pikepdf** (Fast, lossless PDF manipulation engine)

### Installing Dependencies

#### Ubuntu / Debian / Linux Mint:

```bash
sudo apt update
sudo apt install -y ghostscript python3-pip
pip install pikepdf
```

#### Fedora / RHEL:

```bash
sudo dnf install -y ghostscript python3-pip
pip install pikepdf
```

#### macOS (via Homebrew):

```bash
brew install ghostscript
pip3 install pikepdf
```

---

## Quickstart

### 1. Simple Run (Auto-detect & Auto-optimize)

Place your PDF in the same folder as `run.py` and run:

```bash
python3 run.py
```

- If 2 parts fits uncompressed, it outputs `1.pdf` and `2.pdf` (100% lossless).
- If 3 parts fits uncompressed, it outputs `1.pdf`, `2.pdf`, and `3.pdf` (100% lossless).
- If compression is required, it chooses 3 parts (`1.pdf`, `2.pdf`, `3.pdf`) to maximize visual quality.
- All outputs are placed in a dedicated folder named `<your_pdf_name>_output/`.

### 2. Specify File via Command Line

```bash
python3 run.py "my_transcript.pdf"
```

### 3. Custom Options

```bash
# Force exactly 2 parts or 3 parts (overriding auto-optimization)
python3 run.py "my_document.pdf" --parts 2
python3 run.py "my_document.pdf" --parts 3

# Set a custom target threshold (e.g. 1.80 MB)
python3 run.py "my_portfolio.pdf" --target-mb 1.80

# Specify a custom output directory
python3 run.py "my_portfolio.pdf" --output-dir ./custom_folder
```

---

## Output Structure

Each processed document automatically gets its own dedicated folder. This allows you to process multiple documents (e.g., transcripts, portfolios, certificates) back-to-back without file collisions:

```
project_folder/
├── Transcript.pdf
├── Portfolio.pdf
├── Transcript_output/
│   ├── 1.pdf           -> Upload to Slot 1
│   ├── 2.pdf           -> Upload to Slot 2
│   └── 3.pdf           -> Upload to Slot 3 (100% original quality)
└── Portfolio_output/
    ├── 1.pdf           -> Upload to Slot 1
    ├── 2.pdf           -> Upload to Slot 2
    └── 3.pdf           -> Upload to Slot 3 (maximum universal DPI)
```

---

## How the Decision Flow Works

```
Original Multi-Page PDF
          |
          v
[Phase 1: Original Quality Check]
Does 2 parts fit uncompressed (<= 1.95 MB)?
 |-- YES --> Save 2 parts with 100% Original Quality.
 `-- NO  --> Does 3 parts fit uncompressed (<= 1.95 MB)?
               |-- YES --> Save 3 parts with 100% Original Quality!
               |           (Avoids compression blurriness entirely).
               `-- NO  --> [Phase 2: Universal Quality Compression]
                           Neither 2 nor 3 fits uncompressed.
                           Choose 3 parts to maximize DPI and visual sharpness!
                           Find highest universal DPI where all 3 parts are <= 1.95 MB.
```

---

## Disclaimer

This is an open-source, independent helper utility created for students and applicants. It is not affiliated with or endorsed by the Common Application.

---

## License

MIT License. Free to use, adapt, and share with fellow applicants!
