# Common App PDF Compressor

> A lightweight, student-first Python CLI tool to compress heavy PDF documents into a **single file under 2000 KB** for Common App upload slots while preserving maximum visual sharpness.

---

## Overview

When submitting documents to the **Common App**, each upload slot strictly enforces the limit:

> *"This file cannot be uploaded. Please ensure the combined file size is 2000 KB or less."*

This tool takes any heavy PDF and compresses it directly into **one single file** under 2000 KB, using a fine-grained, micro-stepped DPI ladder to retain the highest possible resolution.

---

## Features

- **Single File Output**: Compresses the entire document into 1 single file without splitting pages.
- **Strict 2000 KB Compliance**: Targets 1980 KB to provide a safe buffer against server-side byte rounding.
- **Maximum Resolution Retention**: Uses narrow DPI steps (300 down through 280, 260, 240, 220, 210, 205, 200, 195, 190, 185, 180, 175, 170, 165, 160, 155, 150, 140, 130, 120, 110, 100, 96, 85, 72, 60, 50, 36). It stops at the exact threshold where the file fits <= 2000 KB, preserving maximum clarity.
- **Lossless When Possible**: If the document is already <= 2000 KB, it retains 100% native original quality.
- **Clean Output Naming**: Automatically creates `<filename>_compressed.pdf` next to your original file.
- **100% Local & Private**: Runs entirely on your machine via Ghostscript. No documents are uploaded to online web converters.
- **Concise Logging**: Displays original size, pages, chosen DPI quality, final size in KB/MB, and clear confirmation.

---

## Requirements

- **Python 3.8+**
- **Ghostscript** (Standard PDF rendering engine)
- **pikepdf** (Fast PDF manipulation engine)

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

### 1. Interactive Run (Auto-detect)

Place your PDF in the same folder as `run.py` and run:

```bash
python3 run.py
```

If one PDF is found, press Enter to process. If multiple PDFs are found, select by number.

### 2. Specify File via Command Line

```bash
python3 run.py "my_transcript.pdf"
```

The script outputs `my_transcript_compressed.pdf` right next to the original file.

### 3. Custom Options

```bash
# Set a custom target threshold in KB (default: 1980 KB)
python3 run.py "my_portfolio.pdf" --target-kb 1950

# Specify custom output path
python3 run.py "my_portfolio.pdf" -o "./output/portfolio_ready.pdf"

# View internal DPI trial search
python3 run.py "my_portfolio.pdf" -v
```

---

## Example Output

```
----------------------------------------------------------------
Document: Test.pdf
Size:     6,060 KB (5.92 MB) (16 pages)
Limit:    <= 2000 KB (Target: 1,980 KB)
Quality:  Good Screen (120 DPI)
Output:   Test_compressed.pdf
Result:   1,893 KB (1.85 MB) [OK <= 2000 KB]
----------------------------------------------------------------
Done: 1 single file under 2000 KB. Ready for Common App upload.
```

---

## Disclaimer

This is an open-source helper utility created for students and applicants. It is not affiliated with or endorsed by the Common Application.

---

## License

MIT License. Free to use, adapt, and share with fellow applicants!
